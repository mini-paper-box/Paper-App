WITH printing_avg AS (
    SELECT
        CASE
            WHEN d.docket_dsc LIKE '%Board and Print%' THEN 'Board and Print'
            WHEN pd.printing_dsc LIKE '%Nozomi%' THEN 'Digital'
            ELSE 'Brown Box'
        END AS printing_type,
        AVG(
            CAST((
                DATEDIFF(DAY, recv.mat_recv_dte, od.scheduled_dte)
                - (DATEDIFF(WEEK, recv.mat_recv_dte, od.scheduled_dte) * 2)
                - CASE WHEN DATEPART(WEEKDAY, recv.mat_recv_dte) = 1 THEN 1 ELSE 0 END
                - CASE WHEN DATEPART(WEEKDAY, od.scheduled_dte)  = 7 THEN 1 ELSE 0 END
            ) + 3 AS FLOAT)
        ) AS avg_workdays

    FROM order_header oh
    LEFT JOIN order_details od 
        ON oh.order_id = od.order_id
    LEFT JOIN docket d 
        ON od.docket_id = d.docket_id
    LEFT JOIN printing_dsc pd 
        ON d.printing_id = pd.printing_id
    LEFT JOIN (
        SELECT 
            order_id, 
            order_line_nbr, 
            purchase_id, 
            purchase_line_nbr,
            ROW_NUMBER() OVER (
                PARTITION BY order_id, order_line_nbr
                ORDER BY purchase_id
            ) AS rn
        FROM purchase_details
    ) pod 
        ON od.order_id = pod.order_id 
        AND od.order_line_nbr = pod.order_line_nbr
        AND pod.rn = 1
    LEFT JOIN (
        SELECT 
            purchase_id,
            purchase_line_nbr,
            MIN(receipt_dte) AS receipt_dte
        FROM purchase_receipts
        GROUP BY purchase_id, purchase_line_nbr
    ) pr 
        ON pod.purchase_id = pr.purchase_id 
        AND pod.purchase_line_nbr = pr.purchase_line_nbr
    CROSS APPLY (
        SELECT CAST(
            CASE 
                WHEN pr.receipt_dte IS NOT NULL THEN pr.receipt_dte
                ELSE DATEADD(DAY, 
                         3 + 2 * (((DATEPART(WEEKDAY, oh.order_dte) + @@DATEFIRST - 2) % 7 + 2) / 5),
                         CAST(oh.order_dte AS DATE))
            END 
        AS DATE) AS mat_recv_dte
    ) recv
    CROSS APPLY (
        SELECT
            (
                DATEDIFF(DAY, recv.mat_recv_dte, od.scheduled_dte)
                - (DATEDIFF(WEEK, recv.mat_recv_dte, od.scheduled_dte) * 2)
                - CASE WHEN DATEPART(WEEKDAY, recv.mat_recv_dte) = 1 THEN 1 ELSE 0 END
                - CASE WHEN DATEPART(WEEKDAY, od.scheduled_dte)  = 7 THEN 1 ELSE 0 END
            ) + 3 AS raw_workdays
    ) wd

    WHERE oh.status_id = 4
    AND wd.raw_workdays <= 30
    GROUP BY
        CASE
            WHEN d.docket_dsc LIKE '%Board and Print%' THEN 'Board and Print'
            WHEN pd.printing_dsc LIKE '%Nozomi%' THEN 'Digital'
            ELSE 'Brown Box'
        END
)

SELECT 
    c.short_name,
    CAST(oh.order_id AS varchar(25)) + '-' + CAST(od.order_line_nbr AS varchar(25)) AS [Order ID],
    od.docket_id AS [Docket ID],
    CASE
        WHEN d.docket_dsc LIKE '%Board and Print%' THEN 'Board and Print'
        WHEN pd.printing_dsc LIKE '%Nozomi%' THEN 'Digital'
        ELSE 'Brown Box'
    END AS printing_type,
    CAST(oh.order_dte AS DATE) AS [Order Date],
    recv.mat_recv_dte AS [Material Recv Date],
    CAST(od.scheduled_dte AS DATE) AS [Ship Date],
    CASE 
        WHEN wd.raw_workdays > 30 THEN ROUND(pa.avg_workdays, 0)
        ELSE wd.raw_workdays 
    END AS [Workdays],
    DATEPART(ISO_WEEK, od.scheduled_dte) AS [Week Number]

FROM order_header oh
LEFT JOIN order_details od 
    ON oh.order_id = od.order_id
LEFT JOIN customer c 
    ON oh.customer_id = c.customer_id 
LEFT JOIN docket d 
    ON od.docket_id = d.docket_id
LEFT JOIN printing_dsc pd 
    ON d.printing_id = pd.printing_id
LEFT JOIN (
    SELECT 
        order_id, 
        order_line_nbr, 
        purchase_id, 
        purchase_line_nbr,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, order_line_nbr
            ORDER BY purchase_id
        ) AS rn
    FROM purchase_details
) pod 
    ON od.order_id = pod.order_id 
    AND od.order_line_nbr = pod.order_line_nbr
    AND pod.rn = 1
LEFT JOIN (
    SELECT 
        purchase_id,
        purchase_line_nbr,
        MIN(receipt_dte) AS receipt_dte
    FROM purchase_receipts
    GROUP BY purchase_id, purchase_line_nbr
) pr 
    ON pod.purchase_id = pr.purchase_id 
    AND pod.purchase_line_nbr = pr.purchase_line_nbr
CROSS APPLY (
    SELECT CAST(
        CASE 
            WHEN pr.receipt_dte IS NOT NULL THEN pr.receipt_dte
            ELSE DATEADD(DAY, 
                     3 + 2 * (((DATEPART(WEEKDAY, oh.order_dte) + @@DATEFIRST - 2) % 7 + 2) / 5),
                     CAST(oh.order_dte AS DATE))
        END 
    AS DATE) AS mat_recv_dte
) recv
CROSS APPLY (
    SELECT
        (
            DATEDIFF(DAY, recv.mat_recv_dte, od.scheduled_dte)
            - (DATEDIFF(WEEK, recv.mat_recv_dte, od.scheduled_dte) * 2)
            - CASE WHEN DATEPART(WEEKDAY, recv.mat_recv_dte) = 1 THEN 1 ELSE 0 END
            - CASE WHEN DATEPART(WEEKDAY, od.scheduled_dte)  = 7 THEN 1 ELSE 0 END
        ) + 3 AS raw_workdays
) wd
LEFT JOIN printing_avg pa
    ON pa.printing_type = CASE
        WHEN d.docket_dsc LIKE '%Board and Print%' THEN 'Board and Print'
        WHEN pd.printing_dsc LIKE '%Nozomi%' THEN 'Digital'
        ELSE 'Brown Box'
    END

WHERE od.scheduled_dte BETWEEN '2026-03-02' AND '2026-03-13'
AND oh.status_id = 4;