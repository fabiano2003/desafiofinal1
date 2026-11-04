"""Gera um relatório HTML estático a partir dos marts existentes.

O relatório usa painel.ler() para ler os marts, os formatadores de painel.py
para apresentar valores e as mesmas cinco funções para criar gráficos. Não
importa Streamlit, não consulta o banco diretamente e não cria gráficos nem
métricas fora do app existente; assim, a regra de negócio continua nos SQLs.

O HTML reúne as quatro faixas do app, na mesma ordem: cabeçalho, quatro
indicadores, tabela de NE com saldo e cinco gráficos com suas tabelas
auxiliares. O resultado é um único arquivo, com cartões HTML simples e Plotly
embutido por divs; o JavaScript da biblioteca vem do CDN uma única vez.
Cada gráfico recebe um div_id estável para que uma execução com os mesmos
dados não troque os identificadores dos gráficos.

O relatório não tem filtros e mostra o conjunto inteiro atualmente lido pelo
app, inclusive os limites iniciais de 15 linhas da tabela de NE e quatro
linhas das tabelas auxiliares. Não há filtro de faturamento ou de período,
pois não existe esse mart na tela atual. O rodapé registra data e hora da
geração: o HTML é estático e não consulta o banco ao ser aberto.
"""

from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import plotly.io as pio

import painel

_RAIZ = Path(__file__).resolve().parent
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


def _texto(valor) -> str:
    if pd.isna(valor):
        return ""
    return escape(str(valor))


def _tabela_html(
    dados: pd.DataFrame,
    *,
    moeda: tuple[str, ...] = (),
    inteiros: tuple[str, ...] = (),
) -> str:
    tabela = dados.copy()
    for coluna in moeda:
        tabela[coluna] = tabela[coluna].map(painel.reais)
    for coluna in inteiros:
        tabela[coluna] = tabela[coluna].map(painel.numero)

    cabecalhos = "".join(f"<th>{_texto(coluna)}</th>" for coluna in tabela.columns)
    linhas = []
    for valores in tabela.itertuples(index=False, name=None):
        celulas = "".join(f"<td>{_texto(valor)}</td>" for valor in valores)
        linhas.append(f"<tr>{celulas}</tr>")
    corpo = "".join(linhas)
    return (
        '<div class="table-wrap"><table><thead><tr>'
        f"{cabecalhos}</tr></thead><tbody>{corpo}</tbody></table></div>"
    )


def _cartao(titulo: str, valor: str, descricao: str) -> str:
    return (
        '<article class="card">'
        f"<p class=\"card-label\">{_texto(titulo)}</p>"
        f"<p class=\"card-value\">{_texto(valor)}</p>"
        f"<p class=\"card-description\">{_texto(descricao)}</p>"
        "</article>"
    )


def _grafico_html(figura, div_id: str, primeiro: bool) -> str:
    return pio.to_html(
        figura,
        full_html=False,
        include_plotlyjs="cdn" if primeiro else False,
        div_id=div_id,
        config={"responsive": True},
    )


