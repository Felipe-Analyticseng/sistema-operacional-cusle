from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"
LOGO_PATH = STATIC_DIR / "img" / "logo_cusle.png"
UPLOAD_DIR = BASE_DIR / "uploads" / "comprovantes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _parse_decimal_env(name: str, default: str = "0") -> float:
    raw = os.getenv(name, default) or default
    normalized = str(raw).strip().replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return float(default)

DATABASE_URL = os.getenv("DATABASE_URL")
PIX_CUSLE_CHAVE = os.getenv("PIX_CUSLE_CHAVE", "Chave Pix ainda não configurada")
PIX_CUSLE_NOME = os.getenv("PIX_CUSLE_NOME", "Favorecido ainda não configurado")
FALTAS_URL = os.getenv("FALTAS_URL", "https://lista-cambones.onrender.com/faltas")

CESTA_BASICA_PAC_VALOR = _parse_decimal_env("CESTA_BASICA_PAC_VALOR")
