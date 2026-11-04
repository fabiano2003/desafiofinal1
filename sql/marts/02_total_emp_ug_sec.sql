--Quanto foi o total de recursos empenhados na Unidade Gestora secundária?
--Grão é uma linha com somatório de todos os valores empenhados, liquidados e pagos.

SELECT
    COD_OM AS "UG_Secundaria",
    COALESCE(SUM(SALDO_NE), 0)
        + COALESCE(SUM(EM_LIQUIDACAO), 0)
        + COALESCE(SUM(LIQUIDADO), 0)
        + COALESCE(SUM(PAGO), 0) AS "TOTAL_RECURSOS_EMPENHADOS_na167"
FROM refined.empenhos_2026_sec
GROUP BY COD_OM
ORDER BY COD_OM;