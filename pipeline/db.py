"""Módulo compartilhado de acesso ao banco.

As regras abaixo mantêm este módulo neutro para as etapas do curso:

- PASTA_RAW e o arquivo olist.duckdb partem da localização deste arquivo, não
  do diretório corrente, para que qualquer comando use as mesmas fontes e o
  mesmo banco.
- A API pública consiste somente em PASTA_RAW, conectar, criar_schema e gravar.
  Este módulo não escolhe tabelas nem interpreta dados, pois essas decisões
  pertencem a cada etapa e não devem virar regras ocultas compartilhadas.
- criar_schema usa CREATE SCHEMA IF NOT EXISTS; gravar usa CREATE OR REPLACE
  TABLE e preserva as colunas, tipos e nulos recebidos, pois transformar dados
  aqui apagaria a fronteira entre as etapas. A contagem vem de uma consulta ao
  banco para confirmar o que foi persistido, e o registro temporário do
  DataFrame é removido para não deixar objetos auxiliares.
- conectar devolve uma conexão aberta; quem a obtém é responsável por fechá-la,
  evitando estado global e permitindo controlar o ciclo de vida da conexão.
"""

from pathlib import Path as _Path
from uuid import uuid4 as _uuid4

import duckdb as _duckdb

PASTA_RAW = _Path(__file__).resolve().parent.parent / "raw"


def conectar():
    """Abre o banco da raiz do projeto, criando-o se ainda não existir."""
    return _duckdb.connect(str(PASTA_RAW.parent / "olist.duckdb"))


def criar_schema(con, nome):
    """Cria o schema quando necessário."""
    schema_sql = '"' + nome.replace('"', '""') + '"'
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_sql}").fetchall()


def gravar(con, df, schema, tabela):
    """Recria uma tabela a partir do DataFrame e devolve sua contagem no banco."""
    schema_sql = '"' + schema.replace('"', '""') + '"'
    tabela_sql = '"' + tabela.replace('"', '""') + '"'
    registro = f"_df_{_uuid4().hex}"
    registro_sql = '"' + registro + '"'

    con.register(registro, df)
    try:
        con.execute(
            f"CREATE OR REPLACE TABLE {schema_sql}.{tabela_sql} "
            f"AS SELECT * FROM {registro_sql}"
        ).fetchall()
    finally:
        con.unregister(registro)

    return int(
        con.execute(
            f"SELECT count(*) FROM {schema_sql}.{tabela_sql}"
        ).fetchall()[0][0]
    )
