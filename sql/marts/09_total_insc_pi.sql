--Qual foi o total inscrito em RP por Plano Interno?
--Grão linha com os valores totais inscritos em RP em cada PI

SELECT
    PLANO_INTERNO,
    SUM(INSCRITO) AS TOTAL_EMPENHADO
FROM (
    SELECT PLANO_INTERNO, INSCRITO
    FROM refined.empenhos_2025_prim

    UNION ALL

    SELECT PLANO_INTERNO, INSCRITO
    FROM refined.empenhos_2025_sec
) AS empenhos_2025
GROUP BY PLANO_INTERNO
ORDER BY PLANO_INTERNO;
