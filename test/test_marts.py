import io
from contextlib import redirect_stderr, redirect_stdout

import duckdb
import pytest

from pipeline import marts


class _SaidaUtf8(io.StringIO):
    def reconfigure(self, *, encoding=None):
        return None


def _preparar_banco(caminho, incluir_refined=True):
    con = duckdb.connect(str(caminho))
    if incluir_refined:
        con.execute("CREATE SCHEMA refined")
        for tabela in marts._TABELAS_REFINED:
            con.execute(f"CREATE TABLE refined.{tabela} (valor INTEGER)")
    con.close()


def _executar_com_banco(caminho, pasta_sql, monkeypatch):
    monkeypatch.setattr(marts, "_PASTA_SQL", pasta_sql)
    monkeypatch.setattr(marts, "conectar", lambda: duckdb.connect(str(caminho)))


def test_arquivo_sem_prefixo_para_antes_de_executar_sql(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "marts.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "teste.sql").write_text("SELECT 1", encoding="utf-8")
    _preparar_banco(caminho)
    _executar_com_banco(caminho, pasta_sql, monkeypatch)

    stderr = io.StringIO()
    with (
        redirect_stderr(stderr),
        redirect_stdout(_SaidaUtf8()),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert "teste.sql" in stderr.getvalue()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM information_schema.schemata "
            "WHERE schema_name = 'marts'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_tabelas_refined_ausentes_sao_listadas_antes_do_processamento(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "refined_ausente.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "01_teste.sql").write_text("SELECT 1", encoding="utf-8")
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA refined")
    con.execute("CREATE TABLE refined.empenhos_2026_prim (valor INTEGER)")
    con.close()
    _executar_com_banco(caminho, pasta_sql, monkeypatch)
    stderr = io.StringIO()

    with (
        redirect_stderr(stderr),
        redirect_stdout(_SaidaUtf8()),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    for tabela in marts._TABELAS_REFINED[1:]:
        assert tabela in stderr.getvalue()
    assert "uv run python -m pipeline.transformacao" in stderr.getvalue()


def test_nomes_de_tabela_duplicados_para_antes_de_executar_sql(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "duplicados.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "01_mesma.sql").write_text("SELECT 1", encoding="utf-8")
    (pasta_sql / "02_mesma.sql").write_text("SELECT 2", encoding="utf-8")
    _preparar_banco(caminho)
    _executar_com_banco(caminho, pasta_sql, monkeypatch)
    stderr = io.StringIO()

    with (
        redirect_stderr(stderr),
        redirect_stdout(_SaidaUtf8()),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert "01_mesma.sql" in stderr.getvalue()
    assert "02_mesma.sql" in stderr.getvalue()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM information_schema.schemata "
            "WHERE schema_name = 'marts'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_arquivos_sao_executados_em_ordem_alfabetica(tmp_path, monkeypatch):
    caminho = tmp_path / "ordem.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "02_b.sql").write_text("SELECT 2 AS valor", encoding="utf-8")
    (pasta_sql / "01_a.sql").write_text("SELECT 1 AS valor", encoding="utf-8")
    _preparar_banco(caminho)
    _executar_com_banco(caminho, pasta_sql, monkeypatch)
    stdout = _SaidaUtf8()

    with redirect_stdout(stdout):
        marts.main()

    linhas = stdout.getvalue().splitlines()
    assert linhas[0].startswith("✓ marts.a")
    assert linhas[1].startswith("✓ marts.b")
    assert linhas[2] == "Total: 2 marts, 2 linhas"


def test_mart_vazio_faz_rollback_e_preserva_schema_anterior(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "marts_vazio.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "01_vazio.sql").write_text(
        "SELECT valor FROM (VALUES (1)) AS dados(valor) WHERE valor = 2",
        encoding="utf-8",
    )
    _preparar_banco(caminho)
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.anterior AS SELECT 7 AS valor")
    con.close()
    _executar_com_banco(caminho, pasta_sql, monkeypatch)

    stderr = io.StringIO()
    with (
        redirect_stderr(stderr),
        redirect_stdout(_SaidaUtf8()),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert "01_vazio.sql" in stderr.getvalue()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchone() == (7,)
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'marts' AND table_name = 'vazio'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_apagar_arquivo_remove_mart_na_execucao_seguinte(
    tmp_path, monkeypatch
):
    caminho = tmp_path / "marts_recriados.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    arquivo = pasta_sql / "00_teste.sql"
    arquivo.write_text("  SELECT 1 AS x;  \n", encoding="utf-8")
    _preparar_banco(caminho)
    _executar_com_banco(caminho, pasta_sql, monkeypatch)

    primeira_saida = _SaidaUtf8()
    with redirect_stdout(primeira_saida):
        marts.main()
    segunda_saida = _SaidaUtf8()
    with redirect_stdout(segunda_saida):
        marts.main()
    assert primeira_saida.getvalue() == segunda_saida.getvalue()
    assert "Total: 1 marts, 1 linhas" in primeira_saida.getvalue()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute("SELECT x FROM marts.teste").fetchone() == (1,)
    finally:
        con.close()

    arquivo.unlink()
    stderr = io.StringIO()
    with (
        redirect_stderr(stderr),
        redirect_stdout(_SaidaUtf8()),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()
    assert erro.value.code == 1

    assert "Nenhum arquivo .sql" in stderr.getvalue()
    assert "marts.teste" in primeira_saida.getvalue()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'marts' AND table_name = 'teste'"
        ).fetchone() == (1,)
    finally:
        con.close()

    (pasta_sql / "01_outro.sql").write_text("SELECT 2 AS y", encoding="utf-8")
    with redirect_stdout(_SaidaUtf8()):
        marts.main()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'marts' AND table_name = 'teste'"
        ).fetchone() == (0,)
        assert con.execute("SELECT y FROM marts.outro").fetchone() == (2,)
    finally:
        con.close()


def test_erro_sql_informa_arquivo_e_reverte_schema(tmp_path, monkeypatch):
    caminho = tmp_path / "marts_erro.duckdb"
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "01_quebrado.sql").write_text(
        "SELECT coluna_inexistente", encoding="utf-8"
    )
    _preparar_banco(caminho)
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.anterior AS SELECT 9 AS valor")
    con.close()
    _executar_com_banco(caminho, pasta_sql, monkeypatch)

    stderr = io.StringIO()
    with (
        redirect_stderr(stderr),
        redirect_stdout(_SaidaUtf8()),
        pytest.raises(SystemExit) as erro,
    ):
        marts.main()

    assert erro.value.code == 1
    assert "01_quebrado.sql" in stderr.getvalue()
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        assert con.execute("SELECT valor FROM marts.anterior").fetchone() == (9,)
    finally:
        con.close()


def test_sql_01_soma_recursos_por_ug_em_entrada_inventada(tmp_path):
    caminho = tmp_path / "sql_01.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA refined")
    con.execute(
        "CREATE TABLE refined.empenhos_2026_prim "
        "(COD_OM INTEGER, SALDO_NE DECIMAL(10,2), "
        "EM_LIQUIDACAO DECIMAL(10,2), LIQUIDADO DECIMAL(10,2), "
        "PAGO DECIMAL(10,2))"
    )
    # Duas notas da mesma UG verificam que o resultado agrega os valores.
    con.execute(
        "INSERT INTO refined.empenhos_2026_prim VALUES "
        "(123, 10.00, 2.00, 3.00, 5.00), (123, 1.00, 0.00, 0.00, 1.00)"
    )
    sql = (marts._RAIZ / "sql" / "marts" / "01_total_emp_ug_prim.sql").read_text(
        encoding="utf-8"
    )

    linhas = con.execute(sql).fetchall()

    assert linhas == [(123, 22.00)]
    con.close()


def test_sql_03_soma_componentes_de_rp_em_entrada_inventada(tmp_path):
    caminho = tmp_path / "sql_03.duckdb"
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA refined")
    con.execute(
        "CREATE TABLE refined.empenhos_2025_prim "
        "(COD_OM INTEGER, INSCRITO DECIMAL(10,2), INSCEMLIQ DECIMAL(10,2), "
        "REINSCRITO DECIMAL(10,2), REINSCEMLIQ DECIMAL(10,2), "
        "BLOQUEADOALIQ DECIMAL(10,2), SALDO_NE DECIMAL(10,2), "
        "EM_LIQUIDACAO DECIMAL(10,2), A_PAGAR DECIMAL(10,2), "
        "PAGO DECIMAL(10,2), CANCELADO DECIMAL(10,2))"
    )
    # Uma linha inventada cobre cada parcela somada pela consulta de RP.
    con.execute(
        "INSERT INTO refined.empenhos_2025_prim VALUES "
        "(321, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)"
    )
    sql = (
        marts._RAIZ / "sql" / "marts" / "03_total_emp_ug_prim25.sql"
    ).read_text(encoding="utf-8")

    linhas = con.execute(sql).fetchall()

    assert linhas == [(321, 55)]
    con.close()
