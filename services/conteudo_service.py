# services/conteudo_service.py

from datetime import date, datetime
from zoneinfo import ZoneInfo

from db.database import fetch_one


GIRAS_PRESENCIAIS = [
    (date(2026, 5, 30), "Gira de Preto Velho"),
    (date(2026, 6, 6), "Gira Festa Cigana"),
    (date(2026, 6, 27), "Gira de Caboclo, Boiadeiro e Légua"),
    (date(2026, 7, 11), "Gira de Bahia e Marinheiro"),
    (date(2026, 8, 29), "Gira de Preto Velho e Kimbandeiros"),
    (date(2026, 9, 26), "Gira Festa de Erê"),
    (date(2026, 10, 31), "Gira de Exú e Pombagira"),
    (date(2026, 11, 7), "Gira Festa Sr. Zé / Gira de Malandro"),
    (date(2026, 11, 21), "Gira Mista"),
    (date(2026, 12, 5), "Gira de Encerramento da Esquerda — Exú e Pombagira"),
]


def _datas_giras_futuras() -> str:
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    linhas = [
        f"{data_gira.strftime('%d/%m')} — {nome}"
        for data_gira, nome in GIRAS_PRESENCIAIS
        if data_gira >= hoje
    ]
    if not linhas:
        return "No momento, não há datas futuras configuradas."
    return "\n".join(linhas)


def _conteudo_medicina_menu() -> dict:
    return {
        "titulo": "Medicina Ancestral",
        "conteudo": f"""
A Medicina Ancestral não realiza diagnósticos médicos e não promete curas milagrosas. Trata-se de um tratamento espiritual complementar, conduzido com responsabilidade, fé e respeito à caminhada de cada pessoa.

Como funciona?

O tratamento é individual, ou seja, ninguém pode receber por outra pessoa. Cada pessoa indicada é acolhida espiritualmente conforme sua própria necessidade.

Durante o trabalho, a espiritualidade se encarrega de direcionar a energia necessária para cada caso. O corpo mediúnico preparado para o tratamento se coloca à disposição, doando sua energia para que a espiritualidade transforme, conduza e entregue aquilo que for permitido e necessário a cada pessoa indicada.

Tratamento à distância

Todas as segundas-feiras, o corpo mediúnico recebe a lista com o nome completo e a data de nascimento de cada pessoa indicada. A partir disso, todos se conectam espiritualmente para a realização do tratamento à distância.

Tratamento presencial

O tratamento presencial acontece sempre nos dias de gira, antes do início dos trabalhos, às 14h30.

Datas das giras presenciais:

{_datas_giras_futuras()}

Com fé, respeito e responsabilidade, seguimos colocando a espiritualidade a serviço do bem, sempre compreendendo que cada tratamento acontece conforme o merecimento, a permissão e a necessidade de cada um.
        """,
    }


def _conteudo_assistencia_menu() -> dict:
    destaque = "Evite roupas curtas e roupas pretas, dando preferência a roupas claras, confortáveis e respeitosas para o ambiente espiritual."
    return {
        "titulo": "Assistência nas Giras",
        "destaque": destaque,
        "conteudo": f"""
A assistência é destinada às pessoas que desejam participar da gira para receber uma consulta espiritual com os médiuns da casa.

Pedimos que todos cheguem com antecedência média de 30 minutos antes do início da gira, para que seja possível informar o nome na recepção, organizar a lista de atendimento e aguardar o momento de ser chamado.

É importante que cada pessoa aguarde com calma, respeito e silêncio, mantendo o ambiente harmonioso para o bom andamento dos trabalhos espirituais.

Pedimos também, com carinho e respeito, que sejam evitadas roupas muito curtas e roupas pretas, prezando por uma vestimenta adequada ao ambiente espiritual e à energia dos trabalhos da casa.

As consultas acontecem conforme a organização da casa e a condução da espiritualidade. Por isso, pedimos compreensão, paciência e respeito aos médiuns, cambones e responsáveis pela gira.

Datas das giras:

{_datas_giras_futuras()}

Orientações importantes:
Chegue com antecedência, informe seu nome na chegada e aguarde ser chamado para o atendimento.

{destaque}

Que todos sejam recebidos com respeito, fé e acolhimento, sempre dentro da ordem e da condução espiritual da casa.
        """,
    }


