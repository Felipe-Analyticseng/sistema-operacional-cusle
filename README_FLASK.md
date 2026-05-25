# Sistema CUSLE — Refatoração Flask

Esta versão remove a camada Streamlit e mantém as regras de negócio em `services/`, com Flask + HTML/CSS/JS para o portal público e o painel administrativo.

## Rodar localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python wsgi.py
```

## Estrutura

```text
app/
  routes/           # blueprints user/admin/api
  templates/        # HTML organizado por área
  static/css        # layout e dashboards
  static/js         # máscaras, formulários dinâmicos e gráficos
services/           # regras de negócio preservadas
sql/                # scripts incrementais
uploads/            # comprovantes
```

## Rotas principais

- `/` portal público
- `/pac` menu PAC
- `/pac/cadastro` cadastro assistido
- `/pac/apadrinhamento` apadrinhamento
- `/financeiro/<tipo>` mensalidade, contribuição voluntária ou contribuição PAC
- `/limpeza` registro de limpeza
- `/admin/login` login administrativo
- `/admin` dashboard executivo
- `/admin/pac` dashboard PAC
- `/admin/comprovantes` financeiro/comprovantes
- `/admin/limpeza` limpeza
- `/admin/faltas` faltas

## Observações

- A lógica de banco foi preservada nas tabelas `cadastro.cadastro`, `cadastro._pac_criancas`, `atendimento.comprovantes`, `atendimento.limpeza_registros`, `atendimento.pac_solicitacoes` e `public.faltas`.
- A autenticação usa `ADMIN_USERS` no `.env`.
- O dashboard usa Chart.js via CDN no template. Para ambiente totalmente offline, baixe o arquivo e coloque em `app/static/js/vendor/`.
