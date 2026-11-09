"""Cierre historico de importacion: emparejamiento de columnas, conversion de
valores confirmados y validacion de columnas numericas.

No usan la base de datos (engine y consultas simulados).

    python -m unittest tests.test_importacion_cierre -v
"""

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.services import importacion_service as svc


def col(nombre, tipo="varchar", **extra):
    return {"column_name": nombre, "data_type": tipo, "is_nullable": 1, "is_identity": 0, **extra}


HIST_INDIVIDUAL = "Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_INDIVIDUAL"
ORIGEN_INDIVIDUAL = "Desarrollo.dbo.compartamos_individual"


@contextmanager
def engine_falso(fila):
    consultas = []

    class Conn:
        def execute(self, query, params=None):
            consultas.append(str(query))
            resultado = MagicMock()
            resultado.mappings.return_value.first.return_value = fila
            return resultado

    @contextmanager
    def connect():
        yield Conn()

    engine = MagicMock()
    engine.connect.side_effect = connect
    with patch.object(svc, "engine_siscob", engine):
        yield consultas


class EmparejamientoColumnasTests(unittest.TestCase):
    def test_cancelacion_porcentaje_no_recibe_el_monto(self):
        origen = [col("Cancelación%"), col("Cancelacion")]
        historico = [col("Cancelación%", "float"), col("Cancelacion", "float")]

        emparejadas, ambiguas = svc.emparejar_columnas_cierre(origen, historico)

        self.assertEqual(emparejadas["Cancelación%"]["column_name"], "Cancelación%")
        self.assertEqual(emparejadas["Cancelacion"]["column_name"], "Cancelacion")
        self.assertEqual(ambiguas, [])

    def test_sin_columna_de_porcentaje_en_origen_no_se_rellena_con_el_monto(self):
        origen = [col("Cancelacion")]
        historico = [col("Cancelación%", "float"), col("Cancelacion", "float")]

        emparejadas, _ = svc.emparejar_columnas_cierre(origen, historico)

        self.assertNotIn("Cancelación%", emparejadas)
        self.assertEqual(emparejadas["Cancelacion"]["column_name"], "Cancelacion")

    def test_nombre_exacto_ignora_mayusculas(self):
        emparejadas, _ = svc.emparejar_columnas_cierre([col("FECULTPAGO")], [col("FecUltPago", "datetime")])
        self.assertEqual(emparejadas["FecUltPago"]["column_name"], "FECULTPAGO")

    def test_sin_nombre_exacto_usa_el_normalizado_si_es_unico(self):
        emparejadas, _ = svc.emparejar_columnas_cierre([col("Tipo Gestion")], [col("Tipo Gestión")])
        self.assertEqual(emparejadas["Tipo Gestión"]["column_name"], "Tipo Gestion")

    def test_normalizado_ambiguo_no_se_carga_y_se_informa(self):
        origen = [col("Monto_X"), col("MONTO-X")]
        emparejadas, ambiguas = svc.emparejar_columnas_cierre(origen, [col("Monto X", "float")])

        self.assertNotIn("Monto X", emparejadas)
        self.assertEqual(ambiguas, ["Monto X"])


class ExpresionesCierreTests(unittest.TestCase):
    def preparar(self, tabla_historica, historico, origen):
        return svc.preparar_columnas_cierre(
            columnas_origen=origen,
            columnas_historico=historico,
            campo_periodo="PERIODO",
            config={},
            periodo="202610",
            tabla_historica=tabla_historica,
        )

    def test_flg_cliref_convierte_n_y_r_en_vigente_individual(self):
        insert, select, params, faltantes = self.preparar(
            HIST_INDIVIDUAL,
            [col("FLG_CliRef", "float"), col("Cancelación%", "float"), col("PERIODO", "varchar")],
            [col("FLG_CliRef"), col("Cancelación%"), col("Cancelacion")],
        )

        self.assertEqual(insert, ["[FLG_CliRef]", "[Cancelación%]", "[PERIODO]"])
        self.assertEqual(
            select[0],
            "CASE UPPER(LTRIM(RTRIM(CONVERT(NVARCHAR(100), [FLG_CliRef])))) "
            "WHEN N'N' THEN 0 WHEN N'R' THEN 1 ELSE CONVERT(float, [FLG_CliRef]) END",
        )
        self.assertEqual(select[1], "[Cancelación%]")
        self.assertEqual(select[2], ":periodo_insert")
        self.assertEqual(params, {"periodo_insert": "202610"})
        self.assertEqual(faltantes, [])

    def test_la_conversion_no_se_aplica_a_otros_historicos(self):
        _, select, _, _ = self.preparar(
            "Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_GRUPAL",
            [col("FLG_CliRef", "float")],
            [col("FLG_CliRef")],
        )
        self.assertEqual(select, ["[FLG_CliRef]"])

    def test_sin_tabla_historica_se_mantiene_el_comportamiento_anterior(self):
        insert, select, _, _ = svc.preparar_columnas_cierre(
            [col("FLG_CliRef")], [col("FLG_CliRef", "float")], "PERIODO", {}, "202610",
        )
        self.assertEqual((insert, select), (["[FLG_CliRef]"], ["[FLG_CliRef]"]))

    def test_tipo_decimal_conserva_precision(self):
        self.assertEqual(svc.tipo_sql_destino({"data_type": "decimal", "precision": 18, "scale": 2}), "decimal(18,2)")
        self.assertEqual(svc.tipo_sql_destino({"data_type": "float"}), "float")


