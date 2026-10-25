SELECT
    g.customer_id,
    g.order_id,
    g.order_date,
    g.prev_order_date,
    (g.order_date - g.prev_order_date) AS days_since_prev,
    ROUND(MONTHS_BETWEEN(g.order_date, g.prev_order_date), 2) AS months_since_prev,
    DATE_TRUNC('day', DATEADD('day', COALESCE(DATEDIFF('day', g.prev_order_date, g.order_date), 30) * 1.5, g.order_date)) AS next_expected,
    ROUND(AVG(g.order_date - g.prev_order_date) OVER (PARTITION BY g.customer_id), 2) AS avg_gap_days
FROM (
    SELECT
        o.customer_id,
        o.order_id,
        o.order_date,
        LAG(o.order_date) OVER (PARTITION BY o.customer_id ORDER BY o.order_date, o.order_id) AS prev_order_date
    FROM raw_orders o
    JOIN dim_customer d ON d.customer_id = o.customer_id
    WHERE o.status <> 'CANCELLED'
) g;