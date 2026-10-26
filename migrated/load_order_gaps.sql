WITH base AS (
  SELECT
    o.customer_id,
    o.order_id,
    o.order_date,
    LAG(o.order_date) OVER (PARTITION BY o.customer_id ORDER BY o.order_date, o.order_id) AS prev_order_date
  FROM raw_orders o
  JOIN dim_customer d ON d.customer_id = o.customer_id
  WHERE o.status <> 'CANCELLED'
)
SELECT
  customer_id,
  order_id,
  order_date,
  prev_order_date,
  order_date - prev_order_date AS days_since_prev,
  ROUND(MONTHS_BETWEEN(order_date, prev_order_date), 2) AS months_since_prev,
  DATEADD(day, FLOOR(COALESCE(order_date - prev_order_date, 30) * 1.5), order_date) AS next_expected,
  ROUND(AVG(order_date - prev_order_date) OVER (PARTITION BY customer_id), 2) AS avg_gap_days
FROM base