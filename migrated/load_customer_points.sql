WITH ordered AS (
  SELECT
    r.customer_id,
    r.order_id,
    r.order_date,
    r.amount,
    r.status,
    d.tier,
    ROW_NUMBER() OVER (PARTITION BY r.customer_id ORDER BY r.order_date, r.order_id) AS seq
  FROM raw_orders r
  JOIN dim_customer d ON d.customer_id = r.customer_id
  WHERE r.status <> 'CANCELLED'
),
recursive_loop AS (
  SELECT
    o.customer_id,
    o.order_id,
    o.order_date,
    o.amount,
    o.status,
    o.tier,
    o.seq,
    CASE WHEN o.status = 'REFUNDED' THEN -1 ELSE 1 END * FLOOR(NVL(o.amount,0) * (CASE o.tier WHEN 'GOLD' THEN 2 WHEN 'SILVER' THEN 1.5 ELSE 1 END)) AS v_points,
    GREATEST(LEAST(
        CASE WHEN o.status = 'REFUNDED' THEN -1 ELSE 1 END * FLOOR(NVL(o.amount,0) * (CASE o.tier WHEN 'GOLD' THEN 2 WHEN 'SILVER' THEN 1.5 ELSE 1 END)),
        1000), 0) AS v_balance,
    o.order_date AS v_prev_date,
    CAST(NULL AS NUMBER) AS v_per_day
  FROM ordered o
  WHERE o.seq = 1
  UNION ALL
  SELECT
    o.customer_id,
    o.order_id,
    o.order_date,
    o.amount,
    o.status,
    o.tier,
    o.seq,
    CASE WHEN o.status = 'REFUNDED' THEN -1 ELSE 1 END * FLOOR(NVL(o.amount,0) * (CASE o.tier WHEN 'GOLD' THEN 2 WHEN 'SILVER' THEN 1.5 ELSE 1 END)) AS v_points,
    GREATEST(LEAST(l.v_balance + 
        CASE WHEN o.status = 'REFUNDED' THEN -1 ELSE 1 END * FLOOR(NVL(o.amount,0) * (CASE o.tier WHEN 'GOLD' THEN 2 WHEN 'SILVER' THEN 1.5 ELSE 1 END)),
        1000), 0) AS v_balance,
    o.order_date AS v_prev_date,
    CASE 
      WHEN DATEDIFF('day', l.v_prev_date, o.order_date) = 0 THEN 0
      ELSE ROUND(
            CASE WHEN o.status = 'REFUNDED' THEN -1 ELSE 1 END * FLOOR(NVL(o.amount,0) * (CASE o.tier WHEN 'GOLD' THEN 2 WHEN 'SILVER' THEN 1.5 ELSE 1 END))
            / DATEDIFF('day', l.v_prev_date, o.order_date), 2)
    END AS v_per_day
  FROM ordered o
  JOIN recursive_loop l ON o.customer_id = l.customer_id AND o.seq = l.seq + 1
)
SELECT
  customer_id,
  order_id,
  order_date,
  v_points AS points,
  v_balance AS balance,
  v_per_day AS points_per_day
FROM recursive_loop
ORDER BY customer_id, order_date, order_id