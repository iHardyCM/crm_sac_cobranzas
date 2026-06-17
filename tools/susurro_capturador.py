from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Optional
import warnings

import numpy as np
import requests
import scipy.io.wavfile as wav
from dotenv import load_dotenv
from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
warnings.filterwarnings("ignore", message="data discontinuity in recording")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_API = "http://127.0.0.1:8000/susurro-ia"
TRANSCRIPTION_MODEL = os.getenv("SUSURRO_TRANSCRIPTION_MODEL", os.getenv("IA_FEEDBACK_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"))


def main():
    parser = argparse.ArgumentParser(description="Capturador local para Susurro IA.")
    parser.add_argument("--api", default=DEFAULT_API, help="Base URL del modulo Susurro IA.")
    parser.add_argument("--session-id", default=None, help="Sesion existente. Si se omite, crea una.")
    parser.add_argument("--speaker", choices=["cliente", "agente"], default="cliente", help="Quien habla en esta fuente.")
    parser.add_argument("--source", choices=["loopback", "mic"], default="loopback", help="Fuente de audio.")
    parser.add_argument("--device", type=int, default=None, help="ID de dispositivo para mic.")
    parser.add_argument("--seconds", type=float, default=6.0, help="Duracion de cada chunk.")
    parser.add_argument("--rate", type=int, default=16000, help="Sample rate de captura.")
    parser.add_argument("--min-rms", type=float, default=0.008, help="Volumen minimo para transcribir.")
    parser.add_argument("--agente", default=None, help="Nombre o DNI del agente.")
    parser.add_argument("--cartera", default=None, help="Cartera o contexto.")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY no esta configurada en .env.")

    session_id = args.session_id or crear_sesion(args.api, args.agente, args.cartera)
    print(f"Sesion Susurro IA: {session_id}")
    print(f"Abre la vista con esta URL: {args.api}?session_id={session_id}")
    print(f"Fuente: {args.source} | hablante: {args.speaker} | chunk: {args.seconds}s")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if args.source == "loopback":
        capturar_loopback(args, session_id, client)
    else:
        capturar_microfono(args, session_id, client)


def crear_sesion(api: str, agente: Optional[str], cartera: Optional[str]) -> str:
    response = requests.post(
        f"{api}/sesiones",
        json={"agente": agente or "capturador_local", "cartera": cartera, "modo": "captura_local"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["session_id"]


def capturar_loopback(args, session_id: str, client: OpenAI):
    import soundcard as sc

    speaker = sc.default_speaker()
    print(f"Salida default: {speaker.name}")
    loopback = sc.get_microphone(id=speaker.id, include_loopback=True)
    print(f"Loopback: {loopback.name}")

    frames = int(args.rate * args.seconds)
    with loopback.recorder(samplerate=args.rate) as recorder:
        while True:
            data = recorder.record(numframes=frames)
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            procesar_chunk(args, session_id, client, data)


def capturar_microfono(args, session_id: str, client: OpenAI):
    import sounddevice as sd

    device = args.device
    if device is None:
        device = sd.default.device[0]
    info = sd.query_devices(device)
    print(f"Microfono: [{device}] {info['name']}")

    frames = int(args.rate * args.seconds)
    while True:
        data = sd.rec(frames, samplerate=args.rate, channels=1, dtype="float32", device=device)
        sd.wait()
        procesar_chunk(args, session_id, client, data.reshape(-1))


def procesar_chunk(args, session_id: str, client: OpenAI, data: np.ndarray):
    rms = calcular_rms(data)
    if rms < args.min_rms:
        print(f"silencio rms={rms:.4f}")
        return

    text = transcribir_chunk(client, data, args.rate)
    if not text:
        print(f"sin texto rms={rms:.4f}")
        return

    print(f"{args.speaker}: {text}")
    enviar_fragmento(args.api, session_id, text, args.speaker, args.source)


def transcribir_chunk(client: OpenAI, data: np.ndarray, rate: int) -> str:
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak > 0:
        data = data / max(peak, 1e-6) * 0.85

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        wav.write(path, rate, np.int16(np.clip(data, -1, 1) * 32767))
        with open(path, "rb") as audio:
            result = client.audio.transcriptions.create(
                model=TRANSCRIPTION_MODEL,
                file=audio,
                language="es",
            )
        return (getattr(result, "text", None) or "").strip()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def enviar_fragmento(api: str, session_id: str, text: str, speaker: str, source: str):
    response = requests.post(
        f"{api}/fragmentos",
        json={
            "session_id": session_id,
            "texto": text,
            "speaker": speaker,
            "source": source,
        },
        timeout=15,
    )
    response.raise_for_status()
    current = response.json().get("session", {}).get("current") or {}
    if current:
        print(f"-> {current.get('intent')} | {current.get('priority')} | {current.get('ai_mode')}")
        print(f"-> {current.get('suggestion')}")
    time.sleep(0.2)


def calcular_rms(data: np.ndarray) -> float:
    if data is None or data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(data))))


if __name__ == "__main__":
    main()
