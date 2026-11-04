"""Spec e execução da transformação das tabelas de empenhos.

ESCOPO E MOTIVAÇÃO
Lê somente raw.empenhos_2026_prim, raw.empenhos_2026_sec,
raw.empenhos_2025_prim e raw.empenhos_2025_sec, e grava no schema refined,
sem escrever em raw. raw.todos_empenhos fica de fora porque será trabalhada
depois: não se transforma dado que esta etapa não vai ler. Antes de transformar,
verifica as quatro entradas e orienta a executar "uv run python -m
pipeline.ingestao" se faltar alguma, evitando produzir um refined incompleto.

MAPAS DE COLUNAS E MOTIVAÇÃO
Os destinos seguem o vocabulário português usado nos JOINs. Cada coluna de
origem é mapeada; a única exceção é BLOQEMLIQ nas duas tabelas de 2025, que
fica fora de refined conforme decisão explícita. Os mapas completos são:

Para empenhos_2026_prim e empenhos_2026_sec:
UG -> COD_OM; NOME_UG -> OM; ICFEX -> CGCFEX; PROGRAMA -> PROGRAMA;
NOME_PROGRAMA -> OBJETIVO; ACAO -> AO; NOME_ACAO -> NOME_ORC;
UGR -> COD_GESTOR; NOME_UGR -> NOME_GESTOR; PTRES -> PTRES;
FONTE -> ORIG_RECURSOS; NOME_FONTE -> NOME_FONTE; PI -> PLANO_INTERNO;
NOME_PI -> NOME_PLAN_INT; ND -> ND; SI -> SUB_ITEM; NE -> NE;
TIPOEMPENHO -> TIPO_NE; CHAVE -> CHAVE_NE; EMISSAO -> DATA_EMISSAO;
FAV -> CNPJ_CPF_FAV; NOME_FAV -> EMPRESA_PF; COD_AMPARO -> AMPARO;
MOD_LIC -> MODALIDADE; REF_DISP -> REF_DISP; OBS -> DETALHAMENTO;
LOCAL -> LOCAL; RP -> COD_TIPO_DESPESA; NOME_RP -> NOME_TIPO_DESP;
TIPO_CREDITO -> TIPO_CREDITO; NOME_TIPO_CREDITO -> NTC;
PO -> PROG_ORCAMENTARIO; AUTOR_EMENDA -> AUTOR_EMENDA;
NOME_AUTOR_EMENDA -> NOME_AUTOR; NOME_UO -> UNID_ORC; UO -> COD_UO;
A_LIQUIDAR -> SALDO_NE; EM_LIQUIDACAO -> EM_LIQUIDACAO;
LIQUIDADO -> LIQUIDADO; PAGO -> PAGO.

Para empenhos_2025_prim e empenhos_2025_sec:
UG -> COD_OM; NOME_UG -> OM; ICFEX -> CGCFEX;
NOME_ICFEX -> NOME_CGCFEX; PROGRAMA -> PROGRAMA;
NOME_PROGRAMA -> OBJETIVO; ACAO -> AO; NOME_ACAO -> NOME_ORC;
UGR -> COD_GESTOR; NOME_UGR -> NOME_GESTOR; PTRES -> PTRES;
FONTE -> ORIG_RECURSOS; NOME_FONTE -> NOME_FONTE; PI -> PLANO_INTERNO;
NOME_PI -> NOME_PLAN_INT; ND -> ND; NOME_ND -> NOME_ND; NE -> NE;
CHAVE -> CHAVE_NE; DATA -> DATA_EMISSAO; FAV -> CNPJ_CPF_FAV;
NOME_FAV -> EMPRESA_PF; RP -> COD_TIPO_DESPESA; NOME_RP -> NOME_TIPO_DESP;
PO -> PROG_ORCAMENTARIO; NOME_PO -> NOME_PROG_ORC; MOD_LIC -> MODALIDADE;
TIPO_NE -> TIPO_NE; GESTAO -> GESTAO; OBS -> DETALHAMENTO; LOCAL -> LOCAL;
NOME_UO -> UNID_ORC; UO -> COD_UO; INSC -> INSCRITO;
INSCEMLIQ -> INSCEMLIQ; REINSC -> REINSCRITO;
REINSCEMLIQ -> REINSCEMLIQ; BLOQALIQ -> BLOQUEADOALIQ; ALIQ -> SALDO_NE;
EMLIQ -> EM_LIQUIDACAO; APAG -> A_PAGAR; PAGO -> PAGO; CANC -> CANCELADO.

TIPOS E NULOS
DATA_EMISSAO vira TIMESTAMP por strptime no formato observado e confirmado
%Y-%m-%d, para dar tipo temporal aos valores de data. Os campos financeiros
SALDO_NE, EM_LIQUIDACAO, LIQUIDADO, PAGO, INSCRITO, INSCEMLIQ, REINSCRITO,
REINSCEMLIQ, BLOQUEADOALIQ, A_PAGAR e CANCELADO viram DECIMAL(10,2), pois
valores monetários precisam somar centavos com exatidão. O SQL troca a vírgula
decimal das fontes por ponto antes do CAST. CNPJ_CPF_FAV, ORIG_RECURSOS e
PROG_ORCAMENTARIO permanecem VARCHAR para preservar identificadores e códigos
alfanuméricos observados. COD_OM, CGCFEX, PROGRAMA, COD_GESTOR, PTRES, ND,
SUB_ITEM, AMPARO, COD_TIPO_DESPESA e COD_UO viram INTEGER; todos os outros
destinos permanecem VARCHAR. A conversão roda no DuckDB para não trazer os
dados à memória. Linhas com nulos permanecem, e nenhum nulo é preenchido,
porque nulos carregam informação e não devem ser inventados ou apagados.

CONVERSÕES E DUPLICATAS
strptime e CAST são estritos; não se usam versões permissivas porque um nulo
fabricado ficaria indistinguível do nulo original. Antes de gravar qualquer
tabela refined, valida cada conversão para reportar tabela, coluna e o valor
que falhou, e então encerra com código 1. Linha inteira repetida é mantida
uma vez e sua quantidade é contada para tornar explícita essa remoção.

RESPONSÁVEL E SAÍDA
Adiciona RESPONSAVEL segundo os códigos contidos em NE: NE00 -> Fisc_Adm;
NE45 -> Almox; NE50 -> S4; NE55 -> Almox; NE60 -> Aprov; NE62 -> STI;
NE64 -> Fisc_Adm2; NE66 -> HTCC; NE68 -> SPIMA; NE70 -> Sec_Sau;
NE72 -> SFPC. Cada tabela refined é recriada com CREATE OR REPLACE TABLE
para que repetir a execução não acrescente linhas. A saída mostra o somatório
de SALDO_NE de cada tabela refined e o valor correspondente calculado em raw,
além da contagem de duplicatas removidas, permitindo conferir os totais
centavo por centavo.
"""

