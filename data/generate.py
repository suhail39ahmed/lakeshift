import csv, random
from datetime import date, timedelta

random.seed(42)
first = ["anna", " raj ", "mei", "LUCAS", "sara", "omar", "li", "noah"]
last = ["tan", "kumar", "LEE", "smith ", "garcia", "ali", "wong", "brown"]

with open("data/raw_customers.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["customer_id", "first_name", "last_name", "email", "country",
                "signup_date", "tier_code", "is_deleted"])
    for i in range(1, 201):
        w.writerow([i, random.choice(first), random.choice(last),
                    random.choice([f"User{i}@Mail.com", ""]),       # some missing emails
                    random.choice(["SG", "IN", "US", "UK", ""]),     # some missing countries
                    date(2023, 1, 1) + timedelta(days=random.randint(0, 900)),
                    random.choice(["G", "S", "B", "X"]),
                    random.choice(["N"] * 9 + ["Y"])])

with open("data/raw_orders.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["order_id", "customer_id", "order_date", "amount", "status"])
    for i in range(1, 3001):
        w.writerow([i, random.randint(1, 200),
                    date(2025, 1, 1) + timedelta(days=random.randint(0, 660)),
                    random.choice([round(random.uniform(5, 500), 2), ""]),
                    random.choice(["PAID"] * 8 + ["CANCELLED", "REFUNDED"])])
print("done")