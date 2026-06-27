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
    WHERE oh.status_id = 3 
      AND t.order_id IS NULL
      AND od.order_qty > 50
    --   AND od.requested_dte >= CAST(GETDATE() AS DATE)
      AND od.requested_dte < CAST(DATEADD(day, 24, GETDATE()) AS DATE)
    GROUP BY od.docket_id, od.order_id, od.order_line_nbr, od.requested_dte, c.short_name
),

-- Isolate multi-channel ink rows into a single string per docket
InkCoverageAggregated AS (
    SELECT 
        dp.docket_id,
        STRING_AGG(i.ink_dsc + ' ' + CAST(dp.coverage AS varchar(10)) + '%', ', ') AS [Coverage]
    FROM docket_printing dp
    JOIN ink i ON dp.ink_id = i.ink_id
    -- 💡 FIX: Drop the "Coated Digital 0%" row completely before string concatenation occurs
    WHERE i.ink_dsc NOT LIKE '%Coated Digital%'
    GROUP BY dp.docket_id
)

SELECT 
    ot.short_name AS [Customer Name],
    ot.order_id AS [Order #],
    ot.order_line_nbr AS [Line #],
    d.docket_id AS [Docket Id],
    (CAST(ot.order_qty / d.net_out AS INT)) AS [Order Qty],
    CAST(ot.requested_dte AS Date) AS [Due Date],
    d.order_size1 AS [Width],
    d.order_size2 AS [Length],
    md.material_dsc AS [Material],
    pd.printing_dsc AS [Printing Type], -- Cleaned up back to standard column grab
    COALESCE(ica.[Coverage], 'No Ink Data') AS [Coverage]

FROM docket d
JOIN OrderTotals ot
    ON d.docket_id = ot.docket_id
JOIN material_dsc md
    ON d.material_id = md.material_id
JOIN printing_dsc pd
    ON d.printing_id = pd.printing_id
LEFT JOIN InkCoverageAggregated ica
    ON d.docket_id = ica.docket_id
LEFT JOIN ScoreRanking sr
    ON d.docket_id = sr.docket_id 

WHERE pd.printing_dsc LIKE '%Nozomi%'

GROUP BY
    ot.short_name,
    ot.order_id,
    ot.order_line_nbr,
    d.docket_id,
    ot.order_qty,
    ot.requested_dte,
    d.net_out,
    d.order_size1,
    d.order_size2,
    md.material_dsc,
    pd.printing_dsc,
    ica.[Coverage];