import sys

import duckdb

from pipeline.db import conectar, criar_schema

_MAPA_2026 = (
    ("UG", "COD_OM"),
    ("NOME_UG", "OM"),
    ("ICFEX", "CGCFEX"),
    ("PROGRAMA", "PROGRAMA"),
    ("NOME_PROGRAMA", "OBJETIVO"),
    ("ACAO", "AO"),
    ("NOME_ACAO", "NOME_ORC"),
    ("UGR", "COD_GESTOR"),
    ("NOME_UGR", "NOME_GESTOR"),
    ("PTRES", "PTRES"),
    ("FONTE", "ORIG_RECURSOS"),
    ("NOME_FONTE", "NOME_FONTE"),
    ("PI", "PLANO_INTERNO"),
    ("NOME_PI", "NOME_PLAN_INT"),
    ("ND", "ND"),
    ("SI", "SUB_ITEM"),
    ("NE", "NE"),
    ("TIPOEMPENHO", "TIPO_NE"),
    ("CHAVE", "CHAVE_NE"),
    ("EMISSAO", "DATA_EMISSAO"),
    ("FAV", "CNPJ_CPF_FAV"),
    ("NOME_FAV", "EMPRESA_PF"),
    ("COD_AMPARO", "AMPARO"),
    ("MOD_LIC", "MODALIDADE"),
    ("REF_DISP", "REF_DISP"),
    ("OBS", "DETALHAMENTO"),
    ("LOCAL", "LOCAL"),
    ("RP", "COD_TIPO_DESPESA"),
    ("NOME_RP", "NOME_TIPO_DESP"),
    ("TIPO_CREDITO", "TIPO_CREDITO"),
    ("NOME_TIPO_CREDITO", "NTC"),
    ("PO", "PROG_ORCAMENTARIO"),
    ("AUTOR_EMENDA", "AUTOR_EMENDA"),
    ("NOME_AUTOR_EMENDA", "NOME_AUTOR"),
    ("NOME_UO", "UNID_ORC"),
    ("UO", "COD_UO"),
    ("A_LIQUIDAR", "SALDO_NE"),
    ("EM_LIQUIDACAO", "EM_LIQUIDACAO"),
    ("LIQUIDADO", "LIQUIDADO"),
    ("PAGO", "PAGO"),
)

