from __future__ import annotations

import re
from datetime import date, datetime

from db.database import execute_command, execute_returning, fetch_one, run_query
from services.cadastro_service import only_digits


UPI_ALL = {
    "curso_key": "UPI",
    "nome": "UPI (Todo Mes)",
    "limite": None,
    "data": None,
}

ATABAQUE_20260316 = {
    "curso_key": "CURSO_ATABAQUE_20260316",
    "nome": "Curso de Atabaque",
    "limite": 40,
    "data": "14/04/2026",
}

PAC_ONLY = [
    {"curso_key": "PAC_MKT_20260228", "nome": "Marketing para as empreendedoras atraves das redes sociais", "limite": None, "data": "28/02/2026"},
    ATABAQUE_20260316,
    {"curso_key": "PAC_PULSEIRAS_20260328", "nome": "Pulseiras e colares artesanais", "limite": None, "data": "28/03/2026"},
    {"curso_key": "PAC_OVOS_PASCOA_20260328", "nome": "Oficina de ovos de Pascoa", "limite": 20, "data": "28/03/2026"},
    {"curso_key": "PAC_CAIXAS_REV_20260425", "nome": "Caixas Revestidas", "limite": 30, "data": "25/04/2026"},
    {"curso_key": "PAC_IMAGEM_PESSOAL_20260425", "nome": "A beleza que nasce de dentro - Uma jornada de autoconhecimento e trabalho - Imagem pessoal", "limite": 30, "data": "25/04/2026"},
    {"curso_key": "PAC_VELAS_20260627", "nome": "Velas aromaticas", "limite": 10, "data": "27/06/2026"},
    {"curso_key": "PAC_MAQUIADORA_20260627", "nome": "Empreendedorismo: Carreira de maquiadora", "limite": 10, "data": "27/06/2026"},
    {"curso_key": "PAC_SABAO_20260725", "nome": "Oficina de sabao artesanal", "limite": 30, "data": "25/07/2026"},
    {"curso_key": "PAC_EMPREENDEDORISMO_T1_20260829", "nome": "Modulo I - Oficina de empreendedorismo - Fundamentos, autoconhecimento e desenvolvimento pessoal, criatividade e inovacao", "limite": 20, "data": "29/08/2026"},
    {"curso_key": "PAC_SOBRANCELHAS_M1_20260829", "nome": "Modulo I - Designer de sobrancelhas", "limite": 10, "data": "29/08/2026"},
    {"curso_key": "PAC_EMPREENDEDORISMO_T2_20260926", "nome": "Modulo II - Oficina de empreendedorismo - Fundamentos, autoconhecimento e desenvolvimento pessoal, criatividade e inovacao", "limite": 20, "data": "26/09/2026"},
    {"curso_key": "PAC_SOBRANCELHAS_M2_20260926", "nome": "Modulo II - Designer de sobrancelhas", "limite": 10, "data": "26/09/2026"},
    {"curso_key": "PAC_VISAGISMO_M1_20261031", "nome": "Modulo I - Visagismo", "limite": 10, "data": "31/10/2026"},
    {"curso_key": "PAC_SABAO_20261031", "nome": "Sabao artesanal", "limite": 30, "data": "31/10/2026"},
    {"curso_key": "PAC_MARCA_20261031", "nome": "Empreendedorismo: construcao de marca", "limite": 30, "data": "31/10/2026"},
    {"curso_key": "PAC_EMPREENDEDORISMO_T3_20261121", "nome": "Modulo III - Oficina de empreendedorismo - Fundamentos, autoconhecimento e desenvolvimento pessoal, criatividade e inovacao", "limite": 20, "data": "21/11/2026"},
]

FILHES_ASSIST = [
    ATABAQUE_20260316,
    {"curso_key": "FA_BELEZA_DENTRO_20260530", "nome": "A beleza que nasce de dentro - Uma jornada de autoconhecimento e trabalho", "limite": 30, "data": "30/05/2026"},
    {"curso_key": "FA_PULSEIRAS_20260627", "nome": "Pulseiras e colares artesanais", "limite": 20, "data": "27/06/2026"},
    {"curso_key": "FA_VISAGISMO_M1_20260829", "nome": "Modulo I - Visagismo", "limite": 10, "data": "29/08/2026"},
    {"curso_key": "FA_VISAGISMO_M2_20260926", "nome": "Modulo II - Visagismo", "limite": 10, "data": "26/09/2026"},
    {"curso_key": "FA_SOBRANCELHAS_M1_20261031", "nome": "Modulo I - Designer de sobrancelhas", "limite": 10, "data": "31/10/2026"},
    {"curso_key": "FA_SOBRANCELHAS_M2_20261121", "nome": "Modulo II - Designer de sobrancelhas", "limite": 10, "data": "21/11/2026"},
]

COURSE_CATALOG = {
    "pac": [UPI_ALL] + PAC_ONLY,
    "filhes": [UPI_ALL] + FILHES_ASSIST,
    "assistencia": [UPI_ALL] + FILHES_ASSIST,
}

