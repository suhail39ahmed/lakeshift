CREATE OR REPLACE PROCEDURE load_order_gaps AS
BEGIN
  INSERT INTO order_gaps (customer_id, order_id, order_date, prev_order_date,
                          days_since_prev, months_since_prev, next_expected, avg_gap_days)
  SELECT g.customer_id, g.order_id, g.order_date, g.prev_order_date,
         g.order_date - g.prev_order_date,
         ROUND(MONTHS_BETWEEN(g.order_date, g.prev_order_date), 2),
         TRUNC(g.order_date + NUMTODSINTERVAL(NVL(g.order_date - g.prev_order_date, 30) * 1.5, 'DAY')),
         ROUND(AVG(g.order_date - g.prev_order_date) OVER (PARTITION BY g.customer_id), 2)
  FROM (SELECT o.customer_id, o.order_id, o.order_date,
               LAG(o.order_date) OVER (PARTITION BY o.customer_id
                                       ORDER BY o.order_date, o.order_id) AS prev_order_date
          FROM raw_orders o
          JOIN dim_customer d ON d.customer_id = o.customer_id
         WHERE o.status <> 'CANCELLED') g;
END;
