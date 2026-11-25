import unittest
from unittest.mock import Mock

from app.services import control_horario_service as control


class PerfilesControlHorarioTests(unittest.TestCase):
    def test_check_incluye_actividad_propia_de_otros_perfiles(self):
        tipos = ["GESTOR", "SUPERVISOR", "JEFE DE CARTERA", "ADMINISTRADOR", "MONITOR DE CALIDAD"]
        mapa = {
            i: {
                "idusuario": i,
                "usuario": str(i),
                "idcartera": 124,
                "cartera": "COMPARTAMOS CASTIGO INDIVIDUAL",
                "tipousuario": tipo,
                "estado": "A",
            }
            for i, tipo in enumerate(tipos, 1)
        }
        rows = [{"IDUSUARIO": i, "IDCARTERA": 124, "PAGO": 10} for i in mapa]

        sin_check = control.enriquecer_por_usuario(rows, mapa, {}, incluir_apoyo_recupero=False)
        con_check = control.enriquecer_por_usuario(rows, mapa, {}, incluir_apoyo_recupero=True)

        self.assertEqual([row["TIPOUSUARIO"] for row in sin_check], ["GESTOR"])
        self.assertEqual([row["TIPOUSUARIO"] for row in con_check], tipos)
        self.assertEqual([row["PAGO"] for row in con_check], [10] * len(tipos))
        self.assertEqual([row["ES_RECUPERO_APOYO"] for row in con_check], [0, 1, 1, 1, 1])

    def test_consultas_complementarias_usan_el_mismo_filtro(self):
        consultas = (
            control.obtener_clientes_unicos_control,
            control.obtener_compromisos_activos_control,
            control.obtener_compromisos_hora_control,
        )
        for consulta in consultas:
            for incluir in (False, True):
                with self.subTest(consulta=consulta.__name__, incluir=incluir):
                    cursor = Mock()
                    cursor.fetchall.return_value = []
                    consulta(cursor, fecha="2026-11-18", incluir_apoyo_recupero=incluir)
                    sql = cursor.execute.call_args.args[0]
                    self.assertIn(control.filtro_perfiles_recupero(incluir), sql)
                    self.assertNotIn(control.filtro_perfiles_recupero(not incluir), sql)

    def test_administrador_sin_cartera_principal_conserva_su_actividad(self):
        cursor = Mock()
        cursor.fetchall.return_value = [(7, "70000007", None, "ADMINISTRADOR", "A")]
        mapa_id, mapa_usuario = control.obtener_mapa_usuarios(cursor)
        self.assertNotIn("WHERE IDCARTERA IS NOT NULL", cursor.execute.call_args.args[0])

        rows = [{"IDUSUARIO": 7, "IDCARTERA": 124, "PAGO": 25}]
        self.assertEqual(control.enriquecer_por_usuario(rows, mapa_id, mapa_usuario), [])
        incluidos = control.enriquecer_por_usuario(rows, mapa_id, mapa_usuario, True)
        self.assertEqual(len(incluidos), 1)
        self.assertEqual(incluidos[0]["PAGO"], 25)
        self.assertIsNone(incluidos[0]["IDCARTERA_USUARIO"])


if __name__ == "__main__":
    unittest.main()
