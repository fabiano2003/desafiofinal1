# Pipeline de Gestão de Recursos Empenhados

Pipeline local em Python para carregar arquivos de empenhos, transformar os
dados no DuckDB, gerar tabelas analíticas (*marts*) e consultá-las por meio de
um painel Streamlit ou de um relatório HTML estático.

O banco se chama `olist.duckdb` por decisão do projeto. As fontes atualmente
esperadas são os arquivos de empenhos listados abaixo.

## Tecnologias

- Python 3.13
- [uv](https://docs.astral.sh/uv/) para ambiente e dependências
- pandas para leitura dos arquivos tabulados
- DuckDB para armazenamento e consultas SQL
- Streamlit e Plotly para o painel
- pytest e pytest-cov para testes

## Estrutura

```text
.
├── app.py                 # Aplicação Streamlit
├── painel.py              # Leitura e apresentação dos marts
├── relatorio.py           # Geração do relatório HTML
├── ui.py                  # Interface web do DuckDB
├── olist.duckdb           # Banco local (criado pelo pipeline)
├── pipeline/
│   ├── db.py              # Conexão e operações compartilhadas do banco
│   ├── ingestao.py        # Arquivos de origem -> schema raw
│   ├── transformacao.py   # raw -> schema refined
│   └── marts.py           # SQLs -> schema marts
├── raw/                   # Arquivos de origem
├── sql/marts/             # Consultas que definem os marts
└── test/                  # Testes unitários com dados temporários
```

O pipeline separa os dados em três schemas:

- **`raw`**: cópia fiel dos arquivos de origem; todas as colunas são lidas como
  texto e os campos vazios permanecem nulos.
- **`refined`**: colunas mapeadas e tipos tratados, datas convertidas para
  `TIMESTAMP`, valores financeiros para `DECIMAL(10,2)` e duplicatas exatas
  removidas.
- **`marts`**: tabelas analíticas construídas pelos arquivos SQL em
  `sql/marts/`.

Cada etapa recria suas tabelas de destino. A ingestão exige todos os cinco
arquivos antes de começar:

| Arquivo em `raw/` | Tabela em `raw` |
|---|---|
| `plan_160.csv` | `empenhos_2026_prim` |
| `plan_167.csv` | `empenhos_2026_sec` |
| `plan_rp_160.csv` | `empenhos_2025_prim` |
| `plan_rp_167.csv` | `empenhos_2025_sec` |
| `plan_geral.csv` | `todos_empenhos` |

Os arquivos são UTF-8 e delimitados por tabulação, apesar da extensão `.csv`.
Eles devem estar em `raw/` na raiz do projeto.

## Preparação

Instale as dependências do projeto, incluindo as de desenvolvimento:

```bash
uv sync --all-groups
```

## Executar o pipeline

Execute os comandos na raiz do projeto e nesta ordem:

```bash
uv run python -m pipeline.ingestao
uv run python -m pipeline.transformacao
uv run python -m pipeline.marts
```

1. A ingestão grava os cinco arquivos no schema `raw`.
2. A transformação lê as quatro tabelas de empenhos de 2025 e 2026 e grava
   suas versões tipadas em `refined`. A tabela `raw.todos_empenhos` não é
   transformada por esta etapa.
3. O gerador de marts executa, em ordem alfabética, cada `sql/marts/*.sql` e
   recria o schema `marts` em uma transação. Cada arquivo SQL deve conter um
   único `SELECT` e ter um nome no formato `NN_nome.sql`.

O arquivo do banco é criado na raiz como `olist.duckdb`. Uma execução com
arquivos de origem ausentes, tabelas `refined` ausentes, SQL inválida ou mart
vazio termina com erro, sem publicar uma atualização parcial do schema
`marts`.

### Consultar o banco pelo DuckDB

Opcionalmente, abra a interface web do DuckDB:

```bash
uv run python ui.py
```

A interface fica disponível em <http://localhost:4213>. Interrompa o processo
com `Ctrl+C` para fechar a conexão.

## Painel e relatório

Depois de gerar os marts, inicie o painel:

```bash
uv run streamlit run app.py
```

O painel apresenta indicadores de recursos empenhados e restos a pagar,
empenhos com saldo a liquidar e gráficos por setor, Plano Interno e modalidade.
Os filtros de setor e Plano Interno recortam a tabela de notas de empenho; os
cartões mantêm os totais do período inteiro.

Para gerar o relatório HTML estático:

```bash
uv run python relatorio.py
```

O comando cria ou substitui `relatorio.html` na raiz. Abra esse arquivo no
navegador para consultar o relatório. Os gráficos usam a biblioteca Plotly
carregada do CDN, portanto a visualização dos gráficos requer conexão à
internet.

## Testes e lint

Os testes usam bancos DuckDB temporários e dados inventados; não dependem de
`olist.duckdb` nem dos arquivos de `raw/`.

```bash
uv run pytest --cov
```

A configuração exige ao menos 60% de cobertura total para `pipeline/`,
`painel.py` e `relatorio.py`. A interface Streamlit (`app.py`) e a interface
do DuckDB (`ui.py`) ficam fora da medição.

Para verificar o estilo dos arquivos Python:

```bash
uv run ruff check .
```

## Consultas SQL

Os arquivos SQL em `sql/marts/` são a fonte das regras analíticas. Para criar
um novo mart, adicione um arquivo `NN_nome.sql` com um único `SELECT` que leia
as tabelas necessárias de `refined`, e execute novamente:

```bash
uv run python -m pipeline.marts
```
