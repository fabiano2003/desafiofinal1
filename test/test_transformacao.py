import io
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from decimal import Decimal

import duckdb
import pytest

from pipeline import transformacao


def _criar_raw(con, tabela, mapa, linhas=()):
    colunas = list(dict.fromkeys(origem for origem, _ in mapa))
    definicoes = ", ".join(f'"{coluna}" VARCHAR' for coluna in colunas)
    con.execute(f'CREATE TABLE raw."{tabela}" ({definicoes})')
    if linhas:
        marcadores = ", ".join("?" for _ in colunas)
        valores = [tuple(linha.get(coluna) for coluna in colunas) for linha in linhas]
        con.executemany(f'INSERT INTO raw."{tabela}" VALUES ({marcadores})', valores)


def _preparar_banco_transformacao(caminho, linha_primaria=None):
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA raw")
    for tabela, mapa in transformacao._TABELAS:
        linhas = (
            [linha_primaria]
            if tabela == "empenhos_2026_prim" and linha_primaria
            else []
        )
        _criar_raw(con, tabela, mapa, linhas)
    con.close()


def test_transformacao_remove_duplicata_e_converte_data_e_dinheiro(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "transformacao.duckdb"
    linha = {
        "UG": "123",
        "EMISSAO": "2026-03-14",
        "A_LIQUIDAR": "12,50",
        "EM_LIQUIDACAO": "0,25",
        "NE": "NE50-001",
    }  # A segunda cópia idêntica prova a deduplicação exata.
    _preparar_banco_transformacao(caminho, linha)
    con = duckdb.connect(str(caminho))
    con.execute(
        'INSERT INTO raw."empenhos_2026_prim" '
        'SELECT * FROM raw."empenhos_2026_prim"'
    )
    con.close()
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho))
    )

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        transformacao.main()

    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM refined.empenhos_2026_prim"
        ).fetchone() == (1,)
        assert con.execute(
            "SELECT COD_OM, DATA_EMISSAO, SALDO_NE, EM_LIQUIDACAO, RESPONSAVEL "
            "FROM refined.empenhos_2026_prim"
        ).fetchone() == (
            123,
            datetime(2026, 3, 14),
            Decimal("12.50"),
            Decimal("0.25"),
            "S4",
        )
        tipos = {
            coluna[0]: coluna[1]
            for coluna in con.execute("DESCRIBE refined.empenhos_2026_prim").fetchall()
        }
        assert tipos["DATA_EMISSAO"] == "TIMESTAMP"
        assert tipos["SALDO_NE"] == "DECIMAL(10,2)"
    finally:
        con.close()

    assert "duplicatas_removidas=1" in stdout.getvalue()


def test_valor_financeiro_invalido_encerra_sem_criar_refined(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "conversao_invalida.duckdb"
    linha = {
        "UG": "123",
        "EMISSAO": "2026-03-14",
        "A_LIQUIDAR": "não é dinheiro",
    }  # Valor propositalmente inválido não deve ser convertido em NULL.
    _preparar_banco_transformacao(caminho, linha)
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho))
    )

    stderr = io.StringIO()
    with redirect_stderr(stderr), pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
    assert "empenhos_2026_prim" in stderr.getvalue()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'refined'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_tabela_raw_ausente_encerra_com_orientacao(tmp_path, monkeypatch):
    caminho = tmp_path / "raw_ausente.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA raw")
    con.close()
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho))
    )

    stderr = io.StringIO()
    with redirect_stderr(stderr), pytest.raises(SystemExit) as erro:
        transformacao.main()

    assert erro.value.code == 1
    mensagem = stderr.getvalue()
    assert "empenhos_2026_prim" in mensagem
    assert "pipeline.ingestao" in mensagem
