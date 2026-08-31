import unittest

from app.services.ia_analysis_service import (
    aplicar_guardas_mibanco_v3,
    evaluar_calidad_transcripcion_v3,
    normalizar_errores_criticos_v2,
    estado_sgc_normalizado,
    validar_mapping_speakers_estandar_v3,
)
from app.services.ia_audio_service import (
    obtener_transcripcion_para_analisis,
    transcripcion_diarizada_valida,
)
from app.services.mibanco_quality_pauta import (
    obtener_pauta_mibanco,
    resumen_pesos_mibanco,
)


def criterio(codigo, peso, estado="REQUIERE_REVISION"):
    return {
        "codigo_criterio": codigo,
        "peso": float(peso),
        "estado": estado,
        "resultado": "Requiere revisión",
    }


class IaFeedbackStabilityTests(unittest.TestCase):
    def test_transcription_quality_gate_marks_complete_diarization_as_usable(self):
        segmentos = [
            {"segmento_id": 1, "speaker_original": "A", "rol": "AGENTE", "inicio_segundos": 0, "fin_segundos": 2, "texto_original": "Buenos días."},
            {"segmento_id": 2, "speaker_original": "B", "rol": "CLIENTE", "inicio_segundos": 2, "fin_segundos": 4, "texto_original": "Sí, dígame."},
        ]

        calidad = evaluar_calidad_transcripcion_v3(segmentos)

        self.assertEqual(calidad["nivel"], "ALTA")
        self.assertFalse(calidad["requiere_revision_humana"])
        self.assertEqual(calidad["metricas"]["roles"]["cobertura_roles_pct"], 100.0)

    def test_transcription_quality_gate_requires_review_for_low_role_coverage(self):
        segmentos = [
            {"segmento_id": 1, "speaker_original": "A", "rol": "AGENTE", "inicio_segundos": 0, "fin_segundos": 2, "texto_original": "Buenos días."},
            {"segmento_id": 2, "speaker_original": "B", "rol": "NO_DETERMINADO", "inicio_segundos": 2, "fin_segundos": 4, "texto_original": "Sí."},
        ]

        calidad = evaluar_calidad_transcripcion_v3(segmentos)

        self.assertEqual(calidad["nivel"], "BAJA")
        self.assertTrue(calidad["requiere_revision_humana"])
        self.assertIn("cobertura de roles", calidad["motivo"].lower())

    def test_reuses_canonical_diarized_transcription(self):
        canonica = "\n".join([
            "#TRANSCRIPCION_DIARIZADA_V1",
            '#SPEAKERS {"A":"AGENTE","B":"CLIENTE"}',
            "[00:00] {A} <AGENTE> (0.0-1.0) Buenos dias.",
            "[00:01] {B} <CLIENTE> (1.0-2.0) Si.",
        ])

        self.assertTrue(transcripcion_diarizada_valida(canonica))
        texto, generada = obtener_transcripcion_para_analisis(
            {"transcripcion": canonica, "ruta_archivo": "no-debe-usarse.wav"},
            forzar_transcripcion=False,
        )

        self.assertEqual(texto, canonica)
        self.assertFalse(generada)

    def test_corrects_multi_speaker_all_agent_mapping(self):
        speakers = {
            "A": [
                {"texto": "Buenos dias, le habla Maria de Mibanco por su credito pendiente."},
                {"texto": "Puede abonar hoy?"},
            ],
            "B": [
                {"texto": "No puedo pagar porque tengo problemas y otros bancos."},
                {"texto": "Podria pagar una parte la semana siguiente."},
            ],
            "C": [{"texto": "Si."}],
        }
        mapping_ia = {speaker: {"rol": "AGENTE", "confianza": "ALTA"} for speaker in speakers}

        mapping = validar_mapping_speakers_estandar_v3(speakers, mapping_ia)

        roles = {item["rol"] for item in mapping.values()}
        self.assertIn("AGENTE", roles)
        self.assertIn("CLIENTE", roles)

    def test_mibanco_guards_are_deterministic_for_same_segments(self):
        segmentos = [
            {
                "segmento_id": 1,
                "hablante": "AGENTE",
                "rol": "AGENTE",
                "texto": "Buenos dias, le habla Maria de Mibanco con la señora Marta.",
                "inicio_segundos": 0,
                "fin_segundos": 2,
            },
            {
                "segmento_id": 2,
                "hablante": "CLIENTE",
                "rol": "CLIENTE",
                "texto": "Tengo problemas con mi esposo y no he podido pagar.",
                "inicio_segundos": 3,
                "fin_segundos": 6,
            },
            {
                "segmento_id": 3,
                "hablante": "AGENTE",
                "rol": "AGENTE",
                "texto": "Ya entiendo, señora. Cuánto ha podido recaudar para llegar a una solución?",
                "inicio_segundos": 7,
                "fin_segundos": 10,
            },
            {
                "segmento_id": 4,
                "hablante": "CLIENTE",
                "rol": "CLIENTE",
                "texto": "Cómo sería?",
                "inicio_segundos": 11,
                "fin_segundos": 12,
            },
            {
                "segmento_id": 5,
                "hablante": "AGENTE",
                "rol": "AGENTE",
                "texto": "Puede abonar una parte y luego coordinamos la fecha de pago.",
                "inicio_segundos": 13,
                "fin_segundos": 16,
            },
            {
                "segmento_id": 6,
                "hablante": "AGENTE",
                "rol": "AGENTE",
                "texto": "Gracias, que tenga buen día.",
                "inicio_segundos": 17,
                "fin_segundos": 18,
            },
        ]
        base = {
            "PENC.1": criterio("PENC.1", 2),
            "PENC.2": criterio("PENC.2", 3),
            "PENC.3": criterio("PENC.3", 3),
            "PENC.4": criterio("PENC.4", 2),
            "PECUF.1": criterio("PECUF.1", 20),
            "PECUF.2": criterio("PECUF.2", 2),
            "PECUF.3": criterio("PECUF.3", 5),
            "PECUF.4": criterio("PECUF.4", 3),
            "PECN.1": criterio("PECN.1", 5),
            "PECN.2": criterio("PECN.2", 10),
            "PECN.3": criterio("PECN.3", 15),
            "PECN.4": criterio("PECN.4", 10),
            "PECC.1": criterio("PECC.1", 5),
            "PECC.2": criterio("PECC.2", 5),
            "PECC.3": criterio("PECC.3", 10),
        }

        resultados = []
        for _ in range(2):
            data = {codigo: dict(valor) for codigo, valor in base.items()}
            aplicar_guardas_mibanco_v3(segmentos, data)
            resultados.append({
                codigo: (estado_sgc_normalizado(item), item.get("puntaje_obtenido"))
                for codigo, item in sorted(data.items())
            })

        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(resultados[0]["PENC.4"], ("CUMPLE", 2.0))
        self.assertEqual(resultados[0]["PECUF.4"], ("CUMPLE", 3.0))
        self.assertEqual(resultados[0]["PECC.3"], ("NO_EVALUABLE", 0.0))

    def test_pecn_requires_negotiation_and_close_without_confirmed_third_or_cut(self):
        segmentos = [
            {"segmento_id": 1, "rol": "AGENTE", "texto": "Buenos días, le habla Ana de Mibanco."},
            {"segmento_id": 2, "rol": "CLIENTE", "texto": "Sí, pero ahora no puedo pagar."},
            {"segmento_id": 3, "rol": "AGENTE", "texto": "Entiendo."},
        ]
        data = {
            "PECN.1": criterio("PECN.1", 5),
            "PECN.2": criterio("PECN.2", 10),
            "PECN.3": criterio("PECN.3", 15),
            "PECN.4": criterio("PECN.4", 10),
        }

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECN.1"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.2"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.3"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.4"]), "NO_CUMPLE")

    def test_pecn_only_marks_no_aplica_for_confirmed_third_or_explicit_cut(self):
        segmentos = [
            {"segmento_id": 1, "rol": "AGENTE", "texto": "Buenos días, ¿hablo con la titular?"},
            {"segmento_id": 2, "rol": "CLIENTE", "texto": "No soy, soy su hermano."},
        ]
        data = {
            "PECN.1": criterio("PECN.1", 5),
            "PECN.2": criterio("PECN.2", 10),
            "PECN.3": criterio("PECN.3", 15),
            "PECN.4": criterio("PECN.4", 10),
        }

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertNotEqual(estado_sgc_normalizado(data["PECN.1"]), "NO_APLICA")
        self.assertEqual(estado_sgc_normalizado(data["PECN.2"]), "NO_APLICA")
        self.assertEqual(estado_sgc_normalizado(data["PECN.3"]), "NO_APLICA")
        self.assertEqual(estado_sgc_normalizado(data["PECN.4"]), "NO_APLICA")

    def test_agent_proposal_is_not_a_confirmed_customer_commitment(self):
        segmentos = [
            {"segmento_id": 1, "rol": "AGENTE", "texto": "Puede abonar 500 soles mañana."},
            {"segmento_id": 2, "rol": "CLIENTE", "texto": "Lo voy a pensar."},
        ]
        data = {"PECN.4": criterio("PECN.4", 10), "PECC.2": criterio("PECC.2", 5)}

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECN.4"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECC.2"]), "NO_APLICA")

    def test_pecn_accepts_a_later_discount_alternative_after_objection(self):
        segmentos = [
            {"segmento_id": 1, "rol": "AGENTE", "texto": "¿A qué se debe el atraso y cuánto podría pagar?"},
            {"segmento_id": 2, "rol": "CLIENTE", "texto": "Porque tuve un problema y no tengo forma de pagar ese importe ahora."},
            *[
                {"segmento_id": indice, "rol": "CLIENTE" if indice % 2 else "AGENTE", "texto": "Entiendo."}
                for indice in range(3, 13)
            ],
            {"segmento_id": 13, "rol": "AGENTE", "texto": "Podemos aplicar el descuento vigente y dejar una cuota menor."},
        ]
        data = {
            "PECN.2": criterio("PECN.2", 10),
            "PECN.3": criterio("PECN.3", 15),
        }

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECN.2"]), "CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.3"]), "CUMPLE")

    def test_pecn_rejects_generic_quota_offer_when_it_ignores_material_context(self):
        segmentos = [
            {"segmento_id": 1, "rol": "AGENTE", "texto": "¿A qué se debe el atraso y cuánto podría pagar actualmente?"},
            {"segmento_id": 2, "rol": "CLIENTE", "texto": "Tuve una pérdida grande en agricultura y recién tendré dinero por la cosecha de marzo; ahora no puedo cancelar."},
            {"segmento_id": 3, "rol": "AGENTE", "texto": "Ya entiendo. Puede abonar dos cuotas para ponerse al día."},
            {"segmento_id": 4, "rol": "CLIENTE", "texto": "Pero necesito una alternativa que considere mi cosecha."},
            {"segmento_id": 5, "rol": "AGENTE", "texto": "Puede ir pagando cuotas poco a poco."},
        ]
        data = {
            "PECN.1": criterio("PECN.1", 5),
            "PECN.2": criterio("PECN.2", 10),
            "PECN.3": criterio("PECN.3", 15),
        }

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECN.1"]), "CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.2"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.3"]), "NO_CUMPLE")
        self.assertIn("cosecha", " ".join(data["PECN.2"].get("evidencia_textual") or []).lower())

    def test_coercion_and_humiliation_are_not_accepted_as_negotiation(self):
        segmentos = [
            {"segmento_id": 1, "rol": "CLIENTE", "texto": "No tengo dinero, estoy trabajando pero no me alcanza."},
            {"segmento_id": 2, "rol": "AGENTE", "texto": "Lo va a tener que conseguir porque tiene que pagar; las leyes le va a obligar."},
            {"segmento_id": 3, "rol": "AGENTE", "texto": "Parece que no es empresario, porque no tiene plata ni para pagarme."},
            {"segmento_id": 4, "rol": "CLIENTE", "texto": "Llame otro día, estoy manejando."},
            {"segmento_id": 5, "rol": "AGENTE", "texto": "Que tenga buen día."},
        ]
        data = {
            "PECUF.1": criterio("PECUF.1", 20),
            "PECN.2": criterio("PECN.2", 10),
            "PECN.3": criterio("PECN.3", 15),
            "PECN.4": criterio("PECN.4", 10),
        }

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECUF.1"]), "NO_CUMPLE")
        self.assertTrue(data["PECUF.1"].get("posible_descalificacion"))
        self.assertIn("no tiene plata", " ".join(data["PECUF.1"].get("evidencia_textual") or []).lower())
        self.assertEqual(estado_sgc_normalizado(data["PECN.2"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.3"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.4"]), "NO_CUMPLE")
        self.assertIn("manejando", " ".join(data["PECN.4"].get("evidencia_textual") or []).lower())

    def test_pecn_requires_cause_and_capacity_for_diagnosis_and_escalation(self):
        segmentos = [
            {"segmento_id": 1, "rol": "AGENTE", "texto": "¿Cuánto podría pagar hoy?"},
            {"segmento_id": 2, "rol": "CLIENTE", "texto": "Podría pagar una parte."},
            {"segmento_id": 3, "rol": "AGENTE", "texto": "Podemos aplicar un descuento."},
        ]
        data = {"PECN.1": criterio("PECN.1", 5), "PECN.2": criterio("PECN.2", 10)}

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECN.1"]), "NO_CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECN.2"]), "NO_CUMPLE")

    def test_follow_up_schedule_closes_management_without_payment_agreement(self):
        segmentos = [
            {"segmento_id": 1, "rol": "AGENTE", "texto": "Le llamaré hoy a las 17:00 para revisar la respuesta."},
            {"segmento_id": 2, "rol": "CLIENTE", "texto": "Sí."},
        ]
        data = {"PECN.4": criterio("PECN.4", 10), "PECC.2": criterio("PECC.2", 5)}

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECN.4"]), "CUMPLE")
        self.assertEqual(estado_sgc_normalizado(data["PECC.2"]), "NO_APLICA")

    def test_vague_future_intent_is_not_a_confirmed_payment_agreement(self):
        segmentos = [
            {"segmento_id": 1, "rol": "CLIENTE", "texto": "De todas formas lo voy a cancelar."},
        ]
        data = {"PECC.2": criterio("PECC.2", 5)}

        aplicar_guardas_mibanco_v3(segmentos, data)

        self.assertEqual(estado_sgc_normalizado(data["PECC.2"]), "NO_APLICA")

    def test_mibanco_catalog_matches_current_excel_weights(self):
        self.assertEqual(len(obtener_pauta_mibanco()), 15)
        self.assertEqual(
            resumen_pesos_mibanco(),
            {
                "PECUF": 30.0,
                "PECN": 30.0,
                "PECC": 30.0,
                "PENC": 10.0,
                "TOTAL": 100.0,
            },
        )

    def test_state_separation_is_preserved(self):
        self.assertEqual(estado_sgc_normalizado({"estado": "NO_APLICA"}), "NO_APLICA")
        self.assertEqual(estado_sgc_normalizado({"estado": "NO_EVALUABLE"}), "NO_EVALUABLE")
        self.assertEqual(estado_sgc_normalizado({"estado": "REQUIERE_REVISION"}), "REQUIERE_REVISION")

    def test_sgc_hallazgos_merge_raw_and_matrix_findings(self):
        raw = [
            {
                "codigo_criterio": "3.5",
                "grupo_error_sgc": "Errores críticos del negocio",
                "factor_sgc": "Manejo de objeciones",
                "calificacion": "No cumple",
                "hallazgo": "No aborda la objeción económica del cliente.",
                "evidencia": "CLIENTE: No puedo pagar ese monto.",
            }
        ]
        evaluacion = [
            {
                "codigo_criterio": "4.3",
                "segmento": "Cierre verificable",
                "segmento_copc": "Cierre verificable",
                "grupo_error_sgc": "Errores críticos del negocio",
                "grupo_sgc_codigo": "ERROR_CRITICO_NEGOCIO",
                "factor_sgc": "Cierre verificable 3C/4C",
                "estado": "NO_CUMPLE",
                "resultado": "No cumple",
                "calificacion": "No cumple",
                "hallazgo": "No confirma canal de pago.",
                "evidencia": "AGENTE: queda para mañana.",
                "impacto": "El compromiso queda incompleto.",
                "recomendacion": "Confirmar el canal de pago antes de cerrar.",
                "error_sgc_confirmado": True,
            }
        ]

        hallazgos = normalizar_errores_criticos_v2(raw, evaluacion)
        factores = {item.get("factor_sgc") for item in hallazgos}

        self.assertIn("Manejo de objeciones", factores)
        self.assertIn("Cierre verificable 3C/4C", factores)

    def test_mibanco_absence_findings_reach_sgc(self):
        evaluacion = [
            {
                "codigo_criterio": codigo,
                "segmento": "Gesti\u00f3n de soluci\u00f3n y negociaci\u00f3n",
                "segmento_copc": "Gesti\u00f3n de soluci\u00f3n y negociaci\u00f3n",
                "estado": "NO_CUMPLE",
                "resultado": "No cumple",
                "calificacion": "No cumple",
                "hallazgo": hallazgo,
                "evidencia": "CLIENTE: Ahorita no.",
                "impacto": "No se conduce la gesti\u00f3n hacia una alternativa verificable.",
                "recomendacion": "Profundizar la negociaci\u00f3n antes de cerrar.",
                "error_sgc_confirmado": True,
            }
            for codigo, hallazgo in (
                ("PECN.2", "No se observa una alternativa posterior y adaptada a la objeci\u00f3n."),
                ("PECN.3", "No se observa abordaje posterior suficiente de la objeci\u00f3n."),
                ("PECN.4", "No se identifica promesa de pago ni siguiente acci\u00f3n verificable."),
            )
        ]

        hallazgos = normalizar_errores_criticos_v2(None, evaluacion)

        self.assertEqual({item["codigo_criterio"] for item in hallazgos}, {"PECN.2", "PECN.3", "PECN.4"})


if __name__ == "__main__":
    unittest.main()
