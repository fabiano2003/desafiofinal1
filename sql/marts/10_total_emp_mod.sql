-- Qual foi o total empenhado por Modelo de Licitacao no ano corrente?
-- Grão linha com os valores totais empenhados em cada tipo de licitacao.

SELECT
    MODALIDADE,
    SUM(SALDO_NE + EM_LIQUIDACAO + LIQUIDADO + PAGO) AS TOTAL_EMPENHADO
FROM (
    SELECT MODALIDADE, SALDO_NE, EM_LIQUIDACAO, LIQUIDADO, PAGO
    FROM refined.empenhos_2026_prim

    UNION ALL

    SELECT MODALIDADE, SALDO_NE, EM_LIQUIDACAO, LIQUIDADO, PAGO
    FROM refined.empenhos_2026_sec
) AS empenhos_2026
GROUP BY MODALIDADE
ORDER BY TOTAL_EMPENHADO DESC;
