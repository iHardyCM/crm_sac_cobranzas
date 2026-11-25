# Calibración del score telefónico · 14/11/2026 15:53

Éxito = CEF (titular o tercero con acuerdo) en la semana siguiente al corte, entre los teléfonos marcados.
Entrenamiento: 9 cortes · 650,459 teléfonos.
Prueba (fuera del tiempo de entrenamiento): 2026-10-19, 2026-10-26, 2026-11-02 · 241,275 teléfonos · tasa de CEF 5.81 %.

## ¿Ordena mejor que una regla simple?
AUC dentro de cada cartera (0,5 = azar, 1 = perfecto). Regla simple = primero el que tuvo CEF más reciente.

| | Score | Regla simple |
|---|---:|---:|
| Total | 0.8284 | 0.7702 |
| COMPARTAMOS | 0.7844 | 0.7175 |
| FINANCIERA_OH | 0.8824 | 0.8388 |
| INTERBANK | 0.909 | 0.8499 |
| MIBANCO | 0.7421 | 0.5888 |
| PROPIA | 0.8396 | 0.7761 |

## Tasa de CEF por tramo (prueba)

| Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| A | 77731 | 11356 | 14.61 |
| B | 41737 | 1322 | 3.17 |
| C | 49154 | 929 | 1.89 |
| D | 46850 | 338 | 0.72 |
| E | 25803 | 85 | 0.33 |

Cortes de tramo (score mínimo): A 41 · B 38 · C 35 · D 31

## Tasa de CEF por decil de score (prueba, 1 = mejor)

| Decil | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| 1 | 25666 | 7360 | 28.68 |
| 2 | 26091 | 2566 | 9.83 |
| 3 | 25974 | 1430 | 5.51 |
| 4 | 24060 | 870 | 3.62 |
| 5 | 36142 | 877 | 2.43 |
| 6 | 16583 | 293 | 1.77 |
| 7 | 25946 | 349 | 1.35 |
| 8 | 26177 | 172 | 0.66 |
| 9 | 16195 | 63 | 0.39 |
| 10 | 18441 | 50 | 0.27 |

## Por entidad y tramo (prueba)

| Entidad | Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|---|
| COMPARTAMOS | A | 44230 | 6633 | 15.0 |
| COMPARTAMOS | B | 21714 | 944 | 4.35 |
| COMPARTAMOS | C | 21529 | 571 | 2.65 |
| COMPARTAMOS | D | 22830 | 215 | 0.94 |
| COMPARTAMOS | E | 10865 | 42 | 0.39 |
| FINANCIERA_OH | A | 17625 | 2273 | 12.9 |
| FINANCIERA_OH | B | 9814 | 145 | 1.48 |
| FINANCIERA_OH | C | 16125 | 182 | 1.13 |
| FINANCIERA_OH | D | 14565 | 46 | 0.32 |
| FINANCIERA_OH | E | 8778 | 18 | 0.21 |
| INTERBANK | A | 4869 | 1100 | 22.59 |
| INTERBANK | B | 3346 | 48 | 1.43 |
| INTERBANK | C | 3833 | 57 | 1.49 |
| INTERBANK | D | 3203 | 29 | 0.91 |
| INTERBANK | E | 2159 | 7 | 0.32 |
| MIBANCO | A | 2767 | 167 | 6.04 |
| MIBANCO | B | 2066 | 52 | 2.52 |
| MIBANCO | C | 1656 | 19 | 1.15 |
| MIBANCO | D | 1173 | 16 | 1.36 |
| MIBANCO | E | 883 | 5 | 0.57 |
| PROPIA | A | 8240 | 1183 | 14.36 |
| PROPIA | B | 4797 | 133 | 2.77 |
| PROPIA | C | 6011 | 100 | 1.66 |
| PROPIA | D | 5079 | 32 | 0.63 |
| PROPIA | E | 3118 | 13 | 0.42 |

## Puntos por característica

