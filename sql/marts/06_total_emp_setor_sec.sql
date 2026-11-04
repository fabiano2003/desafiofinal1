--Quanto foi o total de recursos empenhados na UG secundária, em 2026, agrupados por ação orçamentária e setor responsável?
--Grão é uma linha com somatório de todos os valores empenhados por ação e por responsável.

SELECT
    AO AS "ACAO_ORCAMENTARIA",
    RESPONSAVEL AS "SETOR_RESPONSÁVEL",
    COALESCE(SUM(SALDO_NE), 0)
        + COALESCE(SUM(EM_LIQUIDACAO), 0)
        + COALESCE(SUM(LIQUIDADO), 0)
        + COALESCE(SUM(PAGO), 0) AS "TOTAL_RECURSOS_EMPENHADOS_POR_SETOR"
FROM refined.empenhos_2026_sec
GROUP BY AO, RESPONSAVEL
ORDER BY AO, RESPONSAVEL;
