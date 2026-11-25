# Calibración del score telefónico · 14/11/2026 17:53

Éxito = CEF (titular o tercero con acuerdo) en la semana siguiente al corte, entre los teléfonos marcados.
Entrenamiento: 9 cortes · 634,883 teléfonos.
Prueba (fuera del tiempo de entrenamiento): 2026-10-19, 2026-10-26, 2026-11-02 · 230,836 teléfonos · tasa de CEF 5.78 %.

## ¿Ordena mejor que una regla simple?
AUC dentro de cada cartera (0,5 = azar, 1 = perfecto). Regla simple = primero el que tuvo CEF más reciente.

| | Score | Regla simple |
|---|---:|---:|
| Total | 0.8347 | 0.783 |
| COMPARTAMOS | 0.7921 | 0.7341 |
| FINANCIERA_OH | 0.8846 | 0.8415 |
| INTERBANK | 0.9199 | 0.8845 |
| MIBANCO | 0.7579 | 0.6033 |
| PROPIA | 0.8401 | 0.7809 |

## Tasa de CEF por tramo (prueba)

| Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| A | 67938 | 10593 | 15.59 |
| B | 39236 | 1376 | 3.51 |
| C | 50905 | 964 | 1.89 |
| D | 45006 | 330 | 0.73 |
| E | 27751 | 87 | 0.31 |

Cortes de tramo (score mínimo): A 51 · B 47 · C 43 · D 38

## Tasa de CEF por decil de score (prueba, 1 = mejor)

| Decil | telefonos | cef | tasa_cef_pct |
|---|---|---|---|
| 1 | 24159 | 7111 | 29.43 |
| 2 | 22499 | 2214 | 9.84 |
| 3 | 30566 | 1701 | 5.57 |
| 4 | 19797 | 632 | 3.19 |
| 5 | 24845 | 654 | 2.63 |
| 6 | 24213 | 453 | 1.87 |
| 7 | 21112 | 280 | 1.33 |
| 8 | 29718 | 197 | 0.66 |
| 9 | 13419 | 54 | 0.4 |
| 10 | 20508 | 54 | 0.26 |

## Por entidad y tramo (prueba)

