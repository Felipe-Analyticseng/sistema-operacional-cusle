from __future__ import annotations

import pandas as pd
from flask import Blueprint, jsonify

from services.financeiro_service import listar_comprovantes
from services.pac_service import listar_criancas_pac, listar_pac_cadastros, listar_responsaveis_pac

bp = Blueprint("api", __name__)


def _faixa(idade):
    try:
        idade = int(idade)
    except Exception:
        return "Não informado"
    if idade <= 3:
        return "0 a 3 anos"
    if idade <= 6:
        return "4 a 6 anos"
    if idade <= 12:
        return "7 a 12 anos"
    if idade <= 17:
        return "13 a 17 anos"
    if idade <= 29:
        return "18 a 29 anos"
    if idade <= 39:
        return "30 a 39 anos"
    if idade <= 49:
        return "40 a 49 anos"
    if idade <= 59:
        return "50 a 59 anos"
    return "60+ anos"


@bp.get("/admin/dashboard")
def admin_dashboard_data():
    # Mantido apenas para alimentar o Dashboard PAC. A visão executiva foi removida.
    cad = listar_pac_cadastros()
    faixas = []
    if cad is not None and not cad.empty:
        tmp = cad.copy()
        tmp["faixa"] = tmp["idade"].apply(_faixa)
        ordem = ["0 a 3 anos", "4 a 6 anos", "7 a 12 anos", "13 a 17 anos", "18 a 29 anos", "30 a 39 anos", "40 a 49 anos", "50 a 59 anos", "60+ anos", "Não informado"]
        grouped = tmp.groupby("faixa", as_index=False).size().rename(columns={"size": "quantidade"})
        grouped["ordem"] = grouped["faixa"].apply(lambda x: ordem.index(x) if x in ordem else 999)
        faixas = grouped.sort_values("ordem")[["faixa", "quantidade"]].to_dict(orient="records")

    return jsonify({"faixas": faixas})
