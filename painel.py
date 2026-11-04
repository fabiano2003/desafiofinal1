"""Leitura e apresentação pura dos marts usados pelo painel.

A função ler executa somente SELECT * em cada mart solicitado, pois a lógica
de negócio deve estar nos arquivos SQL e o painel não deve inventar métricas.
Ela abre DuckDB em modo somente leitura e fecha a conexão dentro da função,
liberando o arquivo para que pipeline.marts possa gravar enquanto o painel
está em execução. Erros de mart ausente são reunidos e informados para que a
página possa orientar a recriação dos marts.

As funções reais e numero formatam valores sem depender do locale da máquina,
mantendo separadores brasileiros. Cada gráfico tem sua própria função e
recebe um DataFrame pronto: pode ordenar e limitar às dez maiores linhas, mas
nunca agrega dados. O setor das tabelas de ação é renomeado para uma grafia
legível porque o nome atualmente gravado no banco contém um caractere de
substituição no lugar da letra acentuada.
"""

import duckdb
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure


class MartsAusentesError(Exception):
    """Indica quais tabelas de mart não foram encontradas no banco."""

    def __init__(self, marts: list[str]):
        self.marts = marts
        super().__init__(", ".join(marts))


def ler(marts: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    """Lê cada mart solicitado e fecha a conexão mesmo quando há erro."""
    con = duckdb.connect("olist.duckdb", read_only=True)
    dados = {}
    ausentes = []

    try:
        for nome in marts:
            try:
                dados[nome] = con.execute(f"SELECT * FROM marts.{nome}").df()
            except duckdb.CatalogException:
                ausentes.append(nome)
    finally:
        con.close()

    if ausentes:
        raise MartsAusentesError(ausentes)

    for nome in ("total_emp_setor_prim", "total_emp_setor_sec"):
        if nome in dados:
            colunas_setor = [
                coluna
                for coluna in dados[nome].columns
                if coluna.startswith("SETOR_RESPONS") and coluna.endswith("VEL")
            ]
            if colunas_setor:
                dados[nome] = dados[nome].rename(
                    columns={colunas_setor[0]: "SETOR_RESPONSAVEL"}
                )

    return dados


def reais(valor, casas=2) -> str:
    """Formata um valor monetário com separadores brasileiros."""
    formatado = f"{valor:,.{casas}f}"
    formatado = formatado.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return f"R$ {formatado}"


def numero(valor, casas=0) -> str:
    """Formata um número com separadores brasileiros."""
    formatado = f"{valor:,.{casas}f}"
    return formatado.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _grafico_barras(
    dados: pd.DataFrame,
    coluna_valor: str,
    colunas_rotulo: tuple[str, ...],
) -> Figure:
    top = dados.sort_values(coluna_valor, ascending=False).head(10).copy()

    if len(colunas_rotulo) == 1:
        coluna_categoria = colunas_rotulo[0]
    else:
        coluna_categoria = "_CATEGORIA_GRAFICO"
        top[coluna_categoria] = top[colunas_rotulo[0]].astype(str).str.cat(
            top[colunas_rotulo[1]].astype(str),
            sep=" · ",
        )

    figura = px.bar(
        top,
        x=coluna_valor,
        y=coluna_categoria,
        orientation="h",
        color_discrete_sequence=["#1f4e79"],
    )
    figura.update_layout(
        xaxis_title="Valor (R$)",
        yaxis_title=None,
        showlegend=False,
        height=320,
        margin={"l": 4, "r": 8, "t": 8, "b": 38},
    )
    figura.update_yaxes(autorange="reversed")
    return figura


def grafico_setor_prim(dados: pd.DataFrame) -> Figure:
    """Cria o gráfico das dez maiores combinações da UG primária."""
    return _grafico_barras(
        dados,
        "TOTAL_RECURSOS_EMPENHADOS_POR_SETOR",
        ("ACAO_ORCAMENTARIA", "SETOR_RESPONSAVEL"),
    )


def grafico_setor_sec(dados: pd.DataFrame) -> Figure:
    """Cria o gráfico das dez maiores combinações da UG secundária."""
    return _grafico_barras(
        dados,
        "TOTAL_RECURSOS_EMPENHADOS_POR_SETOR",
        ("ACAO_ORCAMENTARIA", "SETOR_RESPONSAVEL"),
    )


def grafico_emp_pi(dados: pd.DataFrame) -> Figure:
    """Cria o gráfico dos dez maiores totais empenhados por PI."""
    return _grafico_barras(dados, "TOTAL_EMPENHADO", ("PLANO_INTERNO",))


def grafico_insc_pi(dados: pd.DataFrame) -> Figure:
    """Cria o gráfico dos dez maiores totais inscritos por PI."""
    return _grafico_barras(dados, "TOTAL_EMPENHADO", ("PLANO_INTERNO",))


def grafico_modalidade(dados: pd.DataFrame) -> Figure:
    """Cria o gráfico dos dez maiores totais por modalidade."""
    return _grafico_barras(dados, "TOTAL_EMPENHADO", ("MODALIDADE",))
