"""Operaciones que compartamos_grupal reconoce como grupales aunque SAC traiga CodigoGrupo 0.

Caso real: DNI 32130767 (grupal + CCM vigentes). SAC: CodigoGrupo 0, CodCreGrupal 20714247.
compartamos_grupal: CodigoGrupo 169336, CodCreGrupal 20714247, Operacion 20714253.
No consulta la base de datos: las lecturas se reemplazan por datos de prueba.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import cliente_crm_service as crm  # noqa: E402

GRUPAL_SAC = {"DNI": "32130767", "CodOperacion": "0000000000020714253", "CodigoGrupo": 0.0, "CodCreGrupal": 20714247.0,
              "NombreGrupo": None, "Linea_Negocio": "GRUPAL", "DiasAtraso": 40, "Deuda_Total": 900}
CCM_SAC = {"DNI": "32130767", "CodOperacion": "0000000000020829127", "CodigoGrupo": 0.0, "CodCreGrupal": 0.0,
           "NombreGrupo": None, "Linea_Negocio": "INDIVIDUAL", "DiasAtraso": 10, "Deuda_Total": 500}
OTRO_SAC = {"DNI": "11111111", "CodOperacion": "0000000000020000001", "CodigoGrupo": 169336.0, "CodCreGrupal": 20714247.0,
            "NombreGrupo": "VIRGEN DEL FATIMA DE COMPARTAM", "Linea_Negocio": "GRUPAL", "DiasAtraso": 5, "Deuda_Total": 300}
ASIG = {"dni": "32130767", "operacion": "20714253", "codigo_grupo": 169336, "credito_grupal": 20714247,
        "nombre_grupo": "VIRGEN DEL FATIMA DE COMPARTAM"}


def filas(*items):
    return [dict(item) for item in items]


class GrupoDesdeAsignacionTest(unittest.TestCase):
    def test_completa_el_grupo_de_la_operacion_grupal_y_no_toca_la_ccm(self):
        data = filas(GRUPAL_SAC, CCM_SAC)
        with mock.patch.object(crm, "consultar_asignacion_grupal", return_value=[ASIG]):
            salida = crm.incorporar_asignacion_grupal(None, data, "32130767")
        grupal, ccm = salida
        self.assertEqual(grupal["CodigoGrupo"], "169336")
        self.assertEqual(grupal["NombreGrupo"], "VIRGEN DEL FATIMA DE COMPARTAM")
        self.assertTrue(grupal[crm.MARCA_GRUPO_ASIGNACION])
        self.assertEqual(ccm["CodigoGrupo"], 0.0)
        self.assertNotIn(crm.MARCA_GRUPO_ASIGNACION, ccm)
        self.assertEqual(crm.operaciones_grupo_por_asignacion(salida), ["0000000000020714253"])
        self.assertEqual(crm.construir_contexto_grupo(salida)["codigo_grupo"], "169336")

    def test_no_pisa_un_codigo_de_grupo_valido_de_sac(self):
        data = filas(OTRO_SAC)
        asig = {"dni": "11111111", "operacion": "20000001", "codigo_grupo": 999999, "credito_grupal": 1, "nombre_grupo": "OTRO"}
        with mock.patch.object(crm, "consultar_asignacion_grupal", return_value=[asig]):
            salida = crm.incorporar_asignacion_grupal(None, data, "11111111")
        self.assertEqual(salida[0]["CodigoGrupo"], 169336.0)
        self.assertNotIn(crm.MARCA_GRUPO_ASIGNACION, salida[0])

    def test_al_buscar_el_grupo_agrega_al_integrante_que_sac_no_asocia(self):
        data = filas(OTRO_SAC)
        faltante = dict(GRUPAL_SAC)
        with mock.patch.object(crm, "consultar_asignacion_grupal", return_value=[ASIG]), \
                mock.patch.object(crm, "consultar_filas_vista_por_operacion", return_value=[faltante]) as vista:
            salida = crm.incorporar_asignacion_grupal(None, data, "169336")
        self.assertEqual([f["DNI"] for f in salida], ["32130767", "11111111"])  # mayor mora primero
        self.assertEqual(salida[0]["CodigoGrupo"], "169336")
        self.assertTrue(salida[0][crm.MARCA_GRUPO_ASIGNACION])
        self.assertEqual(vista.call_args[0][1][0]["dni"], "32130767")

    def test_ceros_a_la_izquierda_no_duplican_al_integrante(self):
        data = filas(GRUPAL_SAC, OTRO_SAC)
        asig = dict(ASIG, dni="032130767", operacion="0020714253")
        with mock.patch.object(crm, "consultar_asignacion_grupal", return_value=[asig]), \
                mock.patch.object(crm, "consultar_filas_vista_por_operacion") as vista:
            salida = crm.incorporar_asignacion_grupal(None, data, "169336")
        vista.assert_not_called()
        self.assertEqual(len(salida), 2)

    def test_si_falla_compartamos_grupal_devuelve_las_filas_como_estaban(self):
        data = filas(GRUPAL_SAC)
        with mock.patch.object(crm, "consultar_asignacion_grupal", side_effect=RuntimeError("sin acceso")):
            salida = crm.incorporar_asignacion_grupal(None, data, "32130767")
        self.assertEqual(salida, data)
        self.assertEqual(salida[0]["CodigoGrupo"], 0.0)

    def test_busqueda_no_numerica_sin_filas_no_consulta_nada(self):
        with mock.patch.object(crm, "consultar_asignacion_grupal", return_value=[]) as consulta:
            self.assertEqual(crm.incorporar_asignacion_grupal(None, [], "ABC"), [])
        consulta.assert_called_once_with([], None)

    def test_cronograma_busca_tambien_por_operacion(self):
        capturado = {}

        class Conexion:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, query, params):
                capturado["sql"], capturado["params"] = str(query), params
                return mock.Mock(mappings=lambda: mock.Mock(all=lambda: []))

        with mock.patch.object(crm.engine_siscob, "connect", return_value=Conexion()):
            crm.consultar_cronograma_grupo(["169336"], ["0000000000020714253"])
        self.assertIn("S.[CodigoGrupo ] IN (:grupo_0)", capturado["sql"])
        self.assertIn("OR S.[Cod Operación] IN (:op_0)", capturado["sql"])
        self.assertEqual(capturado["params"], {"grupo_0": "169336", "op_0": "0000000000020714253"})

    def test_cronograma_solo_por_operacion_si_no_hay_codigo_de_grupo(self):
        self.assertEqual(crm.consultar_cronograma_grupo([], []), [])


if __name__ == "__main__":
    unittest.main()
