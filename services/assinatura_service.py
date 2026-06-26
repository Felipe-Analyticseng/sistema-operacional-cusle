from __future__ import annotations

import base64
import os
import secrets
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from flask import request, url_for
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from config.settings import BASE_DIR
from db.database import execute_command, execute_returning, fetch_one, run_query
from services.cadastro_service import only_digits


BATCHES = {
    "filhes_batch": {
        "label": "Lote FILHES (Consentimento + LGPD + Imagem/Voz)",
        "perfil_db": "filhes",
        "docs": ["doc1", "doc2", "doc3"],
        "source_table": "cadastro.cadastro",
    },
    "pac_batch": {
        "label": "Lote PAC (Consentimento + Imagem/Voz)",
        "perfil_db": "pac",
        "docs": ["doc4", "doc5"],
        "source_table": "cadastro.cadastro_pac",
    },
}


def _originals_dir() -> Path:
    configured = os.getenv("TERMOS_ORIGINALS_DIR")
    if configured:
        return Path(configured)
    local_originals = BASE_DIR / "originals"
    if local_originals.exists():
        return local_originals
    return BASE_DIR.parent.parent / "Via-Nativo" / "originals"


def _uploads_dir() -> Path:
    path = Path(os.getenv("TERMOS_UPLOAD_DIR") or (BASE_DIR / "uploads" / "termos"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def termos_upload_dir() -> Path:
    return _uploads_dir()


def termos_allowed_upload_dirs() -> list[Path]:
    roots = [_uploads_dir()]
    legacy = Path(os.getenv("TERMOS_LEGACY_UPLOAD_DIR") or (BASE_DIR.parent.parent / "Via-Nativo" / "uploads"))
    roots.append(legacy)
    return roots


def get_base_url() -> str:
    base = (os.getenv("APP_BASE_URL") or "").strip()
    if base:
        return base.rstrip("/")
    return request.host_url.rstrip("/")


def garantir_estrutura_assinaturas() -> None:
    execute_command("CREATE SCHEMA IF NOT EXISTS cadastro;")
    execute_command(
        """
        CREATE TABLE IF NOT EXISTS cadastro.envelopes (
            id SERIAL PRIMARY KEY,
            doc_key VARCHAR(60) NOT NULL,
            cadastro_id INTEGER NOT NULL,
            token VARCHAR(200) NOT NULL UNIQUE,
            status VARCHAR(20) NOT NULL DEFAULT 'sent',
            signed_pdf_path TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            signed_at TIMESTAMP WITH TIME ZONE
        );
        """
    )
    execute_command(
        """
        ALTER TABLE cadastro.envelopes
        ADD COLUMN IF NOT EXISTS signed_pdf_data BYTEA,
        ADD COLUMN IF NOT EXISTS signed_by_name TEXT;
        """
    )
    execute_command(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_envelope_doc_cadastro
            ON cadastro.envelopes (doc_key, cadastro_id);
        """
    )


def migrar_envelopes_pac_legados() -> None:
    """Vincula termos PAC antigos ao cadastro.cadastro_pac pelo CPF."""
    garantir_estrutura_assinaturas()
    from services.pac_service import garantir_estrutura_pac

    garantir_estrutura_pac()
    execute_command(
        """
        WITH matches AS (
            SELECT
                e.id AS legacy_envelope_id,
                cp.id AS pac_cadastro_id,
                target.id AS target_envelope_id
            FROM cadastro.envelopes e
            JOIN cadastro.cadastro c
                ON c.id = e.cadastro_id
               AND LOWER(COALESCE(c.perfil, '')) = 'pac'
            JOIN cadastro.cadastro_pac cp
                ON regexp_replace(COALESCE(cp.cpf, ''), '[^0-9]', '', 'g')
                 = regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g')
               AND LOWER(COALESCE(cp.perfil, '')) = 'pac'
            LEFT JOIN cadastro.envelopes target
                ON target.doc_key = e.doc_key
               AND target.cadastro_id = cp.id
            WHERE e.doc_key = 'pac_batch'
              AND e.cadastro_id <> cp.id
        )
        UPDATE cadastro.envelopes e
        SET cadastro_id = m.pac_cadastro_id
        FROM matches m
        WHERE e.id = m.legacy_envelope_id
          AND m.target_envelope_id IS NULL;
        """
    )
    execute_command(
        """
        WITH matches AS (
            SELECT
                e.id AS legacy_envelope_id,
                target.id AS target_envelope_id
            FROM cadastro.envelopes e
            JOIN cadastro.cadastro c
                ON c.id = e.cadastro_id
               AND LOWER(COALESCE(c.perfil, '')) = 'pac'
            JOIN cadastro.cadastro_pac cp
                ON regexp_replace(COALESCE(cp.cpf, ''), '[^0-9]', '', 'g')
                 = regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g')
               AND LOWER(COALESCE(cp.perfil, '')) = 'pac'
            JOIN cadastro.envelopes target
                ON target.doc_key = e.doc_key
               AND target.cadastro_id = cp.id
            WHERE e.doc_key = 'pac_batch'
              AND e.cadastro_id <> cp.id
              AND target.id <> e.id
        )
        UPDATE cadastro.envelopes target
        SET
            status = CASE
                WHEN target.status = 'signed' OR legacy.status = 'signed' THEN 'signed'
                ELSE target.status
            END,
            signed_at = COALESCE(target.signed_at, legacy.signed_at),
            signed_pdf_path = COALESCE(target.signed_pdf_path, legacy.signed_pdf_path),
            signed_pdf_data = COALESCE(target.signed_pdf_data, legacy.signed_pdf_data)
        FROM matches m
        JOIN cadastro.envelopes legacy ON legacy.id = m.legacy_envelope_id
        WHERE target.id = m.target_envelope_id;
        """
    )


def _table_for_batch(batch_key: str) -> str:
    cfg = BATCHES.get(batch_key)
    if not cfg:
        raise ValueError("Lote de assinatura inválido.")
    return cfg["source_table"]


def _cadastro_by_id(batch_key: str, cadastro_id: int) -> dict | None:
    table = _table_for_batch(batch_key)
    return fetch_one(
        f"""
        SELECT id, nome, email, cpf, telefone, menor_idade, responsavel_nome, responsavel_cpf
        FROM {table}
        WHERE id = :cadastro_id
        LIMIT 1;
        """,
        {"cadastro_id": cadastro_id},
    )


def _cadastro_by_token(token: str) -> dict | None:
    garantir_estrutura_assinaturas()
    env = fetch_one("SELECT * FROM cadastro.envelopes WHERE token = :token LIMIT 1;", {"token": token})
    if not env or env.get("doc_key") not in BATCHES:
        return None
    cadastro = _cadastro_by_id(env["doc_key"], env["cadastro_id"])
    if not cadastro:
        return None
    return {"envelope": env, "cadastro": cadastro, "batch": BATCHES[env["doc_key"]]}


def envelope_existente_por_cpf(batch_key: str, cpf: str | None) -> dict | None:
    cpf_limpo = only_digits(cpf)
    if not cpf_limpo:
        return None
    table = _table_for_batch(batch_key)
    return fetch_one(
        f"""
        SELECT e.*
        FROM cadastro.envelopes e
        JOIN {table} c ON c.id = e.cadastro_id
        WHERE e.doc_key = :batch_key
          AND regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g') = :cpf
        ORDER BY e.created_at DESC
        LIMIT 1;
        """,
        {"batch_key": batch_key, "cpf": cpf_limpo},
    )


def criar_ou_obter_envelope(batch_key: str, cadastro_id: int) -> dict:
    garantir_estrutura_assinaturas()
    cadastro = _cadastro_by_id(batch_key, cadastro_id)
    if not cadastro:
        raise ValueError("Cadastro do assinante não encontrado.")

    existente = envelope_existente_por_cpf(batch_key, cadastro.get("cpf"))
    if existente:
        existente["sign_url"] = f"{get_base_url()}{url_for('assinaturas.sign', token=existente['token'])}"
        return existente

    env = execute_returning(
        """
        INSERT INTO cadastro.envelopes (doc_key, cadastro_id, token, status)
        VALUES (:doc_key, :cadastro_id, :token, 'sent')
        RETURNING *;
        """,
        {"doc_key": batch_key, "cadastro_id": cadastro_id, "token": secrets.token_urlsafe(32)},
    )
    env["sign_url"] = f"{get_base_url()}{url_for('assinaturas.sign', token=env['token'])}"
    return env


def pendentes_por_lote(batch_key: str) -> list[dict]:
    garantir_estrutura_assinaturas()
    cfg = BATCHES[batch_key]
    table = cfg["source_table"]
    perfil = cfg["perfil_db"]
    df = run_query(
        f"""
        WITH base AS (
            SELECT
                CASE
                    WHEN c.menor_idade = true THEN NULLIF(TRIM(c.responsavel_cpf), '')
                    ELSE NULLIF(TRIM(c.cpf), '')
                END AS signer_cpf
            FROM {table} c
            WHERE LOWER(COALESCE(c.perfil, '')) = :perfil
        ),
        signers AS (
            SELECT DISTINCT signer_cpf FROM base WHERE signer_cpf IS NOT NULL
        ),
        signer_info AS (
            SELECT c.id AS cadastro_id, c.nome, c.email, c.cpf
            FROM signers s
            JOIN {table} c ON regexp_replace(COALESCE(c.cpf, ''), '[^0-9]', '', 'g') = regexp_replace(s.signer_cpf, '[^0-9]', '', 'g')
            WHERE NULLIF(TRIM(COALESCE(c.email, '')), '') IS NOT NULL
        )
        SELECT si.*
        FROM signer_info si
        WHERE NOT EXISTS (
            SELECT 1
            FROM cadastro.envelopes e
            JOIN {table} c2 ON c2.id = e.cadastro_id
            WHERE e.doc_key = :batch_key
              AND regexp_replace(COALESCE(c2.cpf, ''), '[^0-9]', '', 'g') = regexp_replace(COALESCE(si.cpf, ''), '[^0-9]', '', 'g')
        )
        ORDER BY si.nome;
        """,
        {"perfil": perfil, "batch_key": batch_key},
    )
    return df.to_dict(orient="records")


def historico_assinaturas(batch_key: str | None = None) -> list[dict]:
    garantir_estrutura_assinaturas()
    if batch_key in (None, "pac_batch"):
        migrar_envelopes_pac_legados()
    where = "WHERE (:batch_key IS NULL OR e.doc_key = :batch_key)"
    rows = []
    for key, cfg in BATCHES.items():
        if batch_key and key != batch_key:
            continue
        table = cfg["source_table"]
        df = run_query(
            f"""
            SELECT
                e.id, e.doc_key, e.cadastro_id, e.token, e.status, e.signed_pdf_path,
                e.created_at, e.signed_at, c.nome, c.email, c.cpf, c.telefone
            FROM cadastro.envelopes e
            JOIN {table} c ON c.id = e.cadastro_id
            {where}
            ORDER BY e.created_at DESC;
            """,
            {"batch_key": key},
        )
        for row in df.to_dict(orient="records"):
            row["batch_label"] = cfg["label"]
            row["sign_url"] = f"{get_base_url()}{url_for('assinaturas.sign', token=row['token'])}"
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return rows


def _path_inside_allowed_dir(path: Path, allowed_dirs: list[Path]) -> bool:
    resolved = path.resolve()
    return any(root == resolved or root in resolved.parents for root in allowed_dirs)


def _resolve_signed_pdf_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    allowed_dirs = [p.resolve() for p in termos_allowed_upload_dirs()]
    raw = Path(str(path_value))
    candidates = [raw]

    if raw.name:
        for root in allowed_dirs:
            candidates.append(root / raw.name)
            candidates.append(root / "termos" / raw.name)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if _path_inside_allowed_dir(resolved, allowed_dirs) and resolved.exists() and resolved.is_file():
            return resolved
    return None


def buscar_pdf_assinado(envelope_id: int | None = None, path: str | None = None) -> dict | None:
    garantir_estrutura_assinaturas()
    envelope = None
    if envelope_id:
        envelope = fetch_one(
            """
            SELECT id, doc_key, cadastro_id, status, signed_at, signed_pdf_path, signed_pdf_data, signed_by_name
            FROM cadastro.envelopes
            WHERE id = :id
            LIMIT 1;
            """,
            {"id": envelope_id},
        )

    if envelope and envelope.get("status") == "signed":
        regenerated = regenerar_pdf_assinado(envelope)
        if regenerated:
            return regenerated

    if envelope and envelope.get("signed_pdf_data") is not None:
        data = envelope["signed_pdf_data"]
        return {
            "bytes": bytes(data),
            "filename": f"termo_assinado_{envelope['id']}.pdf",
        }

    file_path = _resolve_signed_pdf_path((envelope or {}).get("signed_pdf_path") or path)
    if file_path:
        if envelope:
            try:
                pdf_bytes = file_path.read_bytes()
                execute_command(
                    """
                    UPDATE cadastro.envelopes
                    SET signed_pdf_data = COALESCE(signed_pdf_data, :pdf_data)
                    WHERE id = :id;
                    """,
                    {"id": envelope["id"], "pdf_data": pdf_bytes},
                )
                return {
                    "bytes": pdf_bytes,
                    "filename": f"termo_assinado_{envelope['id']}.pdf",
                }
            except Exception:
                pass
        return {"path": file_path, "filename": file_path.name}
    return None


def dependentes_do_responsavel(batch_key: str, responsavel_cpf: str | None) -> list[dict]:
    cpf = only_digits(responsavel_cpf)
    if not cpf:
        return []
    table = _table_for_batch(batch_key)
    df = run_query(
        f"""
        SELECT nome, cpf
        FROM {table}
        WHERE menor_idade = true
          AND regexp_replace(COALESCE(responsavel_cpf, ''), '[^0-9]', '', 'g') = :cpf
        ORDER BY nome;
        """,
        {"cpf": cpf},
    )
    return df.to_dict(orient="records")


def responsavel_do_cadastro(batch_key: str, cadastro: dict) -> dict | None:
    responsavel_cpf = only_digits(cadastro.get("responsavel_cpf"))
    if not responsavel_cpf:
        return None
    table = _table_for_batch(batch_key)
    return fetch_one(
        f"""
        SELECT nome, cpf, telefone, email
        FROM {table}
        WHERE regexp_replace(COALESCE(cpf, ''), '[^0-9]', '', 'g') = :cpf
        LIMIT 1;
        """,
        {"cpf": responsavel_cpf},
    ) or {
        "nome": cadastro.get("responsavel_nome"),
        "cpf": cadastro.get("responsavel_cpf"),
        "telefone": None,
        "email": None,
    }


def merge_docs_to_pdf_bytes(doc_keys: list[str]) -> bytes:
    writer = PdfWriter()
    for doc_key in doc_keys:
        path = _originals_dir() / f"{doc_key}.pdf"
        if not path.exists():
            raise FileNotFoundError(f"Documento {doc_key}.pdf não encontrado em {path}.")
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


def _draw_dependents(c, page_w, start_y, dependentes: list[dict]) -> None:
    if not dependentes:
        return
    margin_x = 48
    y = start_y
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin_x, y, "Dependentes vinculados:")
    y -= 15
    c.setFont("Helvetica", 9)
    for dep in dependentes[:12]:
        c.drawString(margin_x, y, f"- {dep.get('nome', '')}")
        y -= 13


def stamp_pdf(
    pdf_bytes: bytes,
    signer_name: str,
    signature_png: bytes | None,
    dependentes: list[dict],
    cadastro: dict | None = None,
    responsavel: dict | None = None,
    signed_at=None,
    regenerated: bool = False,
) -> bytes:
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    first_page = writer.pages[0]
    page_w = float(first_page.mediabox.width)
    page_h = float(first_page.mediabox.height)

    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_w, page_h))
    signed_dt = signed_at.strftime("%d/%m/%Y %H:%M") if hasattr(signed_at, "strftime") else datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")

    margin = 48
    y = page_h - 64
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "Confirmacao de assinatura eletronica")
    y -= 26
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, "Este documento foi assinado eletronicamente pelo Portal CUSLE.")
    if regenerated:
        y -= 15
        c.drawString(margin, y, "PDF regenerado a partir do registro de assinatura armazenado no sistema.")

    y -= 36
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Assinante")
    y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(margin, y, f"Nome: {signer_name}")
    y -= 16
    c.drawString(margin, y, f"Data da assinatura: {signed_dt}")

    if responsavel and responsavel.get("nome"):
        y -= 30
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "Responsavel vinculado")
        y -= 18
        c.setFont("Helvetica", 11)
        c.drawString(margin, y, f"Nome: {responsavel.get('nome')}")
        if responsavel.get("telefone"):
            y -= 16
            c.drawString(margin, y, f"Telefone: {responsavel.get('telefone')}")

    y -= 38
    c.setStrokeColorRGB(.72, .78, .86)
    c.line(margin, y, page_w - margin, y)
    y -= 86
    if signature_png:
        c.drawImage(ImageReader(BytesIO(signature_png)), margin, y, width=260, height=70, mask="auto")
    else:
        c.setFont("Helvetica-Oblique", 28)
        c.drawString(margin + 8, y + 28, signer_name)
    c.setFont("Helvetica", 9)
    c.drawString(margin, y - 8, "Assinatura eletronica")

    if dependentes:
        _draw_dependents(c, page_w, y - 42, dependentes)
    c.save()
    packet.seek(0)

    signature_page = PdfReader(packet).pages[0]
    writer.add_page(signature_page)
    out = BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


def regenerar_pdf_assinado(envelope: dict) -> dict | None:
    if envelope.get("doc_key") not in BATCHES:
        return None
    cadastro = _cadastro_by_id(envelope["doc_key"], envelope["cadastro_id"])
    if not cadastro:
        return None
    signer_name = (envelope.get("signed_by_name") or cadastro.get("nome") or "").strip()
    if not signer_name:
        return None
    try:
        merged = merge_docs_to_pdf_bytes(BATCHES[envelope["doc_key"]]["docs"])
        dependentes = dependentes_do_responsavel(envelope["doc_key"], cadastro.get("cpf"))
        responsavel = responsavel_do_cadastro(envelope["doc_key"], cadastro)
        if not responsavel and dependentes:
            responsavel = cadastro
        signed_pdf = stamp_pdf(
            merged,
            signer_name,
            None,
            dependentes,
            cadastro=cadastro,
            responsavel=responsavel,
            signed_at=envelope.get("signed_at"),
            regenerated=True,
        )
        execute_command(
            """
            UPDATE cadastro.envelopes
            SET signed_pdf_data = :pdf_data,
                signed_by_name = COALESCE(signed_by_name, :signed_by_name)
            WHERE id = :id;
            """,
            {"id": envelope["id"], "pdf_data": signed_pdf, "signed_by_name": signer_name},
        )
        return {"bytes": signed_pdf, "filename": f"termo_assinado_{envelope['id']}.pdf"}
    except Exception:
        return None


def assinar_envelope(token: str, typed_name: str, signature_data_url: str) -> dict:
    data = _cadastro_by_token(token)
    if not data:
        raise ValueError("Link inválido ou cadastro não encontrado.")
    env = data["envelope"]
    if env["status"] == "signed":
        raise ValueError("Este lote já foi assinado.")
    if not typed_name or len(typed_name.strip()) < 3:
        raise ValueError("Digite o nome completo.")
    if not signature_data_url.startswith("data:image/png;base64,"):
        raise ValueError("Assinatura inválida.")

    signature_png = base64.b64decode(signature_data_url.split(",", 1)[1])
    dependentes = dependentes_do_responsavel(env["doc_key"], data["cadastro"].get("cpf"))
    responsavel = responsavel_do_cadastro(env["doc_key"], data["cadastro"])
    if not responsavel and dependentes:
        responsavel = data["cadastro"]
    merged = merge_docs_to_pdf_bytes(data["batch"]["docs"])
    signed_pdf = stamp_pdf(
        merged,
        typed_name.strip(),
        signature_png,
        dependentes,
        cadastro=data["cadastro"],
        responsavel=responsavel,
    )

    filename = f"signed_{env['doc_key']}_env{env['id']}_{secrets.token_urlsafe(8)}.pdf"
    path = _uploads_dir() / filename
    path.write_bytes(signed_pdf)
    updated = execute_returning(
        """
        UPDATE cadastro.envelopes
        SET status = 'signed',
            signed_at = NOW(),
            signed_pdf_path = :path,
            signed_pdf_data = :pdf_data,
            signed_by_name = :signed_by_name
        WHERE id = :id
        RETURNING *;
        """,
        {"id": env["id"], "path": str(path), "pdf_data": signed_pdf, "signed_by_name": typed_name.strip()},
    )
    return {"envelope": updated, "cadastro": data["cadastro"], "batch": data["batch"], "filename": filename}


def buscar_assinatura(token: str) -> dict | None:
    data = _cadastro_by_token(token)
    if not data:
        return None
    data["preview_url"] = url_for("assinaturas.preview_pdf", token=token)
    return data
