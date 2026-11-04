import gzip
import io
from contextlib import redirect_stderr, redirect_stdout

import duckdb
import pytest

from pipeline import ingestao


class _SaidaUtf8(io.StringIO):
    def reconfigure(self, *, encoding=None):
        return None


def _criar_csvs_pequenos(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    for arquivo, _ in ingestao._ARQUIVOS_TABELAS:
        with gzip.open(pasta / arquivo, "wt", encoding="utf-8") as csv:
            csv.write("codigo\ttexto\n")
            csv.write("1\tprimeira linha inventada\n")  # Registro de exemplo.
            csv.write("2\t\n")  # Campo vazio deve continuar nulo.


def test_csv_gzip_vira_tabelas_com_linhas_e_tipos_texto_preservados(
    tmp_path, monkeypatch
):
    pasta_raw = tmp_path / "raw"
    arquivos_gz = tuple(
        (f"{arquivo}.gz", tabela)
        for arquivo, tabela in ingestao._ARQUIVOS_TABELAS
    )
    monkeypatch.setattr(ingestao, "_ARQUIVOS_TABELAS", arquivos_gz)
    _criar_csvs_pequenos(pasta_raw)
    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)
    monkeypatch.setattr(ingestao, "conectar", lambda: duckdb.connect(str(banco)))

    primeira_saida = _SaidaUtf8()
    segunda_saida = _SaidaUtf8()
    with redirect_stdout(primeira_saida):
        ingestao.main()
    with redirect_stdout(segunda_saida):
        ingestao.main()

    assert primeira_saida.getvalue() == segunda_saida.getvalue()
    assert "Total: 10" in primeira_saida.getvalue()
    con = duckdb.connect(str(banco), read_only=True)
    try:
        for _, tabela in ingestao._ARQUIVOS_TABELAS:
            assert con.execute(f"SELECT count(*) FROM raw.{tabela}").fetchone() == (2,)
            linhas = con.execute(
                f"SELECT codigo, texto FROM raw.{tabela} ORDER BY codigo"
            ).fetchall()
            assert linhas == [
                ("1", "primeira linha inventada"),
                ("2", None),
            ]
            assert [
                coluna[1]
                for coluna in con.execute(f"DESCRIBE raw.{tabela}").fetchall()
            ] == ["VARCHAR", "VARCHAR"]
    finally:
        con.close()


def test_arquivo_ausente_encerra_antes_de_abrir_o_banco(
    tmp_path, monkeypatch
):
    pasta_raw = tmp_path / "raw_vazia"
    pasta_raw.mkdir()
    banco = tmp_path / "nao_deve_existir.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)

    def conectar_nao_esperado():
        raise AssertionError("A ingestão não deve abrir o banco")

    monkeypatch.setattr(ingestao, "conectar", conectar_nao_esperado)

    stdout = _SaidaUtf8()
    stderr = io.StringIO()
    with (
        redirect_stdout(stdout),
        redirect_stderr(stderr),
        pytest.raises(SystemExit) as erro,
    ):
        ingestao.main()

    assert erro.value.code == 1
    assert all(
        arquivo in stderr.getvalue() for arquivo, _ in ingestao._ARQUIVOS_TABELAS
    )
    assert str(pasta_raw) in stderr.getvalue()
    assert not banco.exists()
