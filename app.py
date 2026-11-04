"""Página Streamlit para explorar os marts de empenhos."""

from pathlib import Path

import duckdb
import streamlit as st

import painel

_MARTS = (
    "ne_com_saldo",
    "total_emp_ug_prim",
    "total_emp_ug_sec",
    "total_emp_ug_prim25",
    "total_emp_ug_sec25",
    "total_emp_setor_prim",
    "total_emp_setor_sec",
    "total_emp_pi",
    "total_insc_pi",
    "total_emp_mod",
)

st.set_page_config(
    page_title="7ºBECmb - Gestão de Recursos",
    layout="wide",
)

cabecalho, controles = st.columns([1.2, 2.0], vertical_alignment="center")
with cabecalho:
    st.caption("EXECUÇÃO ORÇAMENTÁRIA · EXERCÍCIO 2026")
    st.title("7ºBECmb - Gestão de Recursos")
with controles:
    filtro_setor_slot, filtro_plano_slot, recarregar_slot = st.columns(
        [1, 1, 0.6],
        vertical_alignment="bottom",
    )
    filtro_setor_slot = filtro_setor_slot.empty()
    filtro_plano_slot = filtro_plano_slot.empty()
    recarregar = recarregar_slot.button(
        "Recarregar dados",
        icon=":material/refresh:",
        width="stretch",
    )
    legenda_filtros = st.empty()

if not Path("olist.duckdb").is_file():
    st.error(
        "Banco olist.duckdb não encontrado. Execute "
        "`uv run python -m pipeline.marts` para criá-lo e carregar os marts."
    )
    st.stop()


@st.cache_data(show_spinner="Carregando os dados do painel...")
def carregar_dados():
    return painel.ler(_MARTS)

if recarregar:
    st.cache_data.clear()

try:
    dados = carregar_dados()
except painel.MartsAusentesError as exc:
    st.error(
        f"Marts ausentes: {', '.join(exc.marts)}. Execute "
        "`uv run python -m pipeline.marts`."
    )
    st.stop()
except (duckdb.Error, OSError) as exc:
    st.error(f"Não foi possível carregar os dados: {exc}")
    st.stop()

ne_saldo = dados["ne_com_saldo"]
setores = tuple(sorted(ne_saldo["SETOR_REPONSAVEL"].dropna().unique()))
planos = tuple(sorted(ne_saldo["PLANO_INTERNO"].dropna().unique()))

intervalo_setor = filtro_setor_slot.select_slider(
    "Setor responsável",
    options=setores,
    value=(setores[0], setores[-1]),
    key="filtro_setor",
)
intervalo_plano = filtro_plano_slot.select_slider(
    "Plano interno",
    options=planos,
    value=(planos[0], planos[-1]),
    key="filtro_plano",
)
legenda_filtros.caption("os cartões valem para o período inteiro")


def _alternar_tabela(chave: str, rotulo: str):
    expandida = st.session_state.get(chave, False)
    if st.button(
        "Mostrar menos" if expandida else rotulo,
        key=f"botao_{chave}",
        width="stretch",
    ):
        st.session_state[chave] = not expandida
    return st.session_state.get(chave, False)


def _mostrar_tabela(
    dados_tabela,
    chave: str,
    linhas_iniciais: int,
    rotulo: str,
    alt: str,
    moeda: tuple[str, ...] = (),
    inteiros: tuple[str, ...] = (),
):
    expandida = _alternar_tabela(chave, rotulo)

    tabela = dados_tabela.copy()
    for coluna in moeda:
        tabela[coluna] = tabela[coluna].map(painel.reais)
    for coluna in inteiros:
        tabela[coluna] = tabela[coluna].map(painel.numero)

    if not expandida:
        tabela = tabela.head(linhas_iniciais)
    st.dataframe(tabela, hide_index=True, width="stretch", alt=alt)


def _intervalo_completo(intervalo, opcoes):
    return intervalo == (opcoes[0], opcoes[-1])


ne_filtrado = ne_saldo
if not _intervalo_completo(intervalo_setor, setores):
    ne_filtrado = ne_filtrado[
        ne_filtrado["SETOR_REPONSAVEL"].between(
            intervalo_setor[0], intervalo_setor[1], inclusive="both"
        )
    ]
