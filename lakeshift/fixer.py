import json, pathlib, re
from lakeshift.llm import chat, NANO, SUPER, ULTRA, usage
from lakeshift.verifier import verify
from lakeshift.researcher import research

LADDER = [NANO, SUPER, ULTRA]    # cheapest first; escalate only when proof fails

SYSTEM = """You repair a Snowflake SQL translation of an Oracle PL/SQL procedure.
The harness runs:  INSERT OVERWRITE INTO <target> <your SELECT>
so you must return ONE SELECT (or WITH ... SELECT) whose rows are the COMPLETE
final contents of the target table after the legacy procedure runs.
The target table already holds its previous rows and can be read in your SELECT.
To emulate MERGE: matched rows take updated columns from the source, unmatched
target rows are kept unchanged, unmatched source rows are inserted.
Never write MERGE, INSERT, UPDATE or DELETE. No explanations, no markdown."""

def clean(sql):
    sql = re.sub(r"^```\w*|```$", "", (sql or "").strip(), flags=re.M).strip()
    m = re.search(r"(?is)\b(WITH|SELECT)\b.*", sql)      # keep from the first SELECT/WITH
    return m.group(0).strip() if m else ""
def run():
    plan = json.loads(pathlib.Path("migrated/plan.json").read_text())
    sqls = {o["name"]: pathlib.Path("migrated", o["name"] + ".sql").read_text()
            for o in plan["objects"]}
    report, log = verify(plan, sqls), []
    evidence = {}

    for model in LADDER:
        failing = [n for n, r in report.items() if r["status"] != "PASS"]
        if not failing:
            break
        for n in failing:
            obj = next(o for o in plan["objects"] if o["name"] == n)
            legacy = pathlib.Path("legacy", obj["file"]).read_text()
            if n not in evidence:                       # research once per object
                query = (f"Oracle to Snowflake: {'; '.join(obj['risks'])}. "
                         f"{report[n].get('scenario', '')}")[:400]
                evidence[n] = research(query)
                print(f"    researched {n}: {len(evidence[n][1])} doc sources")
            prompt = (f"Oracle source:\n{legacy}\n\nCurrent Snowflake SQL:\n{sqls[n]}\n\n"
                      f"Official documentation evidence:\n{evidence[n][0]}\n\n"
                      f"Verifier report:\n{json.dumps(report[n], ensure_ascii=False)[:4000]}")
            fixed = clean(chat(model, SYSTEM, prompt))
            if fixed:                       # keep last real SQL if the model rambled
                sqls[n] = fixed
        report = verify(plan, sqls)
        for n in failing:
            log.append({"object": n, "model": model, "result": report[n]["status"],
                        "sources": evidence.get(n, ("", []))[1]})
            print(f"{model.split('/')[-1]:40} {n:22} -> {report[n]['status']}")

    for n, sql in sqls.items():
        pathlib.Path("migrated", n + ".sql").write_text(sql)
    pathlib.Path("migrated/report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    pathlib.Path("migrated/fix_log.json").write_text(json.dumps(log, indent=2))
    print("\nfinal:", {n: r["status"] for n, r in report.items()})
    print("tokens:", usage)

if __name__ == "__main__":
    run()
