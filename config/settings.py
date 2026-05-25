from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"
LOGO_PATH = STATIC_DIR / "img" / "logo_cusle.png"
UPLOAD_DIR = BASE_DIR / "uploads" / "comprovantes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL")
PIX_CUSLE_CHAVE = os.getenv("PIX_CUSLE_CHAVE", "Chave Pix ainda não configurada")
PIX_CUSLE_NOME = os.getenv("PIX_CUSLE_NOME", "Favorecido ainda não configurado")
FALTAS_URL = os.getenv("FALTAS_URL", "https://lista-cambones.onrender.com/faltas")

CESTA_BASICA_PAC_VALOR = float(os.getenv("CESTA_BASICA_PAC_VALOR", "0") or 0)