DYNAMIC_CONTENT = {
    "medicina_menu": _conteudo_medicina_menu,
    "assistencia_menu": _conteudo_assistencia_menu,
}


DEFAULT_CONTENT = {
    "medicina_menu": {
        "titulo": "Medicina Ancestral",
        "conteudo": """
A Medicina Ancestral não realiza diagnósticos médicos e não promete curas milagrosas. Trata-se de um tratamento espiritual complementar, conduzido com responsabilidade, fé e respeito à caminhada de cada pessoa.

Como funciona?

O tratamento é individual, ou seja, ninguém pode receber por outra pessoa. Cada pessoa indicada é acolhida espiritualmente conforme sua própria necessidade.

Durante o trabalho, a espiritualidade se encarrega de direcionar a energia necessária para cada caso. O corpo mediúnico preparado para o tratamento se coloca à disposição, doando sua energia para que a espiritualidade transforme, conduza e entregue aquilo que for permitido e necessário a cada pessoa indicada.

Tratamento à distância

Todas as segundas-feiras, o corpo mediúnico recebe a lista com o nome completo e a data de nascimento de cada pessoa indicada. A partir disso, todos se conectam espiritualmente para a realização do tratamento à distância.

Tratamento presencial

O tratamento presencial acontece sempre nos dias de gira, antes do início dos trabalhos, às 14h30.

Datas das giras presenciais:

30/05 — Gira de Preto Velho
06/06 — Gira Festa Cigana
27/06 — Gira de Caboclo, Boiadeiro e Légua
11/07 — Gira de Bahia e Marinheiro
29/08 — Gira de Preto Velho e Kimbandeiros
26/09 — Gira Festa de Erê
31/10 — Gira de Exú e Pombagira
07/11 — Gira Festa Sr. Zé / Gira de Malandro
21/11 — Gira Mista
05/12 — Gira de Encerramento da Esquerda — Exú e Pombagira

Com fé, respeito e responsabilidade, seguimos colocando a espiritualidade a serviço do bem, sempre compreendendo que cada tratamento acontece conforme o merecimento, a permissão e a necessidade de cada um.
        """,
    },
    "medicina_dias_horarios": {
        "titulo": "Dias e horários presenciais",
        "conteudo": """
Os dias e horários presenciais devem ser confirmados com a organização da casa antes da participação.

Em caso de dúvida, procure uma pessoa responsável pela organização da atividade.
        """,
    },
    "medicina_preparo": {
        "titulo": "Preparo para participar presencialmente",
        "conteudo": """
Para participar presencialmente, siga as orientações passadas pela casa.

Recomenda-se chegar com antecedência, manter postura respeitosa e seguir as instruções da equipe responsável.
        """,
    },
    "medicina_indicacao": {
        "titulo": "Como indicar pessoas para o trabalho",
        "conteudo": """
Caso deseje indicar uma pessoa para participar do trabalho, converse antes com a organização responsável.

A indicação deve ser feita com cuidado, responsabilidade e respeito aos critérios da casa.
        """,
    },
    "assistencia_menu": {
        "titulo": "Assistência / Redes Sociais",
        "conteudo": """
Este espaço é voltado para pessoas da assistência, pessoas que conheceram a casa pelas redes sociais ou por indicação.
        """,
    },
    "assistencia_proximas_giras": {
        "titulo": "Próximas giras",
        "conteudo": """
As próximas giras serão informadas pelos canais oficiais da casa.

Acompanhe as orientações da organização e confirme as informações antes de se deslocar.
        """,
    },
    "assistencia_atendimento": {
        "titulo": "Como passar em atendimento",
        "conteudo": """
Para passar em atendimento, siga as orientações da casa no dia da gira.

A organização poderá informar horários, ordem de chegada e demais orientações necessárias.
        """,
    },
    "assistencia_contribuicao": {
        "titulo": "Contribuição para o terreiro",
        "conteudo": """
As contribuições ajudam na manutenção da casa e das atividades realizadas.

Caso deseje contribuir, utilize a opção de contribuição voluntária disponível no portal.
        """,
    },
    "assistencia_filho_casa": {
        "titulo": "Como se tornar filho(a) da casa",
        "conteudo": """
Caso tenha interesse em se aproximar da casa, procure orientação presencialmente com a liderança responsável.

Esse processo deve ser feito com respeito, tempo, presença e orientação adequada.
        """,
    },
    "cursos_menu": {
        "titulo": "Cursos CUSLE",
        "conteudo": """
Este espaço reúne informações sobre cursos, cronogramas e envio de comprovantes relacionados às atividades formativas da casa.
        """,
    },
    "cursos_informacoes": {
        "titulo": "Informações sobre os cursos",
        "conteudo": """
As informações dos cursos serão divulgadas conforme calendário da casa.

Acompanhe os canais oficiais e siga as orientações de inscrição e participação.
        """,
    },
    "cursos_comprovante": {
        "titulo": "Comprovante de pagamento da cesta básica",
        "conteudo": """
Quando solicitado, o comprovante relacionado à cesta básica deverá ser enviado pelo fluxo específico de cursos.

Esse fluxo será conectado ao financeiro para conferência.
        """,
    },
    "cursos_cronograma": {
        "titulo": "Cronograma do curso",
        "conteudo": """
O cronograma do curso será informado pela organização responsável.

Confirme sempre datas, horários e local antes de participar.
        """,
    },
    "pac_parcerias": {
        "titulo": "Parcerias PAC",
        "conteudo": """
O PAC pode receber apoio por meio de parcerias com pessoas, grupos ou instituições alinhadas ao propósito do programa.

Caso tenha interesse em apoiar, entre em contato com a coordenação responsável.
        """,
    },
    "pac_apadrinhamentos": {
        "titulo": "Apadrinhamentos",
        "conteudo": """
O apadrinhamento é uma forma de apoiar pessoas ou famílias acompanhadas pelo Programa Acolhe CUSLE.

A coordenação do PAC orientará como participar de forma organizada e responsável.
        """,
    },
    "pac_cesta_basica": {
        "titulo": "Doação de cesta básica",
        "conteudo": """
A doação de cesta básica apoia diretamente as ações de acolhimento do PAC.

As necessidades e orientações de entrega devem ser confirmadas com a coordenação responsável.
        """,
    },
}


def obter_conteudo(categoria: str) -> dict:
    """
    Busca conteúdo ativo em atendimento.conteudos_informativos.
    Se não existir, retorna conteúdo padrão do sistema.
    """

    if categoria in DYNAMIC_CONTENT:
        default = DYNAMIC_CONTENT[categoria]()
        return {
            "titulo": default["titulo"],
            "conteudo": default["conteudo"],
            "destaque": default.get("destaque"),
            "fonte": "padrao",
        }

    row = fetch_one(
        """
        SELECT
            titulo,
            conteudo
        FROM atendimento.conteudos_informativos
        WHERE categoria = :categoria
          AND ativo = TRUE
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 1;
        """,
        {"categoria": categoria},
    )

    if row:
        return {
            "titulo": row.get("titulo"),
            "conteudo": row.get("conteudo"),
            "destaque": None,
            "fonte": "banco",
        }

    default = DEFAULT_CONTENT.get(
        categoria,
        {
            "titulo": "Informação",
            "conteudo": "Conteúdo ainda não configurado.",
        },
    )

    return {
        "titulo": default["titulo"],
        "conteudo": default["conteudo"],
        "destaque": default.get("destaque"),
        "fonte": "padrao",
    }