class ValoresNoNumericosTests(unittest.TestCase):
    def test_detecta_valores_que_romperian_el_insert(self):
        historico = [col("FLG_CliRef", "float"), col("Edad", "int"), col("Nomcliente", "varchar"), col("PERIODO", "float")]
        origen = [col("FLG_CliRef"), col("Edad"), col("Nomcliente"), col("PERIODO")]
        fila = {"filas_0": 2, "ej1_0": "X", "ej2_0": "Z", "filas_1": 0, "ej1_1": None, "ej2_1": None}

        with engine_falso(fila) as consultas:
            problemas = svc.detectar_valores_no_numericos(
                ORIGEN_INDIVIDUAL, HIST_INDIVIDUAL, origen, historico, "PERIODO",
            )

        sql = consultas[0]
        self.assertIn("TRY_CONVERT(float, [FLG_CliRef]) IS NULL", sql)
        self.assertIn("NOT IN (N'N', N'R')", sql)          # N y R son validos (se convierten)
        self.assertIn("TRY_CONVERT(int, [Edad]) IS NULL", sql)
        self.assertNotIn("[Nomcliente]", sql)               # texto -> texto: no se revisa
        self.assertNotIn("[PERIODO]", sql)                  # periodo lo pone el cierre
        self.assertEqual(problemas, [{
            "columna_historico": "FLG_CliRef",
            "columna_origen": "FLG_CliRef",
            "tipo_historico": "float",
            "filas": 2,
            "ejemplos": ["X", "Z"],
        }])

    def test_sin_columnas_a_revisar_no_consulta(self):
        with engine_falso({}) as consultas:
            problemas = svc.detectar_valores_no_numericos(
                ORIGEN_INDIVIDUAL, HIST_INDIVIDUAL, [col("Monto", "float")], [col("Monto", "float")], None,
            )
        self.assertEqual((problemas, consultas), ([], []))


class ValidarCierreTests(unittest.TestCase):
    CONFIG = {
        "id_config": 5,
        "cartera": "COMPARTAMOS",
        "producto": "VIGENTE INDIVIDUAL",
        "tabla_destino": ORIGEN_INDIVIDUAL,
        "tabla_historica": HIST_INDIVIDUAL,
        "tipo_estructura_historico": "MISMA_ESTRUCTURA",
        "campo_periodo_historico": "PERIODO",
    }

    def validar(self, problemas):
        columnas = {
            ORIGEN_INDIVIDUAL: [col("FLG_CliRef"), col("Nomcliente")],
            HIST_INDIVIDUAL: [col("FLG_CliRef", "float"), col("Nomcliente"), col("PERIODO")],
        }
        with patch.object(svc, "asegurar_tabla_cierres_historicos"), \
             patch.object(svc, "obtener_configuracion", return_value=dict(self.CONFIG)), \
             patch.object(svc, "obtener_columnas_tabla", side_effect=lambda t: columnas[t]), \
             patch.object(svc, "contar_tabla", return_value=3027), \
             patch.object(svc, "contar_periodo_historico", return_value=0), \
             patch.object(svc, "detectar_valores_no_numericos", return_value=problemas):
            return svc.validar_cierre_historico(5, "202610")

    def test_valores_no_numericos_bloquean_el_cierre_con_mensaje_claro(self):
        resultado = self.validar([{
            "columna_historico": "FLG_CliRef", "columna_origen": "FLG_CliRef",
            "tipo_historico": "float", "filas": 3, "ejemplos": ["X"],
        }])

        self.assertFalse(resultado["puede_cerrar"])
        errores = [a["mensaje"] for a in resultado["alertas"] if a["tipo"] == "error"]
        self.assertEqual(len(errores), 1)
        self.assertIn("FLG_CliRef", errores[0])
        self.assertIn("3 filas", errores[0])
        self.assertIn("'X'", errores[0])

    def test_sin_problemas_el_cierre_puede_ejecutarse(self):
        resultado = self.validar([])
        self.assertTrue(resultado["puede_cerrar"])
        self.assertEqual(resultado["alertas"][-1]["tipo"], "ok")


