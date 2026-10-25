WITH RECURSIVE tree AS (
  SELECT r.customer_id,
         r.customer_id AS root_id,
         1 AS depth,
         r.customer_id::STRING AS path,
         CASE WHEN NOT EXISTS (SELECT 1 FROM raw_referrals r2 WHERE r2.referred_by = r.customer_id) THEN 1 ELSE 0 END AS is_leaf
  FROM raw_referrals r
  WHERE r.referred_by IS NULL
  UNION ALL
  SELECT r.customer_id,
         t.root_id,
         t.depth + 1,
         t.path || '/' || r.customer_id,
         CASE WHEN NOT EXISTS (SELECT 1 FROM raw_referrals r2 WHERE r2.referred_by = r.customer_id) THEN 1 ELSE 0 END
  FROM raw_referrals r
  JOIN tree t ON r.referred_by = t.customer_id
)
SELECT customer_id,
       root_id,
       depth,
       path,
       is_leaf
FROM tree;