| Caracteristica | Tramo | Puntos | N | tasa_cef_pct_entrenamiento |
|---|---|---|---|---|
| T_ULT_CEF | 1-7 | 53.63 | 23280 | 40.06 |
| T_ULT_CEF | 31-90 | 11.71 | 25378 | 9.49 |
| T_ULT_CEF | 8-30 | 28.99 | 30299 | 19.76 |
| T_ULT_CEF | SIN_CEF_90 | 0.0 | 571502 | 2.29 |
| T_ULT_TERCERO | 1-30 | 9.59 | 38283 | 11.35 |
| T_ULT_TERCERO | 31-90 | 8.82 | 23495 | 7.78 |
| T_ULT_TERCERO | SIN_TERC_90 | 0.0 | 588681 | 4.19 |
| T_TASA_CEF_90 | 0 | 0.0 | 454902 | 1.82 |
| T_TASA_CEF_90 | 5-15% | 32.48 | 20779 | 25.84 |
| T_TASA_CEF_90 | <5% | 20.79 | 40927 | 13.24 |
| T_TASA_CEF_90 | >=15% | 41.06 | 17251 | 40.2 |
| T_TASA_CEF_90 | SIN_INTENTOS | 10.14 | 116600 | 4.15 |
| T_INTENTOS_30 | 0 | 9.03 | 158418 | 3.49 |
| T_INTENTOS_30 | 1-3 | 12.24 | 89239 | 4.86 |
| T_INTENTOS_30 | 11-30 | 1.95 | 181688 | 4.86 |
| T_INTENTOS_30 | 4-10 | 5.97 | 110653 | 5.17 |
| T_INTENTOS_30 | >30 | 0.0 | 110461 | 5.8 |
| T_ULT_INTENTO | 1-7 | 3.05 | 380934 | 5.71 |
| T_ULT_INTENTO | 31-90 | 0.0 | 41818 | 1.67 |
| T_ULT_INTENTO | 8-30 | 5.57 | 111107 | 3.19 |
| T_ULT_INTENTO | SIN_INT_90 | 13.19 | 116600 | 4.15 |
| T_MAQUINA_90 | APAGADO | 0.0 | 6166 | 2.74 |
| T_MAQUINA_90 | BUZON | 3.66 | 106776 | 2.74 |
| T_MAQUINA_90 | CONTESTA | 22.38 | 25066 | 14.71 |
| T_MAQUINA_90 | SIN_DATO | 9.0 | 330019 | 3.91 |
| T_MAQUINA_90 | TIMBRA | 11.91 | 182432 | 6.1 |
| F_EQUIVOCADO_DNI | NO | 0.0 | 650099 | 4.74 |
| F_EQUIVOCADO_DNI | SI | 12.26 | 360 | 7.22 |
| F_NO_EXISTE | NO | 3.95 | 649812 | 4.74 |
| F_NO_EXISTE | SI | 0.0 | 647 | 8.96 |
| S_ORIGEN | BUSQUEDA | 6.28 | 14072 | 3.79 |
| S_ORIGEN | CLIENTE | 0.0 | 0 |  |
| S_ORIGEN | EMPRESA | 3.38 | 250821 | 5.5 |
| S_ORIGEN | OPERADORA | 0.0 | 339771 | 4.13 |
| S_ORIGEN | OTRO | 4.68 | 45795 | 5.35 |
| S_FUENTE | BASE_INTERNA | 12.64 | 35465 | 0.91 |
| S_FUENTE | ENRIQUECIMIENTO | 9.64 | 1891 | 1.85 |
| S_FUENTE | OTRA | 17.4 | 589037 | 5.12 |
| S_FUENTE | SEARCH | 0.0 | 24066 | 1.19 |
| S_ANTIG_DATO | 1-2A | 0.0 | 48196 | 1.37 |
| S_ANTIG_DATO | 3-5A | 3.6 | 24241 | 1.7 |
| S_ANTIG_DATO | <1A | 1.4 | 38366 | 1.27 |
| S_ANTIG_DATO | >5A | 0.75 | 628 | 3.5 |
| S_ANTIG_DATO | SIN_DATO | 6.67 | 539028 | 5.43 |
| S_OSIPTEL | NO | 0.0 | 255600 | 2.18 |
| S_OSIPTEL | SI | 31.93 | 394624 | 6.37 |
| S_OSIPTEL | SV | 34.13 | 235 | 52.34 |
| S_WHATSAPP | NO | 0.0 | 193978 | 1.94 |
| S_WHATSAPP | SI | 12.56 | 456214 | 5.9 |
| S_WHATSAPP | SV | 27.87 | 267 | 50.56 |
| S_TIMBRA | 0 | 0.0 | 113089 | 2.38 |
| S_TIMBRA | 1 | 6.55 | 47002 | 5.18 |
| S_TIMBRA | 2 | 6.31 | 96574 | 4.63 |
| S_TIMBRA | 3 | 8.61 | 84441 | 5.41 |
| S_TIMBRA | 4 | 8.59 | 309120 | 5.35 |
| S_TIMBRA | SIN_DATO | 13.22 | 233 | 52.79 |
| S_TIPO_LINEA | CONTROL | 18.46 | 127992 | 6.38 |
| S_TIPO_LINEA | NO_INFORMA | 33.14 | 167251 | 3.02 |
| S_TIPO_LINEA | POSTPAGO | 20.03 | 185093 | 7.38 |
| S_TIPO_LINEA | PREPAGO | 0.0 | 170123 | 2.32 |
| S_RELACION | AVAL | 23.11 | 2105 | 2.38 |
| S_RELACION | CONYUGE | 43.65 | 1289 | 2.4 |
| S_RELACION | FAMILIAR | 55.63 | 997 | 5.12 |
| S_RELACION | NO_INFORMA | 41.89 | 638779 | 4.75 |
| S_RELACION | REFERENCIA | 0.0 | 5702 | 0.25 |
| S_RELACION | TITULAR | 72.35 | 1587 | 20.16 |
| S_COMPARTIDO | 1 | 1.61 | 639728 | 4.71 |
| S_COMPARTIDO | 2-4 | 0.0 | 10260 | 5.84 |
| S_COMPARTIDO | 5+ | 34.77 | 471 | 16.56 |

Puntos máximos posibles: 414.13 (= score 100).

Notas:
- El semáforo (S_COLOR) no entra: solo existe su valor de hoy y depende de las llamadas.
- OSIPTEL, WhatsApp y timbrado se usan con su valor de hoy (vienen de validaciones externas).
- La tasa por tramo en entrenamiento es descriptiva; los puntos salen del modelo, que separa el efecto
  de cada característica del de la cartera y de los intentos de esa semana.