class CastigoGrupalTests(unittest.TestCase):
    """Castigo Grupal debe cerrar en su propio historico, nunca en el de vigente."""

    CONFIG = {
        "id_config": 7,
        "cartera": "COMPARTAMOS",
        "producto": "CASTIGO GRUPAL",
        "tabla_destino": "Desarrollo.dbo.compartamos_grupal_castigo",
        "tipo_estructura_historico": "MAPEO_HISTORICO",
        "campo_periodo_historico": "Mes Asignacion",
        "tipo_periodo": "DATE",
        "formato_periodo": "YYYY-MM-01",
    }

    def validar(self, tabla_historica):
        config = dict(self.CONFIG, tabla_historica=tabla_historica)
        columnas = {
            config["tabla_destino"]: [col("Operacion")],
            tabla_historica: [col("Operacion"), col("Mes_Asignacion")],
        }
        with patch.object(svc, "asegurar_tabla_cierres_historicos"), \
             patch.object(svc, "obtener_configuracion", return_value=config), \
             patch.object(svc, "obtener_columnas_tabla", side_effect=lambda t: columnas[t]), \
             patch.object(svc, "contar_tabla", return_value=100), \
             patch.object(svc, "contar_periodo_historico", return_value=0) as contar, \
             patch.object(svc, "detectar_valores_no_numericos", return_value=[]) as detectar:
            return svc.validar_cierre_historico(7, "202610"), contar, detectar

    def test_castigo_apuntando_al_historico_de_vigente_se_bloquea_sin_consultarlo(self):
        resultado, contar, detectar = self.validar("Compartamos_Vigente_Cobranzas.dbo.HIST_COMPARTAMOS_GRUPAL")

        self.assertFalse(resultado["puede_cerrar"])
        errores = " ".join(a["mensaje"] for a in resultado["alertas"] if a["tipo"] == "error")
        self.assertIn("CASTIGO GRUPAL", errores)
        self.assertIn("HIST_GRUPAL_CASTIGO", errores)
        contar.assert_not_called()       # no se consulta el historico equivocado
        detectar.assert_not_called()

    def test_castigo_con_su_historico_valida_normal(self):
        resultado, contar, _ = self.validar("Compartamos_Castigo_Cobranzas.dbo.HIST_GRUPAL_CASTIGO")

        self.assertTrue(resultado["puede_cerrar"])
        contar.assert_called_once()

    def test_vigente_no_puede_cerrar_en_un_historico_de_castigo(self):
        alertas = []
        svc.validar_ruta_historica_compartamos(
            "Desarrollo.dbo.compartamos_grupal",
            "Compartamos_Castigo_Cobranzas.dbo.HIST_GRUPAL_CASTIGO",
            alertas,
            producto="VIGENTE GRUPAL",
        )
        self.assertEqual([a["tipo"] for a in alertas], ["error"])

    def test_la_configuracion_ya_no_se_reescribe_desde_python(self):
        sentencias = []

        class Conn:
            def execute(self, query, params=None):
                sentencias.append(str(query))

        @contextmanager
        def begin():
            yield Conn()

        engine = MagicMock()
        engine.begin.side_effect = begin
        with patch.object(svc, "engine_siscob", engine):
            svc.asegurar_configuracion_importacion()

        self.assertEqual(len(sentencias), 1)
        self.assertNotIn("UPDATE", sentencias[0].upper())
        self.assertIn("ADD tabla_actual_es_mensual", sentencias[0])


if __name__ == "__main__":
    unittest.main()
