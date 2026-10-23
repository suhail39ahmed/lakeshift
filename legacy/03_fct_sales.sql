CREATE OR REPLACE PROCEDURE load_fct_sales AS
BEGIN
  INSERT INTO fct_sales (order_month, country, tier, orders, revenue, avg_order, rank_in_country)
  SELECT TRUNC(o.order_date, 'MM'),
         d.country,
         d.tier,
         COUNT(*),
         ROUND(SUM(NVL(o.amount, 0)), 2),
         ROUND(AVG(NVL(o.amount, 0)), 2),
         RANK() OVER (PARTITION BY d.country, TRUNC(o.order_date, 'MM')
                      ORDER BY SUM(NVL(o.amount, 0)) DESC)
  FROM raw_orders o
  JOIN dim_customer d ON d.customer_id = o.customer_id
  WHERE o.order_date >= ADD_MONTHS(TRUNC(SYSDATE, 'YYYY'), -12)
    AND o.status <> 'CANCELLED'
  GROUP BY TRUNC(o.order_date, 'MM'), d.country, d.tier;
END;