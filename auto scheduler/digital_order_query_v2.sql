WITH ScoreRanking AS (
    SELECT 
        docket_id,
        score_msr,
        ROW_NUMBER() OVER (
            PARTITION BY docket_id 
            ORDER BY docket_scoring_id
        ) AS rn
    FROM docket_scoring
    WHERE score_direction = 2
),

OrderTotals AS (
    SELECT
        od.docket_id,
        od.order_id,
        od.order_line_nbr,
        od.requested_dte,
        c.short_name,
        SUM(od.order_qty) AS order_qty
    FROM order_details od
    JOIN order_header oh
        ON od.order_id = oh.order_id
    LEFT JOIN track t 
        ON od.order_id = t.order_id AND od.order_line_nbr = t.order_line_nbr
    JOIN customer c  
        ON oh.customer_id = c.customer_id
    WHERE oh.status_id = 3 AND t.order_id IS NULL
    AND od.order_qty > 500
    AND od.requested_dte >= CAST(GETDATE() AS DATE)
    GROUP BY od.docket_id, od.order_line_nbr, c.short_name, od.requested_dte, od.order_id
)

-- SELECT * from OrderTotals

SELECT 
    ot.short_name AS 'Customer Name',
    ot.order_id AS 'Order #',
    ot.order_line_nbr AS 'Line #',
    d.docket_id AS [Docket Id],

    ot.order_qty AS 'Order Qty',
    ot.requested_dte AS 'Due Date',
    d.order_size1 AS [Width],
    d.order_size2 AS [Length],

    -- MAX(CASE WHEN sr.rn = 1 THEN sr.score_msr END) AS score_1,
    -- MAX(CASE WHEN sr.rn = 2 THEN sr.score_msr END) AS score_2,
    -- MAX(CASE WHEN sr.rn = 3 THEN sr.score_msr END) AS score_3,

    md.material_dsc AS 'Material',

    pd.printing_dsc AS [Printing Type],

    STRING_AGG(
        i.ink_dsc + ' ' + CAST(dp.coverage AS varchar(10)) + '%',
        ', '
    ) AS [Coverage]

FROM docket d

JOIN OrderTotals ot
    ON d.docket_id = ot.docket_id

LEFT JOIN ScoreRanking sr
    ON d.docket_id = sr.docket_id

JOIN material_dsc md
    ON d.material_id = md.material_id

JOIN printing_dsc pd
    ON d.printing_id = pd.printing_id

JOIN docket_printing dp
    ON d.docket_id = dp.docket_id

JOIN ink i
    ON dp.ink_id = i.ink_id

WHERE pd.printing_dsc LIKE '%Nozomi%'

GROUP BY
    ot.short_name,
    ot.order_line_nbr,
    ot.requested_dte,
    ot.order_id,
    d.docket_id,
    ot.order_qty,
    d.order_size1,
    d.order_size2,
    md.material_dsc,
    pd.printing_dsc;