PERFIL_LABELS = {
    "filhes": "Filhe",
    "assistencia": "Assistencia",
    "pac": "PAC - Programa Acolhe CUSLE",
}

PERFIL_ALIASES = {
    "filhe": "filhes",
    "filhes": "filhes",
    "filho": "filhes",
    "filha": "filhes",
    "filhos": "filhes",
    "filhas": "filhes",
    "assistencia": "assistencia",
    "assistência": "assistencia",
    "pac": "pac",
}


def ensure_cursos_tables() -> None:
    execute_command("CREATE SCHEMA IF NOT EXISTS cadastro;")
    execute_command(
        """
        CREATE TABLE IF NOT EXISTS cadastro.cadastro_curso (
            id SERIAL PRIMARY KEY,
            cadastro_id INTEGER NOT NULL REFERENCES cadastro.cadastro(id) ON DELETE CASCADE,
            curso_key VARCHAR(80) NOT NULL,
            curso_nome TEXT NOT NULL,
            data_turma DATE NULL,
            vagas_limite INTEGER NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );
        """
    )
    execute_command(
        """
        CREATE INDEX IF NOT EXISTS idx_cadastro_curso_cadastro_id
            ON cadastro.cadastro_curso (cadastro_id);
        """
    )
    execute_command(
        """
        CREATE INDEX IF NOT EXISTS idx_cadastro_curso_curso_key
            ON cadastro.cadastro_curso (curso_key);
        """
    )


def parse_date_br(date_str: str | None) -> date | None:
    if not date_str:
        return None
    return datetime.strptime(date_str, "%d/%m/%Y").date()


def parse_date_iso(date_str: str | None) -> date | None:
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def parse_date_br_flexible(date_str: str | None) -> date | None:
    if not date_str:
        return None
    value = re.sub(r"\s+", "", str(date_str).strip())
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(value, fmt).date()
            if parsed.year < 100:
                return date(parsed.year + 2000, parsed.month, parsed.day)
            return parsed
        except ValueError:
            pass
    return None


def is_valid_email_basic(email: str | None) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (email or "").strip()))


def is_valid_cpf_basic(cpf: str | None) -> bool:
    digits = only_digits(cpf)
    if not digits or len(digits) != 11:
        return False
    return digits != digits[0] * 11


def is_valid_phone_basic(phone: str | None) -> bool:
    digits = only_digits(phone)
    return bool(digits and len(digits) in (10, 11))


def is_valid_birth_date(value) -> bool:
    if not value:
        return False
    parsed = value if isinstance(value, date) else parse_date_iso(str(value))
    today = date.today()
    return parsed <= today and today.year - parsed.year <= 120


def sort_courses_keep_upi_first(courses: list[dict]) -> list[dict]:
    upi = [c for c in courses if c.get("curso_key") == "UPI"]
    rest = [c for c in courses if c.get("curso_key") != "UPI"]
    return upi + sorted(
        rest,
        key=lambda c: (
            parse_date_br_flexible(c.get("data")) is None,
            parse_date_br_flexible(c.get("data")) or date(9999, 12, 31),
            (c.get("nome") or "").lower(),
        ),
    )


def build_course_label(course: dict) -> str:
    return (course.get("nome") or "").strip().upper()


def find_course(perfil: str | None, curso_key: str | None) -> dict | None:
    for course in COURSE_CATALOG.get(normalizar_perfil(perfil) or "", []):
        if course.get("curso_key") == curso_key:
            return course
    return None


def normalizar_perfil(perfil: str | None) -> str | None:
    value = (perfil or "").strip().lower()
    return PERFIL_ALIASES.get(value, value or None)


def _counts_by_course() -> dict[str, int]:
    ensure_cursos_tables()
    df = run_query(
        """
        SELECT curso_key, COUNT(id) AS total
        FROM cadastro.cadastro_curso
        GROUP BY curso_key;
        """
    )
    if df.empty:
        return {}
    return {str(row["curso_key"]): int(row["total"]) for _, row in df.iterrows()}


def catalogo_para_ui() -> dict[str, list[dict]]:
    counts = _counts_by_course()
    catalog_for_ui = {}
    for perfil, cursos in COURSE_CATALOG.items():
        catalog_for_ui[perfil] = []
        for course in sort_courses_keep_upi_first(cursos):
            limite = course.get("limite")
            atual = counts.get(course["curso_key"], 0)
            catalog_for_ui[perfil].append(
                {
                    "curso_key": course["curso_key"],
                    "label": build_course_label(course),
                    "data": course.get("data"),
                    "disponivel": True if limite is None else atual < limite,
                }
            )
    return catalog_for_ui


def listar_inscricoes_cadastro(cadastro_id: int) -> list[dict]:
    ensure_cursos_tables()
    df = run_query(
        """
        SELECT id, curso_key, curso_nome, data_turma, vagas_limite, created_at
        FROM cadastro.cadastro_curso
        WHERE cadastro_id = :cadastro_id
        ORDER BY data_turma ASC NULLS LAST, curso_nome ASC;
        """,
        {"cadastro_id": cadastro_id},
    )
    if df.empty:
        return []
    clean = df.where(df.notna(), None)
    return clean.to_dict(orient="records")


