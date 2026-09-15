"""Preproceso del audio antes de transcribir: recorte del timbrado inicial.

PROBLEMA QUE RESUELVE
En muchas llamadas el timbrado previo a la conexion queda grabado. El
transcriptor trabaja con dos cupos de hablante y ese tramo puede consumir
uno, dejando toda la conversacion real en el cupo restante. Ese es el origen
del caso en que la transcripcion salio 28 segmentos AGENTE / 2 CLIENTE.

COMO SE DISTINGUE EL TIMBRADO DE LA VOZ
Medido sobre llamadas reales, el tono de timbrado tiene tres marcas que la
voz no tiene:
  - toda su energia en una sola frecuencia (pureza espectral 0.96 a 0.99;
    la voz, incluso en su vocal mas limpia, rara vez pasa de 0.85);
  - esa frecuencia es EXACTAMENTE la misma marco tras marco (453.1 Hz
    repetido), mientras en la voz el pico salta en cada marco;
  - nivel constante.
Por eso no basta con "hay un pico espectral": se exige pureza alta Y
frecuencia sostenida durante varios marcos seguidos. Un detector que solo
mire el pico marca como tono la voz entera.

CRITERIO CONSERVADOR
El tramo recortado es el grupo de tonos del ARRANQUE de la grabacion. Un
tono que aparece mas tarde no es timbrado (puede ser un IVR, un pitido o
musica en espera) y no se toca. Si el archivo no es WAV PCM legible, si no
hay evidencia suficiente o si el recorte resultara desproporcionado, se
devuelve el audio original intacto. Ante la duda, no se modifica el audio.

DEPENDENCIAS
Solo biblioteca estandar. La FFT va implementada aqui: no requiere numpy,
scipy, librosa ni ffmpeg en el servidor. Formatos que no sean WAV PCM 16
bits (por ejemplo GSM 6.10) no se procesan.

TIMESTAMPS
El recorte desplaza el tiempo del audio que se envia a transcribir. Quien
use este modulo debe sumar `segundos_descartados` a los tiempos devueltos
por el transcriptor, para que la evidencia siga apuntando al minuto real
del audio que escucha el usuario.
"""

from __future__ import annotations

import array
import cmath
import math
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4


# --- Parametros del analisis -------------------------------------------------

TASA_ANALISIS_HZ = 4000          # se submuestrea a 4 kHz: cubre hasta 2 kHz
VENTANA_MUESTRAS = 512           # 128 ms a 4 kHz; resolucion ~7.8 Hz
HOP_SEGUNDOS = 0.125
ANALISIS_MAXIMO_SEGUNDOS = 120.0 # solo se inspecciona el arranque de la llamada

BANDA_ANALISIS_MIN_HZ = 90.0     # el pico se busca en todo el rango util, no
BANDA_ANALISIS_MAX_HZ = 1900.0   # solo en la banda del tono: si la voz domina
                                 # en 120 Hz, el pico debe salir en 120 Hz

BANDA_TONO_MIN_HZ = 300.0        # banda donde vive el tono de timbrado
BANDA_TONO_MAX_HZ = 1200.0

# --- Parametros de decision (calibrados contra llamadas reales) --------------

UMBRAL_AUDIBLE_DBFS = -45.0      # por debajo es silencio de linea
PUREZA_TONO = 0.90               # tono medido 0.96-0.99; voz por debajo de 0.85
TOLERANCIA_FRECUENCIA_HZ = 12.0  # el tono repite la misma frecuencia exacta
MARCOS_SOSTENIDOS_MINIMOS = 3    # ~0.4 s de tono continuo para llamarlo tono
MARCOS_TONALES_MINIMOS = 6       # ~0.8 s de tono acumulado en el grupo inicial

INICIO_MAXIMO_TIMBRADO_SEGUNDOS = 10.0  # el timbrado arranca al principio
SALTO_MAXIMO_ENTRE_TONOS_SEGUNDOS = 8.0 # cadencia ~1 s activo / ~4 s en
                                        # silencio; un hueco mayor = ya conecto

RECORTE_MINIMO_SEGUNDOS = 3.0    # por debajo no vale la pena tocar el archivo
RECORTE_MAXIMO_SEGUNDOS = 90.0   # tope duro de seguridad
RECORTE_MAXIMO_PROPORCION = 0.60 # una llamada corta puede ser mayormente
                                 # timbrado, pero no mas de esto