_MAPA_2025 = (
    ("UG", "COD_OM"),
    ("NOME_UG", "OM"),
    ("ICFEX", "CGCFEX"),
    ("NOME_ICFEX", "NOME_CGCFEX"),
    ("PROGRAMA", "PROGRAMA"),
    ("NOME_PROGRAMA", "OBJETIVO"),
    ("ACAO", "AO"),
    ("NOME_ACAO", "NOME_ORC"),
    ("UGR", "COD_GESTOR"),
    ("NOME_UGR", "NOME_GESTOR"),
    ("PTRES", "PTRES"),
    ("FONTE", "ORIG_RECURSOS"),
    ("NOME_FONTE", "NOME_FONTE"),
    ("PI", "PLANO_INTERNO"),
    ("NOME_PI", "NOME_PLAN_INT"),
    ("ND", "ND"),
    ("NOME_ND", "NOME_ND"),
    ("NE", "NE"),
    ("CHAVE", "CHAVE_NE"),
    ("DATA", "DATA_EMISSAO"),
    ("FAV", "CNPJ_CPF_FAV"),
    ("NOME_FAV", "EMPRESA_PF"),
    ("RP", "COD_TIPO_DESPESA"),
    ("NOME_RP", "NOME_TIPO_DESP"),
    ("PO", "PROG_ORCAMENTARIO"),
    ("NOME_PO", "NOME_PROG_ORC"),
    ("MOD_LIC", "MODALIDADE"),
    ("TIPO_NE", "TIPO_NE"),
    ("GESTAO", "GESTAO"),
    ("OBS", "DETALHAMENTO"),
    ("LOCAL", "LOCAL"),
    ("NOME_UO", "UNID_ORC"),
    ("UO", "COD_UO"),
    ("INSC", "INSCRITO"),
    ("INSCEMLIQ", "INSCEMLIQ"),
    ("REINSC", "REINSCRITO"),
    ("REINSCEMLIQ", "REINSCEMLIQ"),
    ("BLOQALIQ", "BLOQUEADOALIQ"),
    ("ALIQ", "SALDO_NE"),
    ("EMLIQ", "EM_LIQUIDACAO"),
    ("APAG", "A_PAGAR"),
    ("PAGO", "PAGO"),
    ("CANC", "CANCELADO"),
)

_TABELAS = (
    ("empenhos_2026_prim", _MAPA_2026),
    ("empenhos_2026_sec", _MAPA_2026),
    ("empenhos_2025_prim", _MAPA_2025),
    ("empenhos_2025_sec", _MAPA_2025),
)

_TIPOS_INTEGER = {
    "COD_OM",
    "CGCFEX",
    "PROGRAMA",
    "COD_GESTOR",
    "PTRES",
    "ND",
    "SUB_ITEM",
    "AMPARO",
    "COD_TIPO_DESPESA",
    "COD_UO",
}

_TIPOS_DECIMAL = {
    "SALDO_NE",
    "EM_LIQUIDACAO",
    "LIQUIDADO",
    "PAGO",
    "INSCRITO",
    "INSCEMLIQ",
    "REINSCRITO",
    "REINSCEMLIQ",
    "BLOQUEADOALIQ",
    "A_PAGAR",
    "CANCELADO",
}