def _count_registrations_for_course(curso_key: str) -> int:
    row = fetch_one(
        """
        SELECT COUNT(id) AS total
        FROM cadastro.cadastro_curso
        WHERE curso_key = :curso_key;
        """,
        {"curso_key": curso_key},
    )
    return int(row.get("total") or 0) if row else 0


def _cadastro_already_registered(cadastro_id: int, curso_key: str) -> bool:
    row = fetch_one(
        """
        SELECT id
        FROM cadastro.cadastro_curso
        WHERE cadastro_id = :cadastro_id
          AND curso_key = :curso_key
        LIMIT 1;
        """,
        {"cadastro_id": cadastro_id, "curso_key": curso_key},
    )
    return bool(row)


def _update_cadastro_curso_flags(cadastro_id: int, participa: bool, perfil: str | None) -> None:
    execute_command(
        """
        UPDATE cadastro.cadastro
        SET
            participa_curso = :participa_curso,
            perfil = COALESCE(NULLIF(:perfil, ''), perfil)
        WHERE id = :cadastro_id;
        """,
        {"cadastro_id": cadastro_id, "participa_curso": participa, "perfil": perfil},
    )


def registrar_cursos(cadastro: dict, form) -> list[dict]:
    ensure_cursos_tables()
    cadastro_id = cadastro.get("id")
    if not cadastro_id:
        raise ValueError("Cadastro oficial nao encontrado.")

    nome = cadastro.get("nome") or (form.get("nome") or "").strip()
    email = cadastro.get("email") or (form.get("email") or "").strip()
    telefone = cadastro.get("telefone") or form.get("telefone")
    cpf = cadastro.get("cpf") or form.get("cpf")
    data_nascimento = cadastro.get("data_nascimento") or form.get("data_nascimento")
    menor_raw = (form.get("menor_idade") or "").strip()
    perfil = normalizar_perfil(form.get("perfil") or cadastro.get("perfil"))
    participa = (form.get("participa") or "").strip()
    curso_keys = list(dict.fromkeys([key.strip() for key in form.getlist("curso") if key.strip()]))

    if not nome:
        raise ValueError("Preencha seu nome.")
    if not is_valid_email_basic(email):
        raise ValueError("E-mail invalido. Verifique e tente novamente.")
    if not is_valid_phone_basic(telefone):
        raise ValueError("Telefone invalido. Informe com DDD.")
    if not is_valid_cpf_basic(cpf):
        raise ValueError("CPF invalido. Verifique e tente novamente.")
    if not is_valid_birth_date(data_nascimento):
        raise ValueError("Data de nascimento invalida. Verifique e tente novamente.")

    if menor_raw not in ("sim", "nao"):
        raise ValueError("Informe se voce e menor de idade.")
    if menor_raw == "sim":
        responsavel_nome = cadastro.get("responsavel_nome") or (form.get("responsavel_nome") or "").strip()
        responsavel_cpf = cadastro.get("responsavel_cpf") or form.get("responsavel_cpf")
        if not responsavel_nome:
            raise ValueError("Preencha o nome do responsavel.")
        if not is_valid_cpf_basic(responsavel_cpf):
            raise ValueError("CPF do responsavel invalido. Verifique e tente novamente.")

    if participa not in ("sim", "nao"):
        raise ValueError("Informe se deseja participar de algum curso.")
    if perfil not in COURSE_CATALOG:
        raise ValueError("Selecione seu perfil.")

    participa_bool = participa == "sim"
    _update_cadastro_curso_flags(int(cadastro_id), participa_bool, perfil)
    if not participa_bool:
        return []

    if not curso_keys:
        raise ValueError("Selecione pelo menos 1 curso.")

    cursos_para_salvar = []
    for curso_key in curso_keys:
        course = find_course(perfil, curso_key)
        if not course:
            raise ValueError("Um dos cursos selecionados nao e valido para o seu perfil.")

        if _cadastro_already_registered(int(cadastro_id), course["curso_key"]):
            raise ValueError(f"Voce ja esta inscrito no curso '{course['nome']}'.")

        limite = course.get("limite")
        if limite is not None and _count_registrations_for_course(course["curso_key"]) >= limite:
            raise ValueError(f"O curso '{course['nome']}' esta indisponivel no momento.")

        cursos_para_salvar.append(course)

    saved = []
    for course in cursos_para_salvar:
        saved.append(
            execute_returning(
                """
                INSERT INTO cadastro.cadastro_curso
                    (cadastro_id, curso_key, curso_nome, data_turma, vagas_limite)
                VALUES
                    (:cadastro_id, :curso_key, :curso_nome, :data_turma, :vagas_limite)
                RETURNING id, cadastro_id, curso_key, curso_nome, data_turma, vagas_limite, created_at;
                """,
                {
                    "cadastro_id": int(cadastro_id),
                    "curso_key": course["curso_key"],
                    "curso_nome": course["nome"],
                    "data_turma": parse_date_br(course.get("data")) if course.get("data") else None,
                    "vagas_limite": course.get("limite"),
                },
            )
        )

    return saved
