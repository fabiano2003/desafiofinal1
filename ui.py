"""Interface do DuckDB pelo navegador.

Abre somente o banco existente na raiz para não criar um arquivo vazio que
pareça uma ingestão válida; se ele não existir, informa que a ingestão deve
ser executada e termina com código 1 antes de conectar. Independente da
ingestão, instala e carrega a extensão ui e chama start_ui(), que disponibiliza
a interface em localhost:4213 e abre o navegador. O processo aguarda Ctrl+C
porque o servidor vive enquanto a conexão permanece aberta; ao interromper,
fecha a conexão para liberar o arquivo e permitir uma nova ingestão. O stdout
usa UTF-8 para exibir corretamente a instrução de encerramento no Windows.
"""

import sys
from pathlib import Path
from threading import Event

import duckdb

_BANCO = Path(__file__).resolve().parent / "olist.duckdb"
_URL = "http://localhost:4213"


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    if not _BANCO.is_file():
        print(
            f"Banco não encontrado em {_BANCO}. É preciso rodar a ingestão antes.",
            file=sys.stderr,
        )
        sys.exit(1)

    con = None
    try:
        con = duckdb.connect(str(_BANCO))
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print(f"Interface disponível em {_URL}")
        print("Ctrl+C para encerrar")
        Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        if con is not None:
            con.close()


if __name__ == "__main__":
    main()
