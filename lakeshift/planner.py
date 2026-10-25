import json, pathlib, re
from lakeshift.llm import chat, ULTRA, usage

SYSTEM = """You are a senior data migration architect.
Given legacy Oracle PL/SQL procedures, return ONLY JSON:
{"objects":[{"name":str,"file":str,"reads":[str],"writes":[str],
  "risks":[str]}],"run_order":[str]}
risks = Oracle-specific features that are easy to mistranslate
(e.g. NVL empty-string semantics, DECODE null matching).
name = the PROCEDURE name (a file may also hold a PACKAGE it depends on).
writes = the target table the procedure inserts into.
run_order must put every object after the objects that write the tables it reads."""

def plan(folder="legacy"):
    files = sorted(pathlib.Path(folder).glob("*.sql"))
    corpus = "\n\n".join(f"-- FILE: {f.name}\n{f.read_text()}" for f in files)
    raw = chat(ULTRA, SYSTEM, corpus)
    raw = re.search(r"\{.*\}", raw, re.S).group(0)   # strip any extra text
    return json.loads(raw)

if __name__ == "__main__":
    p = plan()
    print(json.dumps(p, indent=2))
    print("tokens:", usage)