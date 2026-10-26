import argparse, json, os, pathlib, sys, tempfile, time
from lakeshift import planner, translator, fixer
from lakeshift.llm import usage, usage_report

LOCK = pathlib.Path(tempfile.gettempdir(), "lakeshift_run.lock")

def take_lock():
    """Only one run at a time: every run resets the same demo tables."""
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 1200:
        print("Another migration is already running. Please wait a minute and try again.")
        sys.exit(1)
    LOCK.write_text(str(os.getpid()))

def main():
    ap = argparse.ArgumentParser(prog="lakeshift")
    ap.add_argument("command", choices=["run"])
    ap.add_argument("folder", nargs="?", default="legacy")
    args = ap.parse_args()

    take_lock()
    try:
        run(args)
    finally:
        LOCK.unlink(missing_ok=True)

def run(args):
    t0 = time.time()
    print("1/3 planning...")
    p = planner.plan(args.folder)
    print(f"    {len(p['objects'])} objects, order: {' -> '.join(p['run_order'])}")

    print("2/3 translating in parallel...")
    translator.translate_all(p, args.folder)

    print("3/3 verifying and fixing...")
    fixer.run()

    report = json.loads(pathlib.Path("migrated/report.json").read_text(encoding="utf-8"))
    log = json.loads(pathlib.Path("migrated/fix_log.json").read_text(encoding="utf-8"))
    print("\n=========== LakeShift scorecard ===========")
    for name, r in report.items():
        fixes = [l["model"].split("/")[-1] for l in log if l["object"] == name]
        if not fixes:
            how = "first try"
        elif r["status"] == "PASS":
            how = f"fixed by {fixes[-1]} (attempt {len(fixes)})"
        else:
            how = f"unsolved, last tried by {fixes[-1]}"
        print(f"  {r['status']:5} {name:22} {how}")
        for url in {u for l in log if l["object"] == name for u in l.get("sources", [])}:
            print(f"         cited: {url}")
    secs = round(time.time() - t0)
    pathlib.Path("migrated/usage.json").write_text(json.dumps(
        {"tokens": {k.split("/")[-1]: v for k, v in usage.items()}, "seconds": secs,
         "details": usage_report()}, indent=2),
        encoding="utf-8")
    print(f"  tokens: {sum(usage.values())}   time: {secs}s")

if __name__ == "__main__":
    main()