# --- Lectura del audio -------------------------------------------------------

def _leer_wav_mono(ruta: Path) -> Optional[Tuple[array.array, int]]:
    """Devuelve (muestras mono, tasa) o None si no es WAV PCM 16 bits.

    No se intenta convertir otros formatos: si el archivo no es legible con
    la biblioteca estandar, el preproceso se omite y el audio va tal cual.
    """
    try:
        with wave.open(str(ruta), "rb") as wf:
            if wf.getcomptype() != "NONE" or wf.getsampwidth() != 2:
                return None
            canales = wf.getnchannels()
            tasa = wf.getframerate()
            n_frames = wf.getnframes()
            if tasa <= 0 or n_frames <= 0 or canales <= 0:
                return None
            crudo = wf.readframes(min(n_frames, int(tasa * ANALISIS_MAXIMO_SEGUNDOS)))
    except Exception:
        return None

    muestras = array.array("h")
    try:
        muestras.frombytes(crudo[: (len(crudo) // (2 * canales)) * 2 * canales])
    except Exception:
        return None
    if not muestras:
        return None

    if canales > 1:
        mezcla = array.array("h", bytes(2 * (len(muestras) // canales)))
        for i in range(len(mezcla)):
            base = i * canales
            mezcla[i] = int(sum(muestras[base : base + canales]) / canales)
        muestras = mezcla

    return muestras, tasa


def _submuestrear(muestras: array.array, tasa: int) -> Tuple[List[float], int]:
    """Baja la tasa a ~4 kHz promediando bloques."""
    factor = max(1, int(tasa // TASA_ANALISIS_HZ))
    if factor == 1:
        return [float(v) for v in muestras], tasa
    total = (len(muestras) // factor) * factor
    return [sum(muestras[i : i + factor]) / factor for i in range(0, total, factor)], tasa // factor


# --- FFT (radix-2, biblioteca estandar) --------------------------------------

_TWIDDLE: Dict[int, List[complex]] = {}
_HANN: Dict[int, List[float]] = {}


def _ventana_hann(n: int) -> List[float]:
    if n not in _HANN:
        _HANN[n] = [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]
    return _HANN[n]


def _fft(x: List[complex]) -> List[complex]:
    n = len(x)
    x = list(x)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            x[i], x[j] = x[j], x[i]
    largo = 2
    while largo <= n:
        if largo not in _TWIDDLE:
            _TWIDDLE[largo] = [cmath.exp(-2j * math.pi * k / largo) for k in range(largo // 2)]
        tw = _TWIDDLE[largo]
        mitad = largo // 2
        for i in range(0, n, largo):
            for k in range(mitad):
                u = x[i + k]
                v = x[i + k + mitad] * tw[k]
                x[i + k] = u + v
                x[i + k + mitad] = u - v
        largo <<= 1
    return x


def _perfilar_marcos(senal: List[float], tasa: int) -> List[Tuple[float, float, float, float]]:
    """Devuelve (tiempo, nivel_dbfs, frecuencia_pico_hz, pureza) por marco.

    `pureza` es la fraccion de la energia del espectro concentrada en el pico
    y sus dos bins vecinos (la fuga de la ventana de Hann reparte el tono en
    tres bins). Un tono puro queda cerca de 1.0; la voz, muy por debajo.
    """
    n = VENTANA_MUESTRAS
    ventana = _ventana_hann(n)
    hop = max(1, int(tasa * HOP_SEGUNDOS))
    bin_min = max(1, int(BANDA_ANALISIS_MIN_HZ * n / tasa))
    bin_max = min(n // 2 - 1, int(BANDA_ANALISIS_MAX_HZ * n / tasa))

    perfil: List[Tuple[float, float, float, float]] = []
    for pos in range(0, len(senal) - n + 1, hop):
        tiempo = pos / float(tasa)
        segmento = senal[pos : pos + n]
        media = sum(segmento) / n
        muestras = [(segmento[i] - media) * ventana[i] for i in range(n)]

        energia = sum(v * v for v in muestras)
        if energia <= 0:
            perfil.append((tiempo, -120.0, 0.0, 0.0))
            continue
        nivel = 20.0 * math.log10(max(math.sqrt(energia / n), 1e-9) / 32768.0)

        espectro = _fft([complex(v, 0.0) for v in muestras])
        potencias = [abs(espectro[k]) ** 2 for k in range(bin_min, bin_max + 1)]
        total = sum(potencias)
        if total <= 0:
            perfil.append((tiempo, nivel, 0.0, 0.0))
            continue

        k_pico = max(range(len(potencias)), key=lambda k: potencias[k])
        lo = max(0, k_pico - 1)
        hi = min(len(potencias) - 1, k_pico + 1)
        pureza = sum(potencias[lo : hi + 1]) / total
        frecuencia = (bin_min + k_pico) * tasa / float(n)
        perfil.append((tiempo, nivel, frecuencia, pureza))
    return perfil


# --- Deteccion ---------------------------------------------------------------

def _rachas_de_tono(perfil) -> List[Tuple[float, float, float]]:
    """Agrupa marcos en rachas de tono sostenido.

    Devuelve (inicio, fin, frecuencia) por racha. Una racha exige pureza alta
    Y la misma frecuencia durante varios marcos seguidos: eso es lo que
    separa el timbrado de una vocal con armonico fuerte.
    """
    rachas: List[Tuple[float, float, float]] = []
    actual: List[Tuple[float, float]] = []  # (tiempo, frecuencia)

    def cerrar():
        if len(actual) >= MARCOS_SOSTENIDOS_MINIMOS:
            frecuencias = sorted(f for _, f in actual)
            rachas.append((
                actual[0][0],
                actual[-1][0] + HOP_SEGUNDOS,
                frecuencias[len(frecuencias) // 2],
            ))
        actual.clear()

    for tiempo, nivel, frecuencia, pureza in perfil:
        es_tono = (
            nivel > UMBRAL_AUDIBLE_DBFS
            and pureza >= PUREZA_TONO
            and BANDA_TONO_MIN_HZ <= frecuencia <= BANDA_TONO_MAX_HZ
        )
        if es_tono and (not actual or abs(frecuencia - actual[-1][1]) <= TOLERANCIA_FRECUENCIA_HZ):
            actual.append((tiempo, frecuencia))
        else:
            cerrar()
            if es_tono:
                actual.append((tiempo, frecuencia))
    cerrar()
    return rachas


def detectar_inicio_conversacion(ruta_audio: str) -> Dict:
    """Detecta donde termina el timbrado. Nunca lanza.

    Claves devueltas:
      aplicable            bool  el archivo se pudo analizar
      hay_timbrado         bool  hay evidencia de tono de timbrado inicial
      segundos_descartados float fin del timbrado
      marcos_tonales       int   marcos de tono del grupo inicial
      frecuencia_tono_hz   float frecuencia del tono
      motivo               str   explicacion legible
    """
    base = {
        "aplicable": False,
        "hay_timbrado": False,
        "segundos_descartados": 0.0,
        "marcos_tonales": 0,
        "frecuencia_tono_hz": 0.0,
        "motivo": "",
    }

    try:
        ruta = Path(ruta_audio)
        if not ruta.exists():
            base["motivo"] = "No se encontro el archivo de audio."
            return base

        leido = _leer_wav_mono(ruta)
        if leido is None:
            base["motivo"] = "El formato no es WAV PCM 16 bits; no se preprocesa."
            return base

        muestras, tasa_original = leido
        senal, tasa = _submuestrear(muestras, tasa_original)
        if tasa <= 0 or len(senal) < VENTANA_MUESTRAS:
            base["motivo"] = "Audio demasiado corto o ilegible."
            return base

        base["aplicable"] = True

        rachas = _rachas_de_tono(_perfilar_marcos(senal, tasa))
        if not rachas:
            base["motivo"] = "No hay tono sostenido; el audio no se modifica."
            return base

        # El timbrado es lo PRIMERO de la grabacion. Un tono posterior es otra
        # cosa (IVR, pitido, musica) y no se toca.
        if rachas[0][0] > INICIO_MAXIMO_TIMBRADO_SEGUNDOS:
            base["motivo"] = (
                f"Hay tono sostenido pero recien desde {rachas[0][0]:.1f}s; "
                "no es timbrado de conexion y el audio no se modifica."
            )
            return base

        # Grupo inicial: se extiende mientras el hueco al siguiente tono sea
        # compatible con la cadencia del timbrado.
        grupo = [rachas[0]]
        for racha in rachas[1:]:
            if racha[0] - grupo[-1][1] > SALTO_MAXIMO_ENTRE_TONOS_SEGUNDOS:
                break
            grupo.append(racha)

        marcos = sum(int(round((fin - ini) / HOP_SEGUNDOS)) for ini, fin, _ in grupo)
        if marcos < MARCOS_TONALES_MINIMOS:
            base["marcos_tonales"] = marcos
            base["motivo"] = (
                f"Solo {marcos} marcos de tono al inicio; evidencia insuficiente, "
                "el audio no se modifica."
            )
            return base

        frecuencias = sorted(f for _, _, f in grupo)
        fin_timbrado = grupo[-1][1]

        base["hay_timbrado"] = True
        base["marcos_tonales"] = marcos
        base["frecuencia_tono_hz"] = round(frecuencias[len(frecuencias) // 2], 1)
        base["segundos_descartados"] = round(fin_timbrado, 2)
        base["motivo"] = (
            f"Timbrado detectado: {len(grupo)} rafagas de tono a "
            f"{base['frecuencia_tono_hz']} Hz entre {grupo[0][0]:.1f}s y "
            f"{fin_timbrado:.1f}s."
        )
        return base
    except Exception as exc:  # el preproceso nunca debe tumbar la transcripcion
        base["motivo"] = f"No se pudo analizar el audio: {exc}"
        return base


# --- Recorte -----------------------------------------------------------------

def _escribir_wav_recortado(origen: Path, segundos: float) -> Optional[Path]:
    try:
        with wave.open(str(origen), "rb") as wf:
            canales = wf.getnchannels()
            ancho = wf.getsampwidth()
            tasa = wf.getframerate()
            total = wf.getnframes()
            saltar = int(tasa * segundos)
            if saltar <= 0 or saltar >= total:
                return None
            wf.setpos(saltar)
            datos = wf.readframes(total - saltar)

        destino = origen.with_name(f"{origen.stem}__sin_timbrado_{uuid4().hex[:8]}{origen.suffix}")
        with wave.open(str(destino), "wb") as salida:
            salida.setnchannels(canales)
            salida.setsampwidth(ancho)
            salida.setframerate(tasa)
            salida.writeframes(datos)
        return destino
    except Exception:
        return None


def preparar_audio_para_transcripcion(ruta_audio: str) -> Tuple[str, Dict]:
    """Devuelve (ruta a transcribir, info del preproceso).

    Si no hay evidencia de timbrado, devuelve la ruta original intacta. El
    archivo original NUNCA se modifica ni se borra: el recorte se escribe
    como un archivo temporal aparte.

    `info["segundos_descartados"]` es el desfase que hay que sumar a los
    timestamps devueltos por el transcriptor.
    """
    info = detectar_inicio_conversacion(ruta_audio)
    info["recortado"] = False
    info["ruta_recorte"] = None

    if not info.get("hay_timbrado"):
        info["segundos_descartados"] = 0.0
        return ruta_audio, info

    segundos = float(info.get("segundos_descartados") or 0.0)
    origen = Path(ruta_audio)

    try:
        with wave.open(str(origen), "rb") as wf:
            duracion = wf.getnframes() / float(wf.getframerate() or 1)
    except Exception:
        duracion = 0.0

    if segundos < RECORTE_MINIMO_SEGUNDOS:
        info["segundos_descartados"] = 0.0
        info["motivo"] = f"{info['motivo']} Tramo breve: no se recorta."
        return ruta_audio, info

    if segundos > RECORTE_MAXIMO_SEGUNDOS or (
        duracion > 0 and segundos > duracion * RECORTE_MAXIMO_PROPORCION
    ):
        info["segundos_descartados"] = 0.0
        info["motivo"] = (
            f"{info['motivo']} Tramo desproporcionado frente a la duracion: "
            "se transcribe el audio completo para no perder conversacion."
        )
        return ruta_audio, info

    destino = _escribir_wav_recortado(origen, segundos)
    if destino is None:
        info["segundos_descartados"] = 0.0
        info["motivo"] = "No se pudo escribir el audio recortado; se usa el original."
        return ruta_audio, info

    info["recortado"] = True
    info["ruta_recorte"] = str(destino)
    return str(destino), info


def limpiar_recorte(info: Dict) -> None:
    """Borra el temporal del recorte. El original queda intacto."""
    ruta = (info or {}).get("ruta_recorte")
    if not ruta:
        return
    try:
        Path(ruta).unlink(missing_ok=True)
    except Exception:
        pass
