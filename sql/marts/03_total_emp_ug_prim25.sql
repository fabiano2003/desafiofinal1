--Quanto foi o total de recursos inscritos em restos a pagar na Unidade Gestora primária?
--Grão é uma linha com somatório de todos os valores inscritos em RP no ano anterior.

SELECT
    COD_OM AS "UG_Primaria",
    COALESCE(SUM(INSCRITO), 0)
        + COALESCE(SUM(INSCEMLIQ), 0)
        + COALESCE(SUM(REINSCRITO), 0)
        + COALESCE(SUM(REINSCEMLIQ), 0)
        + COALESCE(SUM(BLOQUEADOALIQ), 0)
        + COALESCE(SUM(SALDO_NE), 0)
        + COALESCE(SUM(EM_LIQUIDACAO), 0)
        + COALESCE(SUM(A_PAGAR), 0)
        + COALESCE(SUM(PAGO), 0)
        + COALESCE(SUM(CANCELADO), 0) AS "TOTAL_RECURSOS_EMPENHADOS_2025"
FROM refined.empenhos_2025_prim
GROUP BY COD_OM
ORDER BY COD_OM;
