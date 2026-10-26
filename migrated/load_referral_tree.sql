WITH RECURSIVE hier AS (
  SELECT
    r.customer_id,
    r.customer_id AS root_id,
    1 AS depth,
    '/' || r.customer_id AS path
  FROM raw_referrals r
  WHERE r.referred_by IS NULL
  UNION ALL
  SELECT
    r.customer_id,
    h.root_id,
    h.depth + 1,
    h.path || '/' || r.customer_id
  FROM raw_referrals r
  JOIN hier h ON r.referred_by = h.customer_id
)
SELECT
  h.customer_id,
  h.root_id,
  h.depth,
  h.path,
  CASE WHEN NOT EXISTS (SELECT 1 FROM raw_referrals r2 WHERE r2.referred_by = h.customer_id) THEN 1 ELSE 0 END AS is_leaf
FROM hier h