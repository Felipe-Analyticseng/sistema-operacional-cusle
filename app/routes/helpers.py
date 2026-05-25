from __future__ import annotations

from functools import wraps
from io import BytesIO
from pathlib import Path
import math

import pandas as pd
from flask import Response, flash, redirect, session, url_for


def df_records(df: pd.DataFrame | None) -> list[dict]:
    if df is None or df.empty:
        return []
    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


def safe_int(value, default=0) -> int:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return int(value)
    except Exception:
        return default


def excel_response(df: pd.DataFrame, filename: str, sheet_name: str = "dados") -> Response:
    output = BytesIO()
    clean = pd.DataFrame() if df is None else df.copy()
    for col in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[col]):
            try:
                clean[col] = clean[col].dt.tz_localize(None)
            except Exception:
                pass
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        clean.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def csv_response(df: pd.DataFrame, filename: str) -> Response:
    clean = pd.DataFrame() if df is None else df.copy()
    data = clean.to_csv(index=False, sep=";", encoding="utf-8-sig")
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logado"):
            flash("Faça login para acessar o painel administrativo.", "warning")
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapper


def portal_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("admin_logado") or session.get("portal_logado"):
            return view(*args, **kwargs)
        flash("Faça login para acessar o portal.", "warning")
        return redirect(url_for("user.portal_login"))
    return wrapper


def normalize_file_path(path_str: str | None, base_dir: Path) -> Path | None:
    if not path_str:
        return None
    raw = Path(str(path_str))
    if raw.exists():
        return raw
    candidate = base_dir / str(path_str)
    return candidate if candidate.exists() else None
