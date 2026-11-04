"""Executa cada arquivo SQL de sql/marts como uma tabela do schema marts.

O script lê apenas as quatro tabelas refined necessárias e escreve somente no
schema marts. Antes de começar, verifica as entradas e orienta a executar a
transformação quando alguma estiver ausente; assim não publica resultados
incompletos. O schema marts é apagado e recriado dentro de uma única transação,
para que marts removidos do diretório também desapareçam do banco, mas uma
falha sempre preserve integralmente a última execução bem-sucedida.

Cada arquivo .sql em ordem alfabética define uma tabela com o mesmo nome sem
a extensão e sem o prefixo numérico NN_. O Python apenas remove espaços
externos e um ponto e vírgula final do conteúdo; toda regra de negócio fica
no SQL do mart. Arquivos sem prefixo e nomes de tabela duplicados são
rejeitados antes de executar qualquer SQL de mart, para impedir resultados
ambíguos. A pasta vazia também é erro, pois não há mart a publicar.

Cada tabela precisa conter linhas: um mart vazio pode parecer um painel
corretamente carregado, embora sua consulta não tenha encontrado dados.
Contagens e total são consultados no banco e formatados com ponto como
separador de milhares. A saída usa UTF-8 para preservar a marca de sucesso e
acentos no terminal do Windows.
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline.db import conectar

_RAIZ = Path(__file__).resolve().parent.parent
_PASTA_SQL = _RAIZ / "sql" / "marts"
_TABELAS_REFINED = (
    "empenhos_2026_prim",
    "empenhos_2026_sec",
    "empenhos_2025_prim",
    "empenhos_2025_sec",
)
_PREFIXO_NUMERICO = re.compile(r"^\d{2}_(.+)$")


def _identificador(nome):
    return '"' + nome.replace('"', '""') + '"'


def _formatar_contagem(valor):
    return f"{valor:,}".replace(",", ".")


def _listar_arquivos():
    arquivos = sorted(_PASTA_SQL.glob("*.sql"))
    if not arquivos:
        print(f"Nenhum arquivo .sql encontrado em {_PASTA_SQL}.", file=sys.stderr)
        raise SystemExit(1)

    sem_prefixo = []
    nomes = {}
    duplicados = set()
    arquivos_mapeados = []

    for arquivo in arquivos:
        correspondencia = _PREFIXO_NUMERICO.match(arquivo.stem)
        if correspondencia is None:
            sem_prefixo.append(arquivo.name)
            continue

        nome_tabela = correspondencia.group(1)
        if nome_tabela in nomes:
            duplicados.update((nomes[nome_tabela], arquivo.name))
        else:
            nomes[nome_tabela] = arquivo.name
        arquivos_mapeados.append((arquivo, nome_tabela))

    if sem_prefixo or duplicados:
        if sem_prefixo:
            print(
                "Arquivos sem prefixo NN_: " + ", ".join(sorted(sem_prefixo)),
                file=sys.stderr,
            )
        if duplicados:
            print(
                "Arquivos com nomes de tabela duplicados: "
                + ", ".join(sorted(duplicados)),
                file=sys.stderr,
            )
        raise SystemExit(1)

    return arquivos_mapeados


def _ler_sql(arquivo):
    sql = arquivo.read_text(encoding="utf-8").strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    return sql


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    transacao_aberta = False

    try:
        tabelas_existentes = {
            tabela
            for (tabela,) in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'refined'"
            ).fetchall()
        }
        ausentes = [
            tabela for tabela in _TABELAS_REFINED if tabela not in tabelas_existentes
        ]
        if ausentes:
            print(
                "Tabelas ausentes em refined: "
                f"{', '.join(ausentes)}. Rode "
                "'uv run python -m pipeline.transformacao'.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        arquivos = _listar_arquivos()
        con.execute("BEGIN TRANSACTION").fetchall()
        transacao_aberta = True
        con.execute("DROP SCHEMA IF EXISTS marts CASCADE").fetchall()
        con.execute("CREATE SCHEMA marts").fetchall()

        resultados = []
        total_linhas = 0
        for arquivo, nome_tabela in arquivos:
            conteudo = _ler_sql(arquivo)
            try:
                con.execute(
                    f"CREATE TABLE marts.{_identificador(nome_tabela)} AS {conteudo}"
                ).fetchall()
                contagem = int(
                    con.execute(
                        f"SELECT count(*) FROM marts.{_identificador(nome_tabela)}"
                    ).fetchall()[0][0]
                )
            except duckdb.Error as exc:
                con.execute("ROLLBACK").fetchall()
                transacao_aberta = False
                print(f"Erro em {arquivo.name}: {exc}", file=sys.stderr)
                raise SystemExit(1) from exc

            if contagem == 0:
                con.execute("ROLLBACK").fetchall()
                transacao_aberta = False
                print(f"Mart vazio: {arquivo.name}", file=sys.stderr)
                raise SystemExit(1)

            resultados.append((nome_tabela, contagem))
            total_linhas += contagem

        con.execute("COMMIT").fetchall()
        transacao_aberta = False
        for nome_tabela, contagem in resultados:
            print(
                f"✓ marts.{nome_tabela:<32} "
                f"{_formatar_contagem(contagem)} linhas"
            )
        print(
            f"Total: {len(resultados)} marts, "
            f"{_formatar_contagem(total_linhas)} linhas"
        )
    except duckdb.Error as exc:
        if transacao_aberta:
            con.execute("ROLLBACK").fetchall()
            transacao_aberta = False
        print(f"Erro ao atualizar o schema marts: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        con.close()


if __name__ == "__main__":
    main()
