import io
import re
from contextlib import redirect_stdout
from datetime import datetime

import duckdb

import relatorio


def test_texto_escapa_html_e_trata_valor_nulo():
    assert relatorio._texto("<inventado>") == "&lt;inventado&gt;"
    assert relatorio._texto(None) == ""


def _criar_marts_inventados(caminho):
    con = duckdb.connect(str(caminho))
    con.execute("CREATE SCHEMA marts")
    con.execute(
        "CREATE TABLE marts.ne_com_saldo "
        "(UG INTEGER, PLANO_INTERNO VARCHAR, ND INTEGER, DIAS INTEGER, "
        "NE VARCHAR, SALDO_NE DECIMAL(10,2), SETOR_REPONSAVEL VARCHAR)"
    )
    # Dezessete linhas inventadas fazem valer o limite inicial de quinze.
    for indice in range(17):
        con.execute(
            "INSERT INTO marts.ne_com_saldo VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                100 + indice,
                "PI <inventado>",
                339030,
                indice,
                f"NE{indice:02d}",
                10 + indice,
                "Setor inventado",
            ],
        )

    con.execute(
        "CREATE TABLE marts.total_emp_ug_prim AS "
        "SELECT 100 AS UG_Primaria, 1234.50::DECIMAL(10,2) "
        "AS TOTAL_RECURSOS_EMPENHADOS"
    )
    con.execute(
        "CREATE TABLE marts.total_emp_ug_sec AS "
        "SELECT 200 AS UG_Secundaria, 2345.60::DECIMAL(10,2) "
        "AS TOTAL_RECURSOS_EMPENHADOS_na167"
    )
    con.execute(
        "CREATE TABLE marts.total_emp_ug_prim25 AS "
        "SELECT 100 AS UG_Primaria, 345.67::DECIMAL(10,2) "
        "AS TOTAL_RECURSOS_EMPENHADOS_2025"
    )
    con.execute(
        "CREATE TABLE marts.total_emp_ug_sec25 AS "
        "SELECT 200 AS UG_Secundaria, 456.78::DECIMAL(10,2) "
        "AS TOTAL_RECURSOS_EMPENHADOS_2025_UG167"
    )
    for nome in ("total_emp_setor_prim", "total_emp_setor_sec"):
        con.execute(
            f'CREATE TABLE marts.{nome} '
            '(ACAO_ORCAMENTARIA VARCHAR, "SETOR_RESPONSÁVEL" VARCHAR, '
            "TOTAL_RECURSOS_EMPENHADOS_POR_SETOR DECIMAL(10,2))"
        )
        for indice in range(6):
            con.execute(
                f'INSERT INTO marts.{nome} VALUES (?, ?, ?)',
                [f"A{indice}", f"Setor {indice}", 100 + indice],
            )
    for nome, categoria in (
        ("total_emp_pi", "PLANO_INTERNO"),
        ("total_insc_pi", "PLANO_INTERNO"),
        ("total_emp_mod", "MODALIDADE"),
    ):
        con.execute(
            f"CREATE TABLE marts.{nome} "
            f"({categoria} VARCHAR, TOTAL_EMPENHADO DECIMAL(10,2))"
        )
        for indice in range(6):
            con.execute(
                f"INSERT INTO marts.{nome} VALUES (?, ?)",
                [f"Categoria {indice}", 100 + indice],
            )
    con.close()


def test_relatorio_grava_html_repetivel_com_so_o_rodape_variando(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(relatorio, "_RAIZ", tmp_path)
    _criar_marts_inventados(tmp_path / "olist.duckdb")
    horarios = iter(
        (datetime(2026, 11, 3, 21, 30), datetime(2026, 11, 3, 21, 31))
    )

    class RelogioFalso:
        @classmethod
        def now(cls):
            return next(horarios)

    monkeypatch.setattr(relatorio, "datetime", RelogioFalso)
    primeira_saida = io.StringIO()
    with redirect_stdout(primeira_saida):
        relatorio.main()
    primeiro_html = (tmp_path / "relatorio.html").read_text(encoding="utf-8")
    segunda_saida = io.StringIO()
    with redirect_stdout(segunda_saida):
        relatorio.main()
    segundo_html = (tmp_path / "relatorio.html").read_text(encoding="utf-8")

    def normalizar_rodape(texto):
        return re.sub(
            r"<footer>Dados de \d{2}/\d{2}/\d{4} \d{2}:\d{2}</footer>",
            "<footer>Dados de HORARIO</footer>",
            texto,
        )
    assert normalizar_rodape(primeiro_html) == normalizar_rodape(segundo_html)
    assert "Dados de 03/11/2026 21:30" in primeiro_html
    assert "Dados de 03/11/2026 21:31" in segundo_html
    assert primeiro_html.count('class="card"') == 4
    assert all(f'id="g{indice:02d}"' in primeiro_html for indice in range(1, 6))
    assert primeiro_html.count("https://cdn.plot.ly/plotly-") == 1
    assert "NE16" not in primeiro_html
    assert "PI &lt;inventado&gt;" in primeiro_html
    assert (tmp_path / "relatorio.html").is_file()
    assert "relatorio.html" in primeira_saida.getvalue()
    assert "relatorio.html" in segunda_saida.getvalue()
