-- Lista as NE com saldo a liquidar das quatro tabelas refined.
-- Cada linha é uma NE, agrupada por responsável e ordenada por data de emissão
-- decrescente dentro de cada responsável.

SELECT
    COD_OM AS "UG",
    PLANO_INTERNO AS "PLANO_INTERNO",
    ND AS "ND",
    DATE_DIFF('day', CAST(DATA_EMISSAO AS DATE), CURRENT_DATE) AS "DIAS",
    NE AS "NE",
    SALDO_NE AS "SALDO_NE",
    RESPONSAVEL AS "SETOR_REPONSAVEL"
FROM (
    SELECT COD_OM, PLANO_INTERNO, ND, DATA_EMISSAO, NE, SALDO_NE, RESPONSAVEL
    FROM refined.empenhos_2026_prim
    WHERE SALDO_NE <> 0.00

    UNION ALL

    SELECT COD_OM, PLANO_INTERNO, ND, DATA_EMISSAO, NE, SALDO_NE, RESPONSAVEL
    FROM refined.empenhos_2026_sec
    WHERE SALDO_NE <> 0.00

    UNION ALL

    SELECT COD_OM, PLANO_INTERNO, ND, DATA_EMISSAO, NE, SALDO_NE, RESPONSAVEL
    FROM refined.empenhos_2025_prim
    WHERE SALDO_NE <> 0.00

    UNION ALL

    SELECT COD_OM, PLANO_INTERNO, ND, DATA_EMISSAO, NE, SALDO_NE, RESPONSAVEL
    FROM refined.empenhos_2025_sec
    WHERE SALDO_NE <> 0.00
) AS empenhos_com_saldo
ORDER BY "SETOR_REPONSAVEL", DATA_EMISSAO DESC;
