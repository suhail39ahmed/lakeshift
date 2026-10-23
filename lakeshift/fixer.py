import json, pathlib, re
from lakeshift.llm import chat, NANO, SUPER, ULTRA, usage
from lakeshift.verifier import verify

LADDER = [NANO, SUPER, ULTRA]    # cheapest first; escalate only when proof fails

SYSTEM = """You repair a Snowflake SQL translation of an Oracle PL/SQL procedure.
A verifier ran the original in Oracle and the SQL in Snowflake on identical data.
The report shows rows that differ. Find the semantic cause and return ONLY the
corrected single SELECT statement. No explanations, no markdown."""

def clean(sql):
    return re.sub(r"^```\w*|```$", "", sql.strip(), flags=re.M).strip()

def run():
    plan = json.loads(pathlib.Path("migrated/plan.json").read_text())
    sqls = {o["name"]: pathlib.Path("migrated", o["name"] + ".sql").read_text()
            for o in plan["objects"]}
    report, log = verify(plan, sqls), []

    for model in LADDER:
        failing = [n for n, r in report.items() if r["status"] != "PASS"]
        if not failing:
            break
        for n in failing:
            obj = next(o for o in plan["objects"] if o["name"] == n)
            legacy = pathlib.Path("legacy", obj["file"]).read_text()
            prompt = (f"Oracle source:\n{legacy}\n\nCurrent Snowflake SQL:\n{sqls[n]}\n\n"
                      f"Verifier report:\n{json.dumps(report[n], ensure_ascii=False)[:4000]}")
            sqls[n] = clean(chat(model, SYSTEM, prompt))
        report = verify(plan, sqls)
        for n in failing:
            log.append({"object": n, "model": model, "result": report[n]["status"]})
            print(f"{model.split('/')[-1]:40} {n:22} -> {report[n]['status']}")

    for n, sql in sqls.items():
        pathlib.Path("migrated", n + ".sql").write_text(sql)
    pathlib.Path("migrated/report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    pathlib.Path("migrated/fix_log.json").write_text(json.dumps(log, indent=2))
    print("\nfinal:", {n: r["status"] for n, r in report.items()})
    print("tokens:", usage)

if __name__ == "__main__":
    run()