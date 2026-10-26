WITH cap AS (SELECT 1000 AS c_cap),
ordered AS (
  SELECT o.customer_id,
         o.order_id,
         o.order_date,
         o.amount,
         o.status,
         d.tier,
         ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY o.order_date, o.order_id) AS seq
    FROM raw_orders o
    JOIN dim_customer d ON d.customer_id = o.customer_id
   WHERE o.status <> 'CANCELLED'
),
points_raw AS (
  SELECT o.*,
         CASE o.status
           WHEN 'REFUNDED' THEN -FLOOR(NVL(o.amount,0) *
                                 CASE o.tier WHEN 'GOLD' THEN 2
                                            WHEN 'SILVER' THEN 1.5
                                            ELSE 1
                                 END)
           ELSE FLOOR(NVL(o.amount,0) *
                                 CASE o.tier WHEN 'GOLD' THEN 2
                                            WHEN 'SILVER' THEN 1.5
                                            ELSE 1
                                 END)
         END AS points
    FROM ordered o
),
recursive_cte AS (
  SELECT p.customer_id,
         p.order_id,
         p.order_date,
         p.amount,
         p.status,
         p.tier,
         p.points,
         GREATEST(LEAST(p.points, c.c_cap), 0) AS balance,
         CAST(NULL AS DATE) AS prev_date,
         p.seq AS rn
    FROM points_raw p
    CROSS JOIN cap c
    WHERE p.seq = 1
  UNION ALL
  SELECT p.customer_id,
         p.order_id,
         p.order_date,
         p.amount,
         p.status,
         p.tier,
         p.points,
         GREATEST(LEAST(r.balance + p.points, c.c_cap), 0) AS balance,
         r.order_date AS prev_date,
         r.rn + 1 AS rn
    FROM recursive_cte r
    CROSS JOIN cap c
    JOIN points_raw p
      ON p.customer_id = r.customer_id
     AND p.seq = r.rn + 1
)
SELECT customer_id,
       order_id,
       order_date,
       points,
       balance,
       CASE 
         WHEN prev_date IS NULL THEN NULL
         WHEN order_date = prev_date THEN 0
         ELSE ROUND(points / (order_date - prev_date), 2)
       END AS points_per_day
FROM recursive_cte
ORDER BY customer_id, order_date, order_id