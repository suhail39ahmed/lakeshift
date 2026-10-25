WITH hier AS (
    SELECT
        r.customer_id,
        r.customer_id AS root_id,
        1 AS depth,
        '/' || r.customer_id AS path,
        r.referred_by
    FROM raw_referrals r
    WHERE r.referred_by IS NULL
    UNION ALL
    SELECT
        r.customer_id,
        h.root_id,
        h.depth + 1,
        h.path || '/' || r.customer_id,
        r.referred_by
    FROM hier h
    JOIN raw_referrals r ON r.referred_by = h.customer_id
)
SELECT t.customer_id,
       t.root_id,
       t.depth,
       t.path,
       t.is_leaf
FROM referral_tree t
UNION ALL
SELECT
    h.customer_id,
    h.root_id,
    h.depth,
    h.path,
    CASE WHEN NOT EXISTS (SELECT 1 FROM hier h2 WHERE h2.referred_by = h.customer_id) THEN 1 ELSE 0 END AS is_leaf
FROM hier h