if not _intervalo_completo(intervalo_plano, planos):
    ne_filtrado = ne_filtrado[
        ne_filtrado["PLANO_INTERNO"].between(
            intervalo_plano[0], intervalo_plano[1], inclusive="both"
        )
    ]
ne_filtrado = ne_filtrado.sort_values(
    ["SETOR_REPONSAVEL", "DIAS"],
    ascending=[True, True],
)

st.divider()
metricas = st.columns(4)
with metricas[0]:
    st.metric(
        "Empenhado UG Primária",
        painel.reais(dados["total_emp_ug_prim"].iloc[0]["TOTAL_RECURSOS_EMPENHADOS"]),
    )
    st.caption("Saldo a liquidar + em liquidação + liquidado + pago.")
with metricas[1]:
    st.metric(
        "Empenhado UG Secundária",
        painel.reais(
            dados["total_emp_ug_sec"].iloc[0]["TOTAL_RECURSOS_EMPENHADOS_na167"]
        ),
    )
    st.caption("Saldo a liquidar + em liquidação + liquidado + pago.")
with metricas[2]:
    st.metric(
        "RP Inscrito - UG Primária",
        painel.reais(
            dados["total_emp_ug_prim25"].iloc[0]["TOTAL_RECURSOS_EMPENHADOS_2025"]
        ),
    )
    st.caption("Total inscrito no ano anterior.")
with metricas[3]:
    st.metric(
        "RP Inscrito - UG Secundária",
        painel.reais(
            dados["total_emp_ug_sec25"].iloc[0][
                "TOTAL_RECURSOS_EMPENHADOS_2025_UG167"
            ]
        ),
    )
    st.caption("Total inscrito no ano anterior.")

with st.container(border=True):
    st.subheader("NE com saldo a liquidar por setor responsável")
    _mostrar_tabela(
        ne_filtrado,
        "ne_saldo_expandida",
        15,
        "Mostrar restante da tabela",
        "NE com saldo a liquidar, filtradas por setor e plano interno",
        moeda=("SALDO_NE",),
        inteiros=("UG", "ND", "DIAS"),
    )

configuracao_graficos = (
    (
        "total_emp_setor_prim",
        "UG primária · Empenhos por ação e setor",
        painel.grafico_setor_prim,
        "setor_prim_expandido",
        ("TOTAL_RECURSOS_EMPENHADOS_POR_SETOR",),
    ),
    (
        "total_emp_setor_sec",
        "UG secundária · Empenhos por ação e setor",
        painel.grafico_setor_sec,
        "setor_sec_expandido",
        ("TOTAL_RECURSOS_EMPENHADOS_POR_SETOR",),
    ),
    (
        "total_emp_pi",
        "Empenhado por Plano Interno",
        painel.grafico_emp_pi,
        "emp_pi_expandido",
        ("TOTAL_EMPENHADO",),
    ),
    (
        "total_insc_pi",
        "RP inscrito por Plano Interno",
        painel.grafico_insc_pi,
        "insc_pi_expandido",
        ("TOTAL_EMPENHADO",),
    ),
    (
        "total_emp_mod",
        "Empenhado por modalidade de licitação",
        painel.grafico_modalidade,
        "modalidade_expandida",
        ("TOTAL_EMPENHADO",),
    ),
)

colunas_graficos = st.columns(5)
for coluna, (nome, titulo, funcao_grafico, chave, colunas_moeda) in zip(
    colunas_graficos,
    configuracao_graficos,
):
    with coluna, st.container(border=True):
        st.markdown(f"**{titulo}**")
        grafico = funcao_grafico(dados[nome])
        st.plotly_chart(
            grafico,
            width="stretch",
            alt=titulo,
        )
        linhas = dados[nome].sort_values(
            colunas_moeda[0],
            ascending=False,
        )
        _mostrar_tabela(
            linhas,
            chave,
            4,
            "Mostrar restante da tabela",
            f"Dados de {titulo}",
            moeda=colunas_moeda,
        )
