SELECT
    TRUNC(o.order_date, 'MM') AS order_month,
    d.country,
    d.tier,
    COUNT(*) AS orders,
    ROUND(SUM(NVL(o.amount, 0)), 2) AS revenue,
    ROUND(AVG(NVL(o.amount, 0)), 2) AS avg_order,
    RANK() OVER (PARTITION BY d.country, TRUNC(o.order_date, 'MM')
                 ORDER BY SUM(NVL(o.amount, 0)) DESC) AS rank_in_country
FROM raw_orders o
JOIN dim_customer d ON d.customer_id = o.customer_id
WHERE o.order_date >= ADD_MONTHS(TRUNC(CURRENT_DATE(), 'YYYY'), -12)
  AND o.status <> 'CANCELLED'
GROUP BY TRUNC(o.order_date, 'MM'), d.country, d.tier;