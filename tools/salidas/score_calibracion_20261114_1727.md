# Calibración del score telefónico · 14/11/2026 17:27

Éxito = CEF (titular o tercero con acuerdo) en la semana siguiente al corte, entre los teléfonos marcados.
Entrenamiento: 9 cortes · 650,459 teléfonos.
Prueba (fuera del tiempo de entrenamiento): 2026-10-19, 2026-10-26, 2026-11-02 · 241,275 teléfonos · tasa de CEF 5.81 %.

## ¿Ordena mejor que una regla simple?
AUC dentro de cada cartera (0,5 = azar, 1 = perfecto). Regla simple = primero el que tuvo CEF más reciente.

| | Score | Regla simple |
|---|---:|---:|
| Total | 0.829 | 0.7702 |
| COMPARTAMOS | 0.7846 | 0.7175 |
| FINANCIERA_OH | 0.8838 | 0.8388 |
| INTERBANK | 0.9105 | 0.8499 |
| MIBANCO | 0.744 | 0.5888 |
| PROPIA | 0.8393 | 0.7761 |

## Tasa de CEF por tramo (prueba)

| Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| A | 70250 | 11005 | 15.67 |
| B | 43111 | 1518 | 3.52 |
| C | 55852 | 1089 | 1.95 |
| D | 48395 | 346 | 0.71 |
| E | 23667 | 72 | 0.3 |

Cortes de tramo (score mínimo): A 49 · B 45 · C 41 · D 36

## Tasa de CEF por decil de score (prueba, 1 = mejor)

| Decil | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| 1 | 24200 | 7143 | 29.52 |
| 2 | 26446 | 2708 | 10.24 |
| 3 | 28403 | 1574 | 5.54 |
| 4 | 20642 | 764 | 3.7 |
| 5 | 28840 | 719 | 2.49 |
| 6 | 30171 | 549 | 1.82 |
| 7 | 10511 | 155 | 1.47 |
| 8 | 31108 | 279 | 0.9 |
| 9 | 17287 | 67 | 0.39 |
| 10 | 23667 | 72 | 0.3 |

## Por entidad y tramo (prueba)

| Entidad | Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|---|
| COMPARTAMOS | A | 40319 | 6395 | 15.86 |
| COMPARTAMOS | B | 22598 | 1062 | 4.7 |
| COMPARTAMOS | C | 24857 | 691 | 2.78 |
| COMPARTAMOS | D | 23679 | 224 | 0.95 |
| COMPARTAMOS | E | 9715 | 33 | 0.34 |
| FINANCIERA_OH | A | 16061 | 2221 | 13.83 |
| FINANCIERA_OH | B | 10330 | 186 | 1.8 |
| FINANCIERA_OH | C | 17374 | 198 | 1.14 |
| FINANCIERA_OH | D | 14844 | 44 | 0.3 |
| FINANCIERA_OH | E | 8298 | 15 | 0.18 |
| INTERBANK | A | 4204 | 1080 | 25.69 |
| INTERBANK | B | 3246 | 63 | 1.94 |
| INTERBANK | C | 4625 | 62 | 1.34 |
| INTERBANK | D | 3475 | 29 | 0.83 |
| INTERBANK | E | 1860 | 7 | 0.38 |
| MIBANCO | A | 2326 | 159 | 6.84 |
| MIBANCO | B | 1972 | 56 | 2.84 |
| MIBANCO | C | 2216 | 22 | 0.99 |
| MIBANCO | D | 1175 | 17 | 1.45 |
| MIBANCO | E | 856 | 5 | 0.58 |
| PROPIA | A | 7340 | 1150 | 15.67 |
| PROPIA | B | 4965 | 151 | 3.04 |
| PROPIA | C | 6780 | 116 | 1.71 |
| PROPIA | D | 5222 | 32 | 0.61 |
| PROPIA | E | 2938 | 12 | 0.41 |

## Puntos por característica

