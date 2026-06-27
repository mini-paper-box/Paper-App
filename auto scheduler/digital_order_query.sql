WITH ScoreRanking AS (
    SELECT 
        docket_id,
        score_msr,
        -- Number each score for this specific docket
        ROW_NUMBER() OVER(PARTITION BY docket_id ORDER BY docket_scoring_id) as rn
    FROM docket_scoring
    WHERE score_direction = 2
)
select 
d.docket_id AS 'Docket Id'
,od.order_qty
,d.order_size1 AS 'Width'
,d.order_size2 AS 'Length'
,MAX(CASE WHEN sr.rn = 1 THEN sr.score_msr END) AS score_1
,MAX(CASE WHEN sr.rn = 2 THEN sr.score_msr END) AS score_2
,MAX(CASE WHEN sr.rn = 3 THEN sr.score_msr END) AS score_3
,md.material_dsc
,pd.printing_dsc AS 'Printing Type'
FROM order_details od
JOIN order_header oh ON od.order_id = oh.order_id
JOIN docket d ON od.docket_id = d.docket_id
LEFT JOIN ScoreRanking sr ON d.docket_id = sr.docket_id
JOIN material_dsc md ON d.material_id = md.material_id
JOIN printing_dsc pd ON d.printing_id = pd.printing_id
WHERE oh.status_id = 3 AND od.order_qty > 1000 AND pd.printing_dsc LIKE '%Nozomi%'
AND od.requested_dte > '2026-04-15'
GROUP BY d.docket_id
,od.order_qty
,d.order_size1
,d.order_size2 
,md.material_dsc
,pd.printing_dsc 