# services/financeiro_service.py

from datetime import datetime
from pathlib import Path
import re
import unicodedata
from uuid import uuid4

from db.database import execute_returning, run_query
from services.cadastro_service import buscar_cadastro_por_cpf, only_digits


BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "uploads" / "comprovantes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


def parse_brl_value(value: str | float | int | None) -> float:
    """
    Converte valores digitados em formato brasileiro para float.

    Exemplos aceitos:
    - 50
    - 50,00
    - 1.250,75
    - 1250.75
    - R$ 1.250,75
    """
    if value is None:
        raise ValueError("Informe um valor.")

    if isinstance(value, (int, float)):
        parsed_value = float(value)
    else:
        value_str = str(value).strip()

        if not value_str:
            raise ValueError("Informe um valor.")

        value_str = value_str.replace("R$", "").strip()

        if "," in value_str:
            value_str = value_str.replace(".", "").replace(",", ".")

        try:
            parsed_value = float(value_str)
        except ValueError:
            raise ValueError("Valor inválido. Use o formato 50,00 ou 1.250,75.")

    if parsed_value <= 0:
        raise ValueError("Informe um valor maior que zero.")

    return parsed_value


def format_brl_value(value) -> str:
    """
    Formata valor numérico no padrão brasileiro.
    """
    if value is None:
        return "R$ 0,00"

    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def normalizar_mes_referencia(mes_referencia: str | None) -> str | None:
    """
    Normaliza o mes para o formato MM/AAAA, que cabe na coluna VARCHAR(7).
    Aceita entradas como 05/2026, 2026-05 ou Maio/2026.
    """
    if mes_referencia is None:
        return None

    valor = str(mes_referencia).strip()
    if not valor:
        return None

    match = re.fullmatch(r"(0?[1-9]|1[0-2])[/\-](\d{4})", valor)
    if match:
        return f"{int(match.group(1)):02d}/{match.group(2)}"

    match = re.fullmatch(r"(\d{4})[/\-](0?[1-9]|1[0-2])", valor)
    if match:
        return f"{int(match.group(2)):02d}/{match.group(1)}"

    normalized = unicodedata.normalize("NFKD", valor)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", "", normalized)

    meses = {
        "janeiro": "01",
        "jan": "01",
        "fevereiro": "02",
        "fev": "02",
        "marco": "03",
        "mar": "03",
        "abril": "04",
        "abr": "04",
        "maio": "05",
        "mai": "05",
        "junho": "06",
        "jun": "06",
        "julho": "07",
        "jul": "07",
        "agosto": "08",
        "ago": "08",
        "setembro": "09",
        "set": "09",
        "outubro": "10",
        "out": "10",
        "novembro": "11",
        "nov": "11",
        "dezembro": "12",
        "dez": "12",
    }

    match = re.fullmatch(r"([a-z]+)[/\-](\d{4})", normalized)
    if match and match.group(1) in meses:
        return f"{meses[match.group(1)]}/{match.group(2)}"

    raise ValueError("Mes de referencia invalido. Use o formato MM/AAAA, exemplo: 05/2026.")


def validar_extensao_arquivo(filename: str) -> None:
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Formato de arquivo não permitido. Envie PDF, PNG, JPG, JPEG ou WEBP."
        )


def salvar_arquivo_comprovante(uploaded_file, tipo_comprovante: str) -> str:
    """
    Salva o comprovante localmente na pasta uploads/comprovantes.

    Retorna o caminho relativo do arquivo salvo.
    """
    if uploaded_file is None:
        raise ValueError("Anexe o comprovante antes de enviar.")

    original_name = getattr(uploaded_file, "filename", None) or getattr(uploaded_file, "name", None)
    validar_extensao_arquivo(original_name)

    suffix = Path(original_name).suffix.lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid4().hex[:10]

    safe_filename = f"{tipo_comprovante}_{timestamp}_{unique_id}{suffix}"
    file_path = UPLOAD_DIR / safe_filename

    with open(file_path, "wb") as file:
        if hasattr(uploaded_file, "getbuffer"):
            file.write(uploaded_file.getbuffer())
        else:
            uploaded_file.seek(0)
            file.write(uploaded_file.read())

    return str(file_path.relative_to(BASE_DIR))