| Entidad | Tramo | telefonos | cef | tasa_cef_pct |
|---|---|---|---|---|
| COMPARTAMOS | A | 39027 | 6095 | 15.62 |
| COMPARTAMOS | B | 21568 | 978 | 4.53 |
| COMPARTAMOS | C | 22211 | 596 | 2.68 |
| COMPARTAMOS | D | 21942 | 209 | 0.95 |
| COMPARTAMOS | E | 12019 | 43 | 0.36 |
| FINANCIERA_OH | A | 16985 | 2240 | 13.19 |
| FINANCIERA_OH | B | 9685 | 163 | 1.68 |
| FINANCIERA_OH | C | 16661 | 179 | 1.07 |
| FINANCIERA_OH | D | 14026 | 47 | 0.34 |
| FINANCIERA_OH | E | 9507 | 18 | 0.19 |
| INTERBANK | A | 2983 | 983 | 32.95 |
| INTERBANK | B | 1955 | 50 | 2.56 |
| INTERBANK | C | 4134 | 55 | 1.33 |
| INTERBANK | D | 2912 | 26 | 0.89 |
| INTERBANK | E | 1886 | 6 | 0.32 |
| MIBANCO | A | 1343 | 124 | 9.23 |
| MIBANCO | B | 1253 | 51 | 4.07 |
| MIBANCO | C | 1504 | 23 | 1.53 |
| MIBANCO | D | 1089 | 16 | 1.47 |
| MIBANCO | E | 926 | 5 | 0.54 |
| PROPIA | A | 7600 | 1151 | 15.14 |
| PROPIA | B | 4775 | 134 | 2.81 |
| PROPIA | C | 6395 | 111 | 1.74 |
| PROPIA | D | 5037 | 32 | 0.64 |
| PROPIA | E | 3413 | 15 | 0.44 |

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
| T_TASA_CEF_90 | >=15% | 42.42 | 17157 | 40.09 | False |
| T_TASA_CEF_90 | SIN_INTENTOS | 8.72 | 101300 | 3.34 | False |
| T_TASA_CEF_90 | * | 0.0 | 0 |  | True |
| T_INTENTOS_30 | 0 | 9.0 | 143090 | 2.85 | False |
| T_INTENTOS_30 | 1-3 | 13.48 | 89103 | 4.83 | False |
| T_INTENTOS_30 | 11-30 | 2.07 | 181636 | 4.85 | False |
| T_INTENTOS_30 | 4-10 | 6.59 | 110616 | 5.15 | False |
| T_INTENTOS_30 | >30 | 0.0 | 110438 | 5.8 | False |
| T_INTENTOS_30 | * | 2.07 | 0 |  | True |
| T_ULT_INTENTO | 1-7 | 1.79 | 380770 | 5.69 | False |
| T_ULT_INTENTO | 31-90 | 0.0 | 41790 | 1.67 | False |
| T_ULT_INTENTO | 8-30 | 4.55 | 111023 | 3.19 | False |
| T_ULT_INTENTO | SIN_INT_90 | 10.51 | 101300 | 3.34 | False |
| T_ULT_INTENTO | * | 1.79 | 0 |  | True |
| T_MAQUINA_90 | APAGADO | 0.0 | 6165 | 2.73 | False |
| T_MAQUINA_90 | BUZON | 3.46 | 106749 | 2.74 | False |
| T_MAQUINA_90 | CONTESTA | 22.06 | 25059 | 14.71 | False |
| T_MAQUINA_90 | SIN_DATO | 8.9 | 314518 | 3.62 | False |
| T_MAQUINA_90 | TIMBRA | 11.59 | 182392 | 6.1 | False |
| T_MAQUINA_90 | * | 8.9 | 0 |  | True |
| S_ORIGEN | BUSQUEDA | 0.0 | 13834 | 2.71 | False |
| S_ORIGEN | CLIENTE | 0.21 | 0 |  | True |
| S_ORIGEN | EMPRESA | 3.9 | 243169 | 5.3 | False |
| S_ORIGEN | OPERADORA | 0.21 | 332759 | 4.12 | False |
| S_ORIGEN | OTRO | 4.16 | 45121 | 5.21 | False |
| S_ORIGEN | * | 0.21 | 0 |  | True |
| S_FUENTE | BASE_INTERNA | 8.7 | 33116 | 0.82 | False |
| S_FUENTE | ENRIQUECIMIENTO | 4.87 | 1890 | 1.85 | False |
| S_FUENTE | OTRA | 11.71 | 577128 | 4.98 | False |
| S_FUENTE | SEARCH | 0.0 | 22749 | 1.19 | False |
| S_FUENTE | * | 11.71 | 0 |  | True |
| S_ANTIG_DATO | 1-2A | 0.0 | 46296 | 1.32 | False |
| S_ANTIG_DATO | 3-5A | 3.05 | 23073 | 1.61 | False |
| S_ANTIG_DATO | <1A | 0.61 | 37391 | 1.21 | False |
| S_ANTIG_DATO | >5A | 6.61 | 576 | 2.95 | True |
| S_ANTIG_DATO | SIN_DATO | 6.61 | 527547 | 5.28 | False |
| S_ANTIG_DATO | * | 6.61 | 0 |  | True |
| S_OSIPTEL | NO | 0.0 | 248065 | 2.01 | False |
| S_OSIPTEL | SI | 31.16 | 386801 | 6.28 | False |
| S_OSIPTEL | SV | 31.16 | 17 | 0.0 | True |
| S_OSIPTEL | * | 31.16 | 0 |  | True |
| S_WHATSAPP | NO | 0.0 | 189126 | 1.85 | False |
| S_WHATSAPP | SI | 12.72 | 445715 | 5.79 | False |
| S_WHATSAPP | SV | 12.72 | 42 | 11.9 | True |
| S_WHATSAPP | * | 12.72 | 0 |  | True |
| S_TIMBRA | 0 | 0.0 | 112474 | 2.3 | False |
| S_TIMBRA | 1 | 7.05 | 46556 | 5.13 | False |
| S_TIMBRA | 2 | 6.87 | 94567 | 4.58 | False |
| S_TIMBRA | 3 | 8.86 | 82169 | 5.34 | False |
| S_TIMBRA | 4 | 8.91 | 299100 | 5.22 | False |
| S_TIMBRA | SIN_DATO | 8.91 | 17 | 0.0 | True |
| S_TIMBRA | * | 8.91 | 0 |  | True |
| S_TIPO_LINEA | CONTROL | 18.6 | 124471 | 6.34 | False |
| S_TIPO_LINEA | NO_INFORMA | 31.95 | 161803 | 2.7 | False |
| S_TIPO_LINEA | POSTPAGO | 19.96 | 181959 | 7.31 | False |
| S_TIPO_LINEA | PREPAGO | 0.0 | 166650 | 2.24 | False |
| S_TIPO_LINEA | * | 19.96 | 0 |  | True |
| S_RELACION | AVAL | 24.48 | 2105 | 2.38 | False |
| S_RELACION | CONYUGE | 39.24 | 1280 | 1.95 | False |
| S_RELACION | FAMILIAR | 41.51 | 968 | 3.2 | True |
| S_RELACION | NO_INFORMA | 41.51 | 623412 | 4.65 | False |
| S_RELACION | REFERENCIA | 0.0 | 5701 | 0.25 | False |
| S_RELACION | TITULAR | 53.16 | 1417 | 12.7 | False |
| S_RELACION | * | 41.51 | 0 |  | True |
| S_COMPARTIDO | 1 | 4.05 | 624785 | 4.61 | False |
| S_COMPARTIDO | 2-4 | 0.0 | 9727 | 4.89 | False |
| S_COMPARTIDO | 5+ | 4.05 | 371 | 0.54 | True |
| S_COMPARTIDO | * | 4.05 | 0 |  | True |

Puntos máximos posibles: 316.24 (= score 100).

Notas:
- El semáforo (S_COLOR) no entra: solo existe su valor de hoy y depende de las llamadas.
- Agrupado = tramo con menos de 1,000 teléfonos de entrenamiento: recibe los puntos del de referencia.
- Tramo * = puntos para un valor que aparezca después y que esta versión no conoce.
- OSIPTEL, WhatsApp y timbrado se usan con su valor de hoy (vienen de validaciones externas).
- La tasa por tramo en entrenamiento es descriptiva; los puntos salen del modelo, que separa el efecto
  de cada característica del de la cartera y de los intentos de esa semana.