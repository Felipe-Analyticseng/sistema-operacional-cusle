from __future__ import annotations

from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, request, send_file, session, url_for, flash

from services.assinatura_service import (
    assinar_envelope,
    buscar_assinatura,
    buscar_pdf_assinado,
    merge_docs_to_pdf_bytes,
)

bp = Blueprint("assinaturas", __name__)


@bp.get("/assinatura/<token>")
def sign(token: str):
    data = buscar_assinatura(token)
    if not data:
        return "Link inválido.", 404
    if data["envelope"].get("status") == "signed":
        return render_template("assinaturas/done.html", batch_label=data["batch"]["label"])
    return render_template("assinaturas/sign.html", token=token, **data)


@bp.get("/assinatura/<token>/preview.pdf")
def preview_pdf(token: str):
    data = buscar_assinatura(token)
    if not data:
        abort(404)
    pdf = merge_docs_to_pdf_bytes(data["batch"]["docs"])
    return send_file(
        BytesIO(pdf),
        as_attachment=False,
        download_name=f"{data['envelope']['doc_key']}.pdf",
        mimetype="application/pdf",
    )


@bp.post("/assinatura/<token>/submit")
def submit(token: str):
    try:
        result = assinar_envelope(
            token=token,
            typed_name=request.form.get("typed_name") or "",
            signature_data_url=request.form.get("signature_data") or "",
        )
        return render_template("assinaturas/done.html", batch_label=result["batch"]["label"])
    except Exception as exc:
        flash(str(exc), "danger")
        return redirect(url_for("assinaturas.sign", token=token))


@bp.get("/assinaturas/download")
def download_signed():
    if not (session.get("admin_logado") or session.get("admin_pac_logado")):
        abort(403)

    envelope_id = request.args.get("id", type=int)
    pdf = buscar_pdf_assinado(envelope_id=envelope_id, path=request.args.get("path"))
    if not pdf:
        abort(404)

    if pdf.get("bytes") is not None:
        return send_file(
            BytesIO(pdf["bytes"]),
            as_attachment=False,
            download_name=pdf["filename"],
            mimetype="application/pdf",
        )

    file_path = Path(pdf["path"])
    return send_file(
        file_path,
        as_attachment=False,
        download_name=pdf["filename"],
        mimetype="application/pdf",
    )