def registrar_comprovante(
    tipo_comprovante: str,
    nome: str,
    cpf: str | None,
    telefone: str | None,
    mes_referencia: str | None,
    valor_informado,
    justificativa: str | None,
    uploaded_file,
) -> dict:
    """
    Registra comprovante financeiro em atendimento.comprovantes.

    Se o CPF existir em cadastro.cadastro, vincula cadastro_id.
    Se não existir, salva apenas os dados informados.
    """
    if not nome or not nome.strip():
        raise ValueError("Nome completo é obrigatório.")

    if not tipo_comprovante:
        raise ValueError("Tipo de comprovante é obrigatório.")

    valor_convertido = parse_brl_value(valor_informado)
    mes_referencia = normalizar_mes_referencia(mes_referencia)

    cpf_limpo = only_digits(cpf)
    telefone_limpo = only_digits(telefone)

    cadastro_id = None

    if cpf_limpo:
        cadastro = buscar_cadastro_por_cpf(cpf_limpo)
        if cadastro:
            cadastro_id = cadastro.get("id")

    arquivo_path = salvar_arquivo_comprovante(
        uploaded_file=uploaded_file,
        tipo_comprovante=tipo_comprovante,
    )

    return execute_returning(
        """
        INSERT INTO atendimento.comprovantes
        (
            cadastro_id,
            nome_informado,
            cpf_informado,
            telefone_informado,
            tipo_comprovante,
            mes_referencia,
            valor_informado,
            justificativa,
            arquivo_path,
            status
        )
        VALUES
        (
            :cadastro_id,
            :nome_informado,
            :cpf_informado,
            :telefone_informado,
            :tipo_comprovante,
            :mes_referencia,
            :valor_informado,
            :justificativa,
            :arquivo_path,
            'pendente'
        )
        RETURNING
            id,
            cadastro_id,
            nome_informado,
            cpf_informado,
            telefone_informado,
            tipo_comprovante,
            mes_referencia,
            valor_informado,
            justificativa,
            arquivo_path,
            status,
            created_at;
        """,
        {
            "cadastro_id": cadastro_id,
            "nome_informado": nome.strip(),
            "cpf_informado": cpf_limpo,
            "telefone_informado": telefone_limpo,
            "tipo_comprovante": tipo_comprovante,
            "mes_referencia": mes_referencia,
            "valor_informado": valor_convertido,
            "justificativa": justificativa.strip() if justificativa else None,
            "arquivo_path": arquivo_path,
        },
    )


def registrar_comprovante_mensalidade(
    nome: str,
    cpf: str | None,
    telefone: str | None,
    mes_referencia: str,
    valor_informado,
    justificativa: str | None,
    uploaded_file,
) -> dict:
    return registrar_comprovante(
        tipo_comprovante="mensalidade",
        nome=nome,
        cpf=cpf,
        telefone=telefone,
        mes_referencia=mes_referencia,
        valor_informado=valor_informado,
        justificativa=justificativa,
        uploaded_file=uploaded_file,
    )


def registrar_comprovante_contribuicao_voluntaria(
    nome: str,
    cpf: str | None,
    telefone: str | None,
    valor_informado,
    justificativa: str | None,
    uploaded_file,
) -> dict:
    return registrar_comprovante(
        tipo_comprovante="contribuicao_voluntaria",
        nome=nome,
        cpf=cpf,
        telefone=telefone,
        mes_referencia=None,
        valor_informado=valor_informado,
        justificativa=justificativa,
        uploaded_file=uploaded_file,
    )

def registrar_comprovante_pac_contribuicao(
    nome: str,
    cpf: str | None,
    telefone: str | None,
    valor_informado,
    justificativa: str | None,
    uploaded_file,
) -> dict:
    return registrar_comprovante(
        tipo_comprovante="pac_contribuicao",
        nome=nome,
        cpf=cpf,
        telefone=telefone,
        mes_referencia=None,
        valor_informado=valor_informado,
        justificativa=justificativa,
        uploaded_file=uploaded_file,
    )

def listar_comprovantes(
    tipo_comprovante: str | None = None,
    status: str | None = None,
):
    """
    Lista comprovantes para uso futuro no admin.
    """
    return run_query(
        """
        SELECT
            comp.id,
            comp.cadastro_id,
            COALESCE(c.nome, comp.nome_informado) AS nome,
            COALESCE(c.cpf, comp.cpf_informado) AS cpf,
            COALESCE(c.telefone, comp.telefone_informado) AS telefone,
            c.email,
            c.perfil,
            comp.tipo_comprovante,
            comp.mes_referencia,
            comp.valor_informado,
            comp.justificativa,
            comp.arquivo_path,
            comp.status,
            comp.observacao_admin,
            comp.created_at,
            comp.updated_at
        FROM atendimento.comprovantes comp
        LEFT JOIN cadastro.cadastro c
            ON c.id = comp.cadastro_id
        WHERE (:tipo_comprovante IS NULL OR comp.tipo_comprovante = :tipo_comprovante)
          AND (:status IS NULL OR comp.status = :status)
        ORDER BY comp.created_at DESC;
        """,
        {
            "tipo_comprovante": tipo_comprovante,
            "status": status,
        },
    )


def atualizar_status_comprovante(
    comprovante_id: int,
    status: str,
    observacao_admin: str | None = None,
) -> dict:
    """
    Atualiza status do comprovante.

    Status recomendados:
    - pendente
    - aprovado
    - recusado
    - em_analise
    """
    return execute_returning(
        """
        UPDATE atendimento.comprovantes
        SET
            status = :status,
            observacao_admin = :observacao_admin,
            updated_at = NOW()
        WHERE id = :comprovante_id
        RETURNING
            id,
            status,
            observacao_admin,
            updated_at;
        """,
        {
            "comprovante_id": comprovante_id,
            "status": status,
            "observacao_admin": observacao_admin,
        },
    )