_MAPA_RESPONSAVEIS = (
    ("NE00", "Fisc_Adm"),
    ("NE45", "Almox"),
    ("NE50", "S4"),
    ("NE55", "Almox"),
    ("NE60", "Aprov"),
    ("NE62", "STI"),
    ("NE64", "Fisc_Adm2"),
    ("NE66", "HTCC"),
    ("NE68", "SPIMA"),
    ("NE70", "Sec_Sau"),
    ("NE72", "SFPC"),
)


def _identificador(nome):
    return '"' + nome.replace('"', '""') + '"'


def _expressao_conversao(origem, destino):
    campo = _identificador(origem)
    if destino == "DATA_EMISSAO":
        return f"strptime({campo}, '%Y-%m-%d')"
    if destino in _TIPOS_DECIMAL:
        return f"CAST(REPLACE({campo}, ',', '.') AS DECIMAL(10, 2))"
    if destino in _TIPOS_INTEGER:
        return f"CAST({campo} AS INTEGER)"
    return campo


def _validar_conversoes(con, tabela, mapa):
    for origem, destino in mapa:
        if destino not in _TIPOS_INTEGER | _TIPOS_DECIMAL and destino != "DATA_EMISSAO":
            continue

        expressao = _expressao_conversao(origem, destino)
        try:
            con.execute(
                f"SELECT {expressao} FROM raw.{_identificador(tabela)} "
                f"WHERE {_identificador(origem)} IS NOT NULL"
            ).fetchall()
        except (duckdb.ConversionException, duckdb.InvalidInputException) as exc:
            print(
                f"Falha de conversão em raw.{tabela}, coluna {destino} "
                f"(origem {origem}): {exc}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc


def _expressao_responsavel():
    casos = " ".join(
        f"WHEN NE LIKE '%{codigo}%' THEN '{responsavel}'"
        for codigo, responsavel in _MAPA_RESPONSAVEIS
    )
    return f"CASE {casos} END"


def _formatar_soma(valor):
    return "NULL" if valor is None else format(valor, "f")


def _contagem(con, sql):
    return int(con.execute(sql).fetchall()[0][0])


def _transformar_tabela(con, tabela, mapa):
    tabela_sql = _identificador(tabela)
    mapa_sql = ", ".join(
        f"{_expressao_conversao(origem, destino)} AS {_identificador(destino)}"
        for origem, destino in mapa
    )
    responsavel_sql = _expressao_responsavel()
    con.execute(
        f"CREATE OR REPLACE TABLE refined.{tabela_sql} AS "
        f"SELECT {mapa_sql}, {responsavel_sql} AS RESPONSAVEL "
        f"FROM (SELECT DISTINCT * FROM raw.{tabela_sql}) AS origem"
    ).fetchall()

    removidas = _contagem(
        con,
        f"SELECT count(*) FROM raw.{tabela_sql}",
    ) - _contagem(
        con,
        f"SELECT count(*) FROM (SELECT DISTINCT * FROM raw.{tabela_sql})",
    )
    soma_refined = con.execute(
        f"SELECT sum(SALDO_NE) FROM refined.{tabela_sql}"
    ).fetchall()[0][0]

    saldo_origem = next(
        origem
        for origem, destino in mapa
        if destino == "SALDO_NE"
    )
    soma_raw = con.execute(
        f"SELECT sum(CAST(REPLACE({_identificador(saldo_origem)}, ',', '.') "
        f"AS DECIMAL(10, 2))) FROM raw.{tabela_sql}"
    ).fetchall()[0][0]

    print(
        f"refined.{tabela}: SALDO_NE={_formatar_soma(soma_refined)}; "
        f"raw={_formatar_soma(soma_raw)}; duplicatas_removidas={removidas}"
    )


def main():
    con = conectar()
    try:
        existentes = {
            tabela
            for (tabela,) in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'raw'"
            ).fetchall()
        }
        ausentes = [
            tabela for tabela, _ in _TABELAS if tabela not in existentes
        ]
        if ausentes:
            print(
                "Tabelas ausentes no schema raw: "
                f"{', '.join(ausentes)}. Rode "
                "'uv run python -m pipeline.ingestao'.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        for tabela, mapa in _TABELAS:
            _validar_conversoes(con, tabela, mapa)

        criar_schema(con, "refined")
        for tabela, mapa in _TABELAS:
            _transformar_tabela(con, tabela, mapa)
    finally:
        con.close()


if __name__ == "__main__":
    main()
