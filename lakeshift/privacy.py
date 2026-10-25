"""Mask customer values before anything is sent to a model.

The fixer only needs the *shape* of a mismatch (which column, NULL vs value,
case, whitespace, length), never the real text. Equal values get the same
token on both sides, so the model can still pair up rows. The salt is random
per run, so tokens cannot be reversed by hashing guesses.
"""
import hashlib, re, secrets

SALT = secrets.token_hex(8)
stats = {"masked": 0}

def token(v):
    if v == "\u2205" or v is None:          # NULL marker from the verifier: keep
        return v
    if v == "":
        return ""  # empty string is not personal data; models need it to spot the Oracle ''=NULL trap
    if re.fullmatch(r"-?\d+(\.\d+)?|\d{4}-\d{2}-\d{2}", v):
        return v                             # numbers and dates drive aggregates: keep
    stats["masked"] += 1
    h = hashlib.sha256((SALT + v).encode()).hexdigest()[:6]
    case = "UPPER" if v.isupper() else "lower" if v.islower() else "Mixed"
    pad = " +spaces" if v != v.strip() else ""
    return f"<text#{h} len={len(v)} {case}{pad}>"

def mask_report(r):
    """Return a copy of one verifier report with sample text values masked."""
    out = dict(r)
    for k in ("sample_oracle_only", "sample_snowflake_only"):
        if k in out:
            out[k] = [[token(v) for v in row] for row in out[k]]
    return out

if __name__ == "__main__":
    demo = {"status": "FAIL", "columns": ["CUSTOMER_ID", "FULL_NAME", "TIER"],
            "sample_oracle_only": [["7.00", "Ana Silva", "GOLD"]],
            "sample_snowflake_only": [["7.00", "Ana Silva ", "\u2205"]]}
    import json
    print(json.dumps(mask_report(demo), indent=2))
    print("masked values:", stats["masked"])

