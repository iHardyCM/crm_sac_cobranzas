# Calibración del score telefónico · 14/11/2026 18:06

Éxito = CEF (titular o tercero con acuerdo) en la semana siguiente al corte, entre los teléfonos marcados.
Entrenamiento: 9 cortes · 634,883 teléfonos.
Prueba (fuera del tiempo de entrenamiento): 2026-10-19, 2026-10-26, 2026-11-02 · 230,836 teléfonos · tasa de CEF 5.78 %.

## ¿Ordena mejor que una regla simple?
AUC dentro de cada cartera (0,5 = azar, 1 = perfecto). Regla simple = primero el que tuvo CEF más reciente.

| | Score | Regla simple |
|---|---:|---:|
| Total | 0.8348 | 0.783 |
| COMPARTAMOS | 0.7922 | 0.7341 |
| FINANCIERA_OH | 0.8846 | 0.8415 |
| INTERBANK | 0.9197 | 0.8845 |
| MIBANCO | 0.7574 | 0.6033 |
| PROPIA | 0.84 | 0.7809 |

## Tasa de CEF por tramo (prueba)

| Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| A | 68298 | 10611 | 15.54 |
| B | 39585 | 1371 | 3.46 |
| C | 50589 | 954 | 1.89 |
| D | 44790 | 327 | 0.73 |
| E | 27574 | 87 | 0.32 |

Cortes de tramo (score mínimo): A 51 · B 47 · C 43 · D 38

## Tasa de CEF por decil de score (prueba, 1 = mejor)

| Decil | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| 1 | 24240 | 7132 | 29.42 |
| 2 | 22948 | 2206 | 9.61 |
| 3 | 30745 | 1723 | 5.6 |
| 4 | 19953 | 624 | 3.13 |
| 5 | 24702 | 649 | 2.63 |
| 6 | 24301 | 439 | 1.81 |
| 7 | 20787 | 275 | 1.32 |
| 8 | 17560 | 140 | 0.8 |
| 9 | 25745 | 108 | 0.42 |
| 10 | 19855 | 54 | 0.27 |

## Por entidad y tramo (prueba)

| Entidad | Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|---|
| COMPARTAMOS | A | 39219 | 6108 | 15.57 |
| COMPARTAMOS | B | 21623 | 975 | 4.51 |
| COMPARTAMOS | C | 22128 | 586 | 2.65 |
| COMPARTAMOS | D | 21889 | 209 | 0.95 |
| COMPARTAMOS | E | 11908 | 43 | 0.36 |
| FINANCIERA_OH | A | 17071 | 2242 | 13.13 |
| FINANCIERA_OH | B | 9926 | 164 | 1.65 |
| FINANCIERA_OH | C | 16437 | 178 | 1.08 |
| FINANCIERA_OH | D | 13959 | 45 | 0.32 |
| FINANCIERA_OH | E | 9471 | 18 | 0.19 |
| INTERBANK | A | 2992 | 983 | 32.85 |
| INTERBANK | B | 1962 | 50 | 2.55 |
| INTERBANK | C | 4143 | 55 | 1.33 |
| INTERBANK | D | 2898 | 26 | 0.9 |
| INTERBANK | E | 1875 | 6 | 0.32 |
| MIBANCO | A | 1343 | 124 | 9.23 |
| MIBANCO | B | 1279 | 51 | 3.99 |
| MIBANCO | C | 1492 | 23 | 1.54 |
| MIBANCO | D | 1083 | 16 | 1.48 |
| MIBANCO | E | 918 | 5 | 0.54 |
| PROPIA | A | 7673 | 1154 | 15.04 |
| PROPIA | B | 4795 | 131 | 2.73 |
| PROPIA | C | 6389 | 112 | 1.75 |
| PROPIA | D | 4961 | 31 | 0.62 |
| PROPIA | E | 3402 | 15 | 0.44 |

## Puntos por característica

