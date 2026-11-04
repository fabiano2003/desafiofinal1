"""Spec e execução da ingestão fiel para o schema raw.

O mapa completo é plan_160.csv -> empenhos_2026_prim,
plan_167.csv -> empenhos_2026_sec, plan_rp_160.csv -> empenhos_2025_prim,
plan_rp_167.csv -> empenhos_2025_sec e plan_geral.csv -> todos_empenhos.
Os nomes em português são o vocabulário previsto para os JOINs seguintes.

Os cinco arquivos são conferidos antes de abrir o banco; se algum faltar, o
script lista os nomes e a pasta e termina com código 1 para não gravar apenas
parte das tabelas. A leitura declara UTF-8 e tabulação, infere a compressão
pela extensão para ler .csv.gz diretamente, força todas as colunas a texto e
trata somente campos vazios como nulos. Isso preserva o dado recebido: nenhuma
linha ou coluna é removida, deduplicada, renomeada ou corrigida, pois a
conversão pertence à passagem de raw para refined.

Cada tabela é substituída a cada execução para que repetir o comando não
acumule registros. A tela mostra uma linha por tabela qualificada, com a
contagem consultada no banco e milhar separado por ponto, além da soma final,
para que a própria saída permita conferir a carga. O stdout usa UTF-8 para
preservar a saída no Windows. A conexão é fechada ao final para devolver o
terminal e liberar o arquivo do banco.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

_ARQUIVOS_TABELAS = (
    ("plan_160.csv", "empenhos_2026_prim"),
    ("plan_167.csv", "empenhos_2026_sec"),
    ("plan_rp_160.csv", "empenhos_2025_prim"),
    ("plan_rp_167.csv", "empenhos_2025_sec"),
    ("plan_geral.csv", "todos_empenhos"),
)


def _formatar_contagem(contagem):
    return f"{contagem:,}".replace(",", ".")


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    ausentes = [
        arquivo
        for arquivo, _ in _ARQUIVOS_TABELAS
        if not (PASTA_RAW / arquivo).is_file()
    ]
    if ausentes:
        print(f"Arquivos não encontrados na pasta {PASTA_RAW}:", file=sys.stderr)
        for arquivo in ausentes:
            print(f"  {arquivo}", file=sys.stderr)
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, "raw")
        total = 0

        for arquivo, tabela in _ARQUIVOS_TABELAS:
            df = pd.read_csv(
                PASTA_RAW / arquivo,
                encoding="utf-8",
                compression="infer",
                sep="\t",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
                skip_blank_lines=False,
            )
            contagem = gravar(con, df, "raw", tabela)
            total += contagem
            print(f"raw.{tabela}: {_formatar_contagem(contagem)}")

        print(f"Total: {_formatar_contagem(total)}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
