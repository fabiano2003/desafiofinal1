import duckdb
import pandas as pd
import plotly.graph_objects as go
import pytest

import painel


def test_reais_e_numero_formatam_valores_inventados():
    assert painel.reais(1003.25) == "R$ 1.003,25"
    assert painel.reais(-12.5, casas=1) == "R$ -12,5"
    assert painel.numero(96470) == "96.470"
    assert painel.numero(12.345, casas=2) == "12,35"


def test_ler_consulta_marts_solicitados_e_renomeia_setor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    con = duckdb.connect("olist.duckdb")
    con.execute("CREATE SCHEMA marts")
    con.execute(
        'CREATE TABLE marts.total_emp_setor_prim AS SELECT 1 AS x, '
        "'Setor inventado' AS \"SETOR_RESPONSÁVEL\""
    )
    con.close()

    dados = painel.ler(("total_emp_setor_prim",))

    assert dados["total_emp_setor_prim"].to_dict(orient="records") == [
        {"x": 1, "SETOR_RESPONSAVEL": "Setor inventado"}
    ]


def test_ler_relata_marts_ausentes_e_libera_o_arquivo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    con = duckdb.connect("olist.duckdb")
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.existe AS SELECT 1 AS x")
    con.close()

    with pytest.raises(painel.MartsAusentesError) as erro:
        painel.ler(("existe", "ausente"))

    assert erro.value.marts == ["ausente"]
    con = duckdb.connect("olist.duckdb")
    try:
        assert con.execute("SELECT 1").fetchone() == (1,)
    finally:
        con.close()


def test_cada_grafico_retorna_pontos_correspondentes_as_linhas():
    dados_combinados = pd.DataFrame(
        {
            "TOTAL_RECURSOS_EMPENHADOS_POR_SETOR": [10, 30, 20],
            "ACAO_ORCAMENTARIA": ["A1", "A2", "A3"],
            "SETOR_RESPONSAVEL": ["S1", "S2", "S3"],
        }
    )
    dados_pi = pd.DataFrame(
        {"TOTAL_EMPENHADO": [10, 30, 20], "PLANO_INTERNO": ["P1", "P2", "P3"]}
    )
    dados_modalidade = pd.DataFrame(
        {"TOTAL_EMPENHADO": [10, 30, 20], "MODALIDADE": ["M1", "M2", "M3"]}
    )
    graficos = (
        painel.grafico_setor_prim(dados_combinados),
        painel.grafico_setor_sec(dados_combinados),
        painel.grafico_emp_pi(dados_pi),
        painel.grafico_insc_pi(dados_pi),
        painel.grafico_modalidade(dados_modalidade),
    )

    assert all(isinstance(figura, go.Figure) for figura in graficos)
    assert [len(figura.data[0].x) for figura in graficos] == [3, 3, 3, 3, 3]
    assert list(graficos[0].data[0].x) == [30, 20, 10]
