import unittest

from app.services.ia_analysis_service import (
    aplicar_guardas_mibanco_v3,
    estado_sgc_normalizado,
    validar_mapping_speakers_estandar_v3,
)
from app.services.ia_audio_service import (
    obtener_transcripcion_para_analisis,
    transcripcion_diarizada_valida,
)


def criterio(codigo, peso, estado="REQUIERE_REVISION"):
    return {
        "codigo_criterio": codigo,
        "peso": float(peso),
        "estado": estado,
        "resultado": "Requiere revisión",
    }


class IaFeedbackStabilityTests(unittest.TestCase):
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
        ]
        base = {
            "PENC.2": criterio("PENC.2", 1),
            "PENC.4": criterio("PENC.4", 2),
            "PENC.7": criterio("PENC.7", 6),
            "PECUF.3": criterio("PECUF.3", 4),
            "PECUF.4": criterio("PECUF.4", 6),
            "PECUF.5": criterio("PECUF.5", 8),
            "PECUF.6": criterio("PECUF.6", 4),
            "PECUF.7": criterio("PECUF.7", 3),
            "PECUF.8": criterio("PECUF.8", 1),
            "PECUF.10": criterio("PECUF.10", 3),
            "PECC.2": criterio("PECC.2", 4),
            "PECC.3": criterio("PECC.3", 4),
            "PECC.4": criterio("PECC.4", 4),
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
        self.assertEqual(resultados[0]["PECUF.4"], ("CUMPLE", 6.0))
        self.assertEqual(resultados[0]["PECC.4"], ("REQUIERE_REVISION", 0.0))

    def test_state_separation_is_preserved(self):
        self.assertEqual(estado_sgc_normalizado({"estado": "NO_APLICA"}), "NO_APLICA")
        self.assertEqual(estado_sgc_normalizado({"estado": "NO_EVALUABLE"}), "NO_EVALUABLE")
        self.assertEqual(estado_sgc_normalizado({"estado": "REQUIERE_REVISION"}), "REQUIERE_REVISION")


if __name__ == "__main__":
    unittest.main()
