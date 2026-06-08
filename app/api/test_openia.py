from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import os

# Ruta raíz del proyecto: CRM_SAC_COBRANZAS
BASE_DIR = Path(__file__).resolve().parents[2]

# Cargar .env desde la raíz
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")

print("BASE_DIR:", BASE_DIR)
print("API KEY cargada:", "SI" if api_key else "NO")

client = OpenAI(api_key=api_key)

response = client.responses.create(
    model="gpt-5.5",
    input="Responde solo: API funcionando."
)

print(response.output_text)