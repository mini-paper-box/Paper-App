UPDATE orders AS o
SET status = 'Closed'
WHERE o.status = 'Active'
  AND NOT EXISTS (
    SELECT 1
    FROM order_routing AS o_r
    WHERE o_r.order_id = o.order_id
);

SELECT * FROM orders WHERE status = "Active";