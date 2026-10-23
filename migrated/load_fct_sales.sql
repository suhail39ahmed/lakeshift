WITH agg AS (
  SELECT
    TRUNC(o.order_date, 'MM') AS order_month,
    d.country,
    d.tier,
    COUNT(*) AS orders,
    SUM(NVL(o.amount, 0)) AS sum_amount,
    ROUND(SUM(NVL(o.amount, 0)), 2) AS revenue,
    ROUND(AVG(NVL(o.amount, 0)), 2) AS avg_order
  FROM raw_orders o
  JOIN dim_customer d ON d.customer_id = o.customer_id
  WHERE o.order_date >= ADD_MONTHS(TRUNC(CURRENT_DATE(), 'YYYY'), -12)
    AND o.status <> 'CANCELLED'
  GROUP BY TRUNC(o.order_date, 'MM'), d.country, d.tier
)
SELECT
  order_month,
  country,
  tier,
  orders,
  revenue,
  avg_order,
  RANK() OVER (PARTITION BY country, order_month ORDER BY sum_amount DESC) AS rank_in_country
FROM agg;