def gerar_html(dados: dict[str, pd.DataFrame], gerado_em: datetime) -> str:
    prim = dados["total_emp_ug_prim"].iloc[0]["TOTAL_RECURSOS_EMPENHADOS"]
    sec = dados["total_emp_ug_sec"].iloc[0]["TOTAL_RECURSOS_EMPENHADOS_na167"]
    rp_prim = dados["total_emp_ug_prim25"].iloc[0]["TOTAL_RECURSOS_EMPENHADOS_2025"]
    rp_sec = dados["total_emp_ug_sec25"].iloc[0][
        "TOTAL_RECURSOS_EMPENHADOS_2025_UG167"
    ]

    cartoes = "".join(
        (
            _cartao(
                "Empenhado UG Primária",
                painel.reais(prim),
                "Saldo a liquidar + em liquidação + liquidado + pago.",
            ),
            _cartao(
                "Empenhado UG Secundária",
                painel.reais(sec),
                "Saldo a liquidar + em liquidação + liquidado + pago.",
            ),
            _cartao(
                "RP Inscrito - UG Primária",
                painel.reais(rp_prim),
                "Total inscrito no ano anterior.",
            ),
            _cartao(
                "RP Inscrito - UG Secundária",
                painel.reais(rp_sec),
                "Total inscrito no ano anterior.",
            ),
        )
    )

    ne = dados["ne_com_saldo"].sort_values(
        ["SETOR_REPONSAVEL", "DIAS"],
        ascending=[True, True],
    ).head(15)
    ne_html = _tabela_html(
        ne,
        moeda=("SALDO_NE",),
        inteiros=("UG", "ND", "DIAS"),
    )

    graficos = (
        (
            "UG primária · Empenhos por ação e setor",
            "total_emp_setor_prim",
            painel.grafico_setor_prim,
            "TOTAL_RECURSOS_EMPENHADOS_POR_SETOR",
        ),
        (
            "UG secundária · Empenhos por ação e setor",
            "total_emp_setor_sec",
            painel.grafico_setor_sec,
            "TOTAL_RECURSOS_EMPENHADOS_POR_SETOR",
        ),
        (
            "Empenhado por Plano Interno",
            "total_emp_pi",
            painel.grafico_emp_pi,
            "TOTAL_EMPENHADO",
        ),
        (
            "RP inscrito por Plano Interno",
            "total_insc_pi",
            painel.grafico_insc_pi,
            "TOTAL_EMPENHADO",
        ),
        (
            "Empenhado por modalidade de licitação",
            "total_emp_mod",
            painel.grafico_modalidade,
            "TOTAL_EMPENHADO",
        ),
    )

    secoes_graficos = []
    for indice, (titulo, nome, funcao, coluna_valor) in enumerate(graficos, start=1):
        dataframe = dados[nome].sort_values(coluna_valor, ascending=False).head(4)
        tabela = _tabela_html(dataframe, moeda=(coluna_valor,))
        figura = funcao(dados[nome])
        grafico = _grafico_html(figura, f"g{indice:02d}", indice == 1)
        secoes_graficos.append(
            '<article class="chart-card">'
            f"<h2>{_texto(titulo)}</h2>"
            f"{grafico}{tabela}</article>"
        )

    data_geracao = gerado_em.strftime("%d/%m/%Y %H:%M")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>7ºBECmb - Gestão de Recursos</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; color: #10233f; }}
    body {{ margin: 0; padding: 24px; background: #f5f7fb; }}
    header {{ display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 20px; }}
    header p {{ margin: 0 0 6px; color: #52719c; font-size: 12px; letter-spacing: .08em; }}
    h1 {{ margin: 0; font-size: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 16px; }}
    .band {{ margin-bottom: 18px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
    .card, .panel, .chart-card {{ background: white; border: 1px solid #d5deeb; border-radius: 9px; padding: 16px; }}
    .card-label {{ margin: 0 0 8px; color: #52719c; font-size: 13px; }}
    .card-value {{ margin: 0 0 7px; color: #10233f; font-size: 23px; font-weight: 700; }}
    .card-description {{ margin: 0; color: #52719c; font-size: 12px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ padding: 8px 9px; border-bottom: 1px solid #e1e7f0; text-align: left; white-space: nowrap; }}
    th {{ color: #52719c; font-size: 11px; }}
    tbody tr:nth-child(odd) {{ background: #f5f7fb; }}
    .charts {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }}
    .chart-card {{ min-width: 0; padding: 12px; }}
    .chart-card table {{ font-size: 11px; }}
    footer {{ margin-top: 16px; padding-top: 12px; border-top: 1px solid #d5deeb; color: #52719c; font-size: 12px; text-align: right; }}
    @media (max-width: 1000px) {{ .charts {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width: 650px) {{ body {{ padding: 14px; }} header {{ display: block; }} .cards, .charts {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header class="band">
    <div><p>EXECUÇÃO ORÇAMENTÁRIA · EXERCÍCIO 2026</p><h1>7ºBECmb - Gestão de Recursos</h1></div>
  </header>
  <section class="band cards" aria-label="Indicadores gerais">{cartoes}</section>
  <section class="band panel">
    <h2>NE com saldo a liquidar por setor responsável</h2>
    {ne_html}
  </section>
  <section class="band charts" aria-label="Gráficos do painel">
    {"".join(secoes_graficos)}
  </section>
  <footer>Dados de {data_geracao}</footer>
</body>
</html>
"""


def main():
    dados = painel.ler(_MARTS)
    conteudo = gerar_html(dados, datetime.now().astimezone())
    caminho = _RAIZ / "relatorio.html"
    caminho.write_text(conteudo, encoding="utf-8")
    tamanho_kb = caminho.stat().st_size / 1024
    print(f"Relatório salvo em {caminho} ({tamanho_kb:.1f} KB)")


if __name__ == "__main__":
    main()
