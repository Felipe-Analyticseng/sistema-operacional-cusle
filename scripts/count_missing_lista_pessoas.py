import os
import re
import sys
import unicodedata
from urllib.parse import urlparse

import pandas as pd


sys.path.insert(0, r"C:\tmp\codex_pg")
import pg8000.dbapi  # noqa: E402


def normalizar_nome(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().strip()
    return re.sub(r"\s+", " ", text)


def read_database_url() -> str:
    for line in open(".env", encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL não encontrada no .env")


planilha = pd.read_excel("lista_pessoas.xlsx")
planilha_nomes = {
    normalizar_nome(nome)
    for nome in planilha["Nome"].dropna().astype(str)
    if normalizar_nome(nome)
}

url = urlparse(read_database_url())
conn = pg8000.dbapi.connect(
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port or 5432,
    database=(url.path or "").lstrip("/"),
    ssl_context=True,
)
try:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT nome
        FROM cadastro.cadastro
        WHERE LOWER(COALESCE(perfil, '')) IN ('filhe', 'filhes');
        """
    )
    cadastro_nomes = {
        normalizar_nome(row[0])
        for row in cur.fetchall()
        if normalizar_nome(row[0])
    }
finally:
    conn.close()

faltantes = sorted(planilha_nomes - cadastro_nomes)
print(f"planilha_total={len(planilha_nomes)}")
print(f"cadastro_filhes_total={len(cadastro_nomes)}")
print(f"faltantes_total={len(faltantes)}")
print("primeiros_faltantes=" + ", ".join(faltantes[:20]))
