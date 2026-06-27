
WITH FinishedTagCTE AS (
    SELECT
        order_id,
        order_line_nbr,
        MAX(CAST(finish_dte AS DATE)) AS finished_date,
        SUM(finish_qty) AS finished_qty
    FROM finished_goods
    GROUP BY order_id, order_line_nbr
)

SELECT
      c.customer_nme
    , oh.customer_id
    , od.order_id
    , od.order_line_nbr
    , od.docket_id
    , CASE  
        WHEN p.printing_dsc LIKE '%Digital%' THEN 'Digital'
        WHEN p.printing_dsc LIKE '%Flexo%' THEN 'Flexo'
        ELSE 
            'Plain'
        END AS printing_style
    , CAST(oh.order_dte as date) AS order_date
    , CAST(s.ship_date AS DATE) AS ship_date
    , CAST(od.requested_dte AS DATE) AS requested_date
    , CASE
        WHEN s.days_diff_workdays >= 2 THEN 'Early'

        WHEN s.days_diff_workdays >= 0
            AND dsd.delivery_status_dsc IN ('OT', 'CRB')
            THEN 'On Time'

        WHEN s.days_diff_workdays < 0  
            THEN 
                CASE  
                    WHEN dsd.delivery_status_dsc IN ('OT', 'CRB') THEN 'Late - Other'
                ELSE dsd.delivery_status_dsc
                END
        ELSE ISNULL(dsd.delivery_status_dsc, 'Late - Other')
    END AS on_time_dsc
    ,CASE
        WHEN dsd.delivery_status_dsc IN ('OT', 'CRB') THEN 'On Time'
        WHEN dsd.delivery_status_dsc IN ('Late') THEN 'Late - Other'
    END AS on_time_code
    ,s.days_diff_workdays
    , CASE 
          WHEN oh.order_dte IS NULL THEN 0
          ELSE
                DATEDIFF(day, CAST(pr.receipt_dte AS DATE), CAST(od.scheduled_dte AS DATE))
              - (DATEDIFF(week, CAST(oh.order_dte AS DATE), CAST(od.scheduled_dte AS DATE)) * 2)
              - CASE WHEN DATENAME(weekday, pr.receipt_dte) = 'Sunday' THEN 1 ELSE 0 END
              - CASE WHEN DATENAME(weekday, od.scheduled_dte) = 'Saturday' THEN 1 ELSE 0 END
      END AS num_days
    ,oh.order_user_id
    ,CONCAT(RTRIM(u.user_first_name), ' ', RTRIM(u.user_last_name))
    ,oh.status_id
FROM order_details od

LEFT JOIN FinishedTagCTE ftc
    ON od.order_id = ftc.order_id
   AND od.order_line_nbr = ftc.order_line_nbr
LEFT JOIN delivery_status_dsc dsd
    ON od.delivery_status_id = dsd.delivery_status_id
LEFT JOIN order_header oh
    ON od.order_id = oh.order_id
LEFT JOIN customer c
    ON oh.customer_id = c.customer_id
LEFT JOIN users u  
    ON oh.order_user_id = u.[user_id]
LEFT JOIN docket d  
    ON od.docket_id = d.docket_id
LEFT JOIN printing_dsc p  
    ON d.printing_id = p.printing_id
LEFT JOIN purchase_details pd    
    ON od.order_id = pd.order_id AND od.order_line_nbr = pd.order_line_nbr
LEFT JOIN purchase_receipts pr  
    ON pd.purchase_id = pr.purchase_id AND pd.purchase_line_nbr = pr.purchase_line_nbr

CROSS APPLY (
    SELECT
        -- 1️⃣ Final ship date
        CASE
            WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
            WHEN oh.status_id = 3 THEN
                CASE
                    WHEN DATENAME(weekday, od.scheduled_dte) = 'Friday' THEN DATEADD(day, 3, od.scheduled_dte)
                    WHEN DATENAME(weekday, od.scheduled_dte) = 'Saturday' THEN DATEADD(day, 2, od.scheduled_dte)
                    ELSE DATEADD(day, 1, od.scheduled_dte)
                END
            ELSE CAST(od.scheduled_dte AS DATE)
        END AS ship_date,

        -- 2️⃣ Working-day difference
        CASE
            WHEN ftc.finished_date IS NULL AND oh.status_id = 4 THEN
                DATEDIFF(day, od.scheduled_dte, CAST(od.requested_dte AS DATE))
              - (DATEDIFF(week, od.scheduled_dte, CAST(od.requested_dte AS DATE)) * 2)
              - CASE WHEN DATENAME(weekday, od.scheduled_dte) = 'Sunday' THEN 1 ELSE 0 END
              - CASE WHEN DATENAME(weekday, od.requested_dte) = 'Saturday' THEN 1 ELSE 0 END
            ELSE
                DATEDIFF(day,
                    CASE
                        WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
                        WHEN oh.status_id = 3 THEN
                            CASE
                                WHEN DATENAME(weekday, od.scheduled_dte) = 'Friday' THEN DATEADD(day, 3, od.scheduled_dte)
                                WHEN DATENAME(weekday, od.scheduled_dte) = 'Saturday' THEN DATEADD(day, 2, od.scheduled_dte)
                                ELSE DATEADD(day, 1, od.scheduled_dte)
                            END
                        ELSE CAST(od.scheduled_dte AS DATE)
                    END,
                    CAST(od.requested_dte AS DATE)
                )
              - (DATEDIFF(week,
                    CASE
                        WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
                        ELSE CAST(od.scheduled_dte AS DATE)
                    END,
                    CAST(od.requested_dte AS DATE)
                ) * 2)
              - CASE WHEN DATENAME(weekday,
                    CASE
                        WHEN ftc.finished_date IS NOT NULL THEN ftc.finished_date
                        ELSE CAST(od.scheduled_dte AS DATE)
                    END
                ) = 'Sunday' THEN 1 ELSE 0 END
              - CASE WHEN DATENAME(weekday, od.requested_dte) = 'Saturday' THEN 1 ELSE 0 END
        END AS days_diff_workdays
) s


WHERE
    (oh.status_id IN (3, 4))
    AND od.requested_dte >= DATEFROMPARTS(YEAR(GETDATE()), 1, 1)
    AND od.requested_dte <  DATEADD(week, DATEDIFF(week, 0, GETDATE()), 0);
