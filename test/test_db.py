import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

from pipeline import db


def test_importar_nao_abre_banco_nem_cria_arquivo(tmp_path):
    raiz_projeto = Path(__file__).resolve().parents[1]
    ambiente = os.environ.copy()
    ambiente["PYTHONPATH"] = str(raiz_projeto)
    resultado = subprocess.run(
        [sys.executable, "-c", "import pipeline.db"],
        cwd=tmp_path,
        env=ambiente,
        check=False,
        capture_output=True,
        text=True,
    )

    assert resultado.returncode == 0
    assert not (tmp_path / "olist.duckdb").exists()


def test_conectar_usa_a_pasta_configurada_e_devolve_conexao_aberta(
    tmp_path, monkeypatch
):
    assert db.PASTA_RAW == Path(db.__file__).resolve().parent.parent / "raw"
    pasta_raw = tmp_path / "projeto" / "raw"
    pasta_raw.mkdir(parents=True)
    pasta_corrente = tmp_path / "outra_pasta"
    pasta_corrente.mkdir()
    monkeypatch.setattr(db, "PASTA_RAW", pasta_raw)
    monkeypatch.chdir(pasta_corrente)

    con = db.conectar()
    try:
        assert (pasta_raw.parent / "olist.duckdb").is_file()
        assert not (pasta_corrente / "olist.duckdb").exists()
        assert con.execute("SELECT 1").fetchone() == (1,)
    finally:
        con.close()


def test_criar_schema_e_recriar_tabela_preservam_tipo_e_nulo(tmp_path):
    con = duckdb.connect(str(tmp_path / "teste.duckdb"))
    try:
        db.criar_schema(con, "inventado")
        db.criar_schema(con, "inventado")
        primeira_entrada = pd.DataFrame(
            {"codigo": ["A", None, "C"], "descricao": ["x", "y", "z"]}
        )
        assert db.gravar(con, primeira_entrada, "inventado", "itens") == 3

        linhas = con.execute(
            "SELECT codigo, descricao FROM inventado.itens ORDER BY descricao"
        ).fetchall()
        tipos = con.execute("DESCRIBE inventado.itens").fetchall()

        assert linhas == [("A", "x"), (None, "y"), ("C", "z")]
        assert [coluna[1] for coluna in tipos] == ["VARCHAR", "VARCHAR"]
    finally:
        con.close()


def test_gravar_substitui_a_tabela_e_retorna_contagem_do_banco(tmp_path):
    con = duckdb.connect(str(tmp_path / "teste.duckdb"))
    try:
        db.criar_schema(con, "raw")
        assert db.gravar(
            con, pd.DataFrame({"valor": ["antigo"]}), "raw", "amostra"
        ) == 1
        assert db.gravar(
            con, pd.DataFrame({"valor": ["a", "b", "c"]}), "raw", "amostra"
        ) == 3

        assert con.execute("SELECT valor FROM raw.amostra ORDER BY valor").fetchall() == [
            ("a",),
            ("b",),
            ("c",),
        ]
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'raw' AND table_name LIKE '_df_%'"
        ).fetchone() == (0,)
    finally:
        con.close()
