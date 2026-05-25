import re
import unicodedata

import pandas as pd


PATH = "lista_pessoas.xlsx"
NAME_COL = "Nome"
REQUIRED_COLUMNS = ["CPF", "Telefone", "Email", "Data Nascimento"]


def slug(value) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", ".", text.lower()).strip(".")
    return text or "pessoa"


def fallback_email(row) -> str:
    current = str(row.get("Email", "")).strip()
    if current and current.lower() != "nan":
        return current
    return f"sem-email+{slug(row[NAME_COL])}@cusle.local"


df = pd.read_excel(PATH)
for column in REQUIRED_COLUMNS:
    if column not in df.columns:
        df[column] = ""

df["Email"] = df.apply(fallback_email, axis=1)
ordered = [NAME_COL, *REQUIRED_COLUMNS]
df = df[ordered + [column for column in df.columns if column not in ordered]]
df.to_excel(PATH, index=False)

print(df.shape)
print(list(df.columns))