| Caracteristica | Tramo | Puntos | N | tasa_cef_pct_entrenamiento | Agrupado |
|---|---|---|---|---|---|
| T_ULT_CEF | 1-7 | 53.64 | 23280 | 40.06 | False |
| T_ULT_CEF | 31-90 | 11.68 | 25378 | 9.49 | False |
| T_ULT_CEF | 8-30 | 28.96 | 30299 | 19.76 | False |
| T_ULT_CEF | SIN_CEF_90 | 0.0 | 571502 | 2.29 | False |
| T_ULT_CEF | * | 0.0 | 0 |  | True |
| T_ULT_TERCERO | 1-30 | 9.61 | 38283 | 11.35 | False |
| T_ULT_TERCERO | 31-90 | 8.83 | 23495 | 7.78 | False |
| T_ULT_TERCERO | SIN_TERC_90 | 0.0 | 588681 | 4.19 | False |
| T_ULT_TERCERO | * | 0.0 | 0 |  | True |
| T_TASA_CEF_90 | 0 | 0.0 | 454902 | 1.82 | False |
| T_TASA_CEF_90 | 5-15% | 32.43 | 20779 | 25.84 | False |
| T_TASA_CEF_90 | <5% | 20.75 | 40927 | 13.24 | False |
| T_TASA_CEF_90 | >=15% | 41.1 | 17251 | 40.2 | False |
| T_TASA_CEF_90 | SIN_INTENTOS | 10.16 | 116600 | 4.15 | False |
| T_TASA_CEF_90 | * | 0.0 | 0 |  | True |
| T_INTENTOS_30 | 0 | 9.02 | 158418 | 3.49 | False |
| T_INTENTOS_30 | 1-3 | 12.21 | 89239 | 4.86 | False |
| T_INTENTOS_30 | 11-30 | 1.94 | 181688 | 4.86 | False |
| T_INTENTOS_30 | 4-10 | 5.94 | 110653 | 5.17 | False |
| T_INTENTOS_30 | >30 | 0.0 | 110461 | 5.8 | False |
| T_INTENTOS_30 | * | 1.94 | 0 |  | True |
| T_ULT_INTENTO | 1-7 | 3.08 | 380934 | 5.71 | False |
| T_ULT_INTENTO | 31-90 | 0.0 | 41818 | 1.67 | False |
| T_ULT_INTENTO | 8-30 | 5.59 | 111107 | 3.19 | False |
| T_ULT_INTENTO | SIN_INT_90 | 13.24 | 116600 | 4.15 | False |
| T_ULT_INTENTO | * | 3.08 | 0 |  | True |
| T_MAQUINA_90 | APAGADO | 0.0 | 6166 | 2.74 | False |
| T_MAQUINA_90 | BUZON | 3.62 | 106776 | 2.74 | False |
| T_MAQUINA_90 | CONTESTA | 22.38 | 25066 | 14.71 | False |
| T_MAQUINA_90 | SIN_DATO | 9.04 | 330019 | 3.91 | False |
| T_MAQUINA_90 | TIMBRA | 11.89 | 182432 | 6.1 | False |
| T_MAQUINA_90 | * | 9.04 | 0 |  | True |
| S_ORIGEN | BUSQUEDA | 6.88 | 14072 | 3.79 | False |
| S_ORIGEN | CLIENTE | 0.0 | 0 |  | True |
| S_ORIGEN | EMPRESA | 3.34 | 250821 | 5.5 | False |
| S_ORIGEN | OPERADORA | 0.0 | 339771 | 4.13 | False |
| S_ORIGEN | OTRO | 4.85 | 45795 | 5.35 | False |
| S_ORIGEN | * | 0.0 | 0 |  | True |
| S_FUENTE | BASE_INTERNA | 14.03 | 35465 | 0.91 | False |
| S_FUENTE | ENRIQUECIMIENTO | 9.11 | 1891 | 1.85 | False |
| S_FUENTE | OTRA | 17.45 | 589037 | 5.12 | False |
| S_FUENTE | SEARCH | 0.0 | 24066 | 1.19 | False |
| S_FUENTE | * | 17.45 | 0 |  | True |
| S_ANTIG_DATO | 1-2A | 0.0 | 48196 | 1.37 | False |
| S_ANTIG_DATO | 3-5A | 3.69 | 24241 | 1.7 | False |
| S_ANTIG_DATO | <1A | 1.6 | 38366 | 1.27 | False |
| S_ANTIG_DATO | >5A | 6.34 | 628 | 3.5 | True |
| S_ANTIG_DATO | SIN_DATO | 6.34 | 539028 | 5.43 | False |
| S_ANTIG_DATO | * | 6.34 | 0 |  | True |
| S_OSIPTEL | NO | 0.0 | 255600 | 2.18 | False |
| S_OSIPTEL | SI | 33.96 | 394624 | 6.37 | False |
| S_OSIPTEL | SV | 33.96 | 235 | 52.34 | True |
| S_OSIPTEL | * | 33.96 | 0 |  | True |
| S_WHATSAPP | NO | 0.0 | 193983 | 1.94 | False |
| S_WHATSAPP | SI | 12.58 | 456218 | 5.9 | False |
| S_WHATSAPP | SV | 12.58 | 258 | 51.16 | True |
| S_WHATSAPP | * | 12.58 | 0 |  | True |
| S_TIMBRA | 0 | 0.0 | 113090 | 2.38 | False |
| S_TIMBRA | 1 | 6.44 | 47002 | 5.18 | False |
| S_TIMBRA | 2 | 6.24 | 96578 | 4.63 | False |
| S_TIMBRA | 3 | 8.53 | 84441 | 5.41 | False |
| S_TIMBRA | 4 | 8.58 | 309124 | 5.35 | False |
| S_TIMBRA | SIN_DATO | 8.58 | 224 | 53.57 | True |
| S_TIMBRA | * | 8.58 | 0 |  | True |
| S_TIPO_LINEA | CONTROL | 18.42 | 127992 | 6.38 | False |
| S_TIPO_LINEA | NO_INFORMA | 35.36 | 167251 | 3.02 | False |
| S_TIPO_LINEA | POSTPAGO | 20.04 | 185093 | 7.38 | False |
| S_TIPO_LINEA | PREPAGO | 0.0 | 170123 | 2.32 | False |
| S_TIPO_LINEA | * | 20.04 | 0 |  | True |
| S_RELACION | AVAL | 21.63 | 2105 | 2.38 | False |
| S_RELACION | CONYUGE | 42.91 | 1289 | 2.4 | False |
| S_RELACION | FAMILIAR | 41.82 | 997 | 5.12 | True |
| S_RELACION | NO_INFORMA | 41.82 | 638779 | 4.75 | False |
| S_RELACION | REFERENCIA | 0.0 | 5702 | 0.25 | False |
| S_RELACION | TITULAR | 72.32 | 1587 | 20.16 | False |
| S_RELACION | * | 41.82 | 0 |  | True |
| S_COMPARTIDO | 1 | 1.72 | 639728 | 4.71 | False |
| S_COMPARTIDO | 2-4 | 0.0 | 10260 | 5.84 | False |
| S_COMPARTIDO | 5+ | 1.72 | 471 | 16.56 | True |
| S_COMPARTIDO | * | 1.72 | 0 |  | True |

Puntos máximos posibles: 347.37 (= score 100).

Notas:
- El semáforo (S_COLOR) no entra: solo existe su valor de hoy y depende de las llamadas.
- Agrupado = tramo con menos de 1,000 teléfonos de entrenamiento: recibe los puntos del de referencia.
- Tramo * = puntos para un valor que aparezca después y que esta versión no conoce.
- OSIPTEL, WhatsApp y timbrado se usan con su valor de hoy (vienen de validaciones externas).
- La tasa por tramo en entrenamiento es descriptiva; los puntos salen del modelo, que separa el efecto
  de cada característica del de la cartera y de los intentos de esa semana.