| Caracteristica | Tramo | Puntos | N | tasa_cef_pct_entrenamiento | Agrupado |
|---|---|---|---|---|---|
| T_ULT_CEF | 1-7 | 53.78 | 23201 | 39.96 | False |
| T_ULT_CEF | 31-90 | 12.62 | 25376 | 9.49 | False |
| T_ULT_CEF | 8-30 | 29.48 | 30277 | 19.76 | False |
| T_ULT_CEF | SIN_CEF_90 | 0.0 | 556029 | 2.09 | False |
| T_ULT_CEF | * | 0.0 | 0 |  | True |
| T_ULT_TERCERO | 1-30 | 9.56 | 38282 | 11.35 | False |
| T_ULT_TERCERO | 31-90 | 8.77 | 23491 | 7.77 | False |
| T_ULT_TERCERO | SIN_TERC_90 | 0.0 | 573110 | 4.04 | False |
| T_ULT_TERCERO | * | 0.0 | 0 |  | True |
| T_TASA_CEF_90 | 0 | 0.0 | 454729 | 1.82 | False |
| T_TASA_CEF_90 | 5-15% | 32.79 | 20778 | 25.84 | False |
| T_TASA_CEF_90 | <5% | 20.66 | 40919 | 13.23 | False |
| T_TASA_CEF_90 | >=15% | 42.43 | 17157 | 40.09 | False |
| T_TASA_CEF_90 | SIN_INTENTOS | 8.72 | 101300 | 3.34 | False |
| T_TASA_CEF_90 | * | 0.0 | 0 |  | True |
| T_INTENTOS_30 | 0 | 8.99 | 143090 | 2.85 | False |
| T_INTENTOS_30 | 1-3 | 13.48 | 89103 | 4.83 | False |
| T_INTENTOS_30 | 11-30 | 2.06 | 181636 | 4.85 | False |
| T_INTENTOS_30 | 4-10 | 6.59 | 110616 | 5.15 | False |
| T_INTENTOS_30 | >30 | 0.0 | 110438 | 5.8 | False |
| T_INTENTOS_30 | * | 2.06 | 0 |  | True |
| T_ULT_INTENTO | 1-7 | 1.79 | 380770 | 5.69 | False |
| T_ULT_INTENTO | 31-90 | 0.0 | 41790 | 1.67 | False |
| T_ULT_INTENTO | 8-30 | 4.54 | 111023 | 3.19 | False |
| T_ULT_INTENTO | SIN_INT_90 | 10.5 | 101300 | 3.34 | False |
| T_ULT_INTENTO | * | 1.79 | 0 |  | True |
| T_MAQUINA_90 | APAGADO | 0.0 | 6165 | 2.73 | False |
| T_MAQUINA_90 | BUZON | 3.5 | 106749 | 2.74 | False |
| T_MAQUINA_90 | CONTESTA | 22.09 | 25059 | 14.71 | False |
| T_MAQUINA_90 | SIN_DATO | 8.93 | 314518 | 3.62 | False |
| T_MAQUINA_90 | TIMBRA | 11.62 | 182392 | 6.1 | False |
| T_MAQUINA_90 | * | 8.93 | 0 |  | True |
| S_ORIGEN | BUSQUEDA | 0.0 | 13834 | 2.71 | False |
| S_ORIGEN | CLIENTE | 0.13 | 0 |  | True |
| S_ORIGEN | EMPRESA | 3.82 | 243169 | 5.3 | False |
| S_ORIGEN | OPERADORA | 0.13 | 332759 | 4.12 | False |
| S_ORIGEN | OTRO | 4.11 | 45121 | 5.21 | False |
| S_ORIGEN | * | 0.13 | 0 |  | True |
| S_FUENTE | BASE_INTERNA | 8.73 | 33116 | 0.82 | False |
| S_FUENTE | ENRIQUECIMIENTO | 5.07 | 1890 | 1.85 | False |
| S_FUENTE | OTRA | 11.73 | 577128 | 4.98 | False |
| S_FUENTE | SEARCH | 0.0 | 22749 | 1.19 | False |
| S_FUENTE | * | 11.73 | 0 |  | True |
| S_ANTIG_DATO | 1-2A | 0.0 | 46296 | 1.32 | False |
| S_ANTIG_DATO | 3-5A | 3.05 | 23073 | 1.61 | False |
| S_ANTIG_DATO | <1A | 0.62 | 37391 | 1.21 | False |
| S_ANTIG_DATO | >5A | 6.6 | 576 | 2.95 | True |
| S_ANTIG_DATO | SIN_DATO | 6.6 | 527547 | 5.28 | False |
| S_ANTIG_DATO | * | 6.6 | 0 |  | True |
| S_OSIPTEL | NO | 0.0 | 248065 | 2.01 | False |
| S_OSIPTEL | SI | 31.18 | 386801 | 6.28 | False |
| S_OSIPTEL | SV | 31.18 | 17 | 0.0 | True |
| S_OSIPTEL | * | 31.18 | 0 |  | True |
| S_WHATSAPP | NO | 0.0 | 189126 | 1.85 | False |
| S_WHATSAPP | SI | 12.72 | 445715 | 5.79 | False |
| S_WHATSAPP | SV | 12.72 | 42 | 11.9 | True |
| S_WHATSAPP | * | 12.72 | 0 |  | True |
| S_TIMBRA | 0 | 0.0 | 112474 | 2.3 | False |
| S_TIMBRA | 1 | 7.05 | 46556 | 5.13 | False |
| S_TIMBRA | 2 | 6.86 | 94567 | 4.58 | False |
| S_TIMBRA | 3 | 8.85 | 82169 | 5.34 | False |
| S_TIMBRA | 4 | 8.9 | 299100 | 5.22 | False |
| S_TIMBRA | SIN_DATO | 8.9 | 17 | 0.0 | True |
| S_TIMBRA | * | 8.9 | 0 |  | True |
| S_TIPO_LINEA | CONTROL | 18.59 | 124471 | 6.34 | False |
| S_TIPO_LINEA | NO_INFORMA | 31.95 | 161803 | 2.7 | False |
| S_TIPO_LINEA | POSTPAGO | 19.96 | 181959 | 7.31 | False |
| S_TIPO_LINEA | PREPAGO | 0.0 | 166650 | 2.24 | False |
| S_TIPO_LINEA | * | 19.96 | 0 |  | True |
| S_RELACION | AVAL | 24.81 | 2105 | 2.38 | False |
| S_RELACION | CONYUGE | 39.67 | 1280 | 1.95 | False |
| S_RELACION | FAMILIAR | 41.93 | 968 | 3.2 | True |
| S_RELACION | NO_INFORMA | 41.93 | 623412 | 4.65 | False |
| S_RELACION | REFERENCIA | 0.0 | 5701 | 0.25 | False |
| S_RELACION | TITULAR | 53.44 | 1417 | 12.7 | False |
| S_RELACION | * | 41.93 | 0 |  | True |
| S_COMPARTIDO | 1 | 4.02 | 624785 | 4.61 | False |
| S_COMPARTIDO | 2-4 | 0.0 | 9727 | 4.89 | False |
| S_COMPARTIDO | 5+ | 4.02 | 371 | 0.54 | True |
| S_COMPARTIDO | * | 4.02 | 0 |  | True |

Puntos máximos posibles: 316.49 (= score 100).

Notas:
- El semáforo (S_COLOR) no entra: solo existe su valor de hoy y depende de las llamadas.
- Agrupado = tramo con menos de 1,000 teléfonos de entrenamiento: recibe los puntos del de referencia.
- Tramo * = puntos para un valor que aparezca después y que esta versión no conoce.
- OSIPTEL, WhatsApp y timbrado se usan con su valor de hoy (vienen de validaciones externas).
- La tasa por tramo en entrenamiento es descriptiva; los puntos salen del modelo, que separa el efecto
  de cada característica del de la cartera y de los intentos de esa semana.