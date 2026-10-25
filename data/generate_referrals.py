import csv, random

# deterministic, acyclic referral tree: a parent always has a smaller id
rng = random.Random(7)
with open("data/raw_referrals.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["customer_id", "referred_by"])
    depth = {}
    for i in range(1, 201):
        if i <= 12 or rng.random() < 0.08:
            parent, depth[i] = "", 1                       # a root
        else:
            parent = rng.choice([p for p in depth if depth[p] < 5])
            depth[i] = depth[parent] + 1
        w.writerow([i, parent])
print("done")
