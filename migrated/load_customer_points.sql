WITH order_stream AS (
   SELECT 
      o.customer_id,
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
   SELECT 
      os.*,
      FLOOR(NVL(os.amount,0) * 
            (CASE os.tier WHEN 'GOLD' THEN 2 WHEN 'SILVER' THEN 1.5 ELSE 1 END)) AS points_raw
   FROM order_stream os
),
points_signed AS (
   SELECT 
      pr.*,
      CASE WHEN pr.status = 'REFUNDED' THEN -1 ELSE 1 END * pr.points_raw AS points
   FROM points_raw pr
),
const AS (
   SELECT 1000 AS c_cap
),
recursive_bal AS (
   SELECT 
      ps.customer_id,
      ps.order_id,
      ps.order_date,
      ps.points,
      GREATEST(LEAST(0 + ps.points, (SELECT c_cap FROM const)), 0) AS balance,
      ps.order_date AS prev_order_date,
      ps.seq
   FROM (
      SELECT *
      FROM points_signed
      WHERE seq = 1
   ) ps
   
   UNION ALL
   
   SELECT 
      ps.customer_id,
      ps.order_id,
      ps.order_date,
      ps.points,
      GREATEST(LEAST(rb.balance + ps.points, (SELECT c_cap FROM const)), 0) AS balance,
      ps.order_date,
      rb.prev_order_date,
      ps.seq
   FROM recursive_bal rb
   JOIN points_signed ps
     ON ps.customer_id = rb.customer_id
    AND ps.seq = rb.seq + 1
)
SELECT 
   rb.customer_id,
   rb.order_id,
   rb.order_date,
   rb.points,
   rb.balance,
   CASE 
        WHEN rb.prev_order_date IS NULL THEN 0
        WHEN DATEDIFF('day', rb.prev_order_date, rb.order_date) = 0 THEN 0
        ELSE ROUND(rb.points / DATEDIFF('day', rb.prev_order_date, rb.order_date), 2)
    END AS points_per_day
FROM recursive_bal rb
ORDER BY rb.customer_id, rb.order_date, rb.order_id;