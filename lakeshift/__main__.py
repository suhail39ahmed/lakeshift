import argparse, json, pathlib, time
from lakeshift import planner, translator, fixer
from lakeshift.llm import usage

def main():
    ap = argparse.ArgumentParser(prog="lakeshift")
    ap.add_argument("command", choices=["run"])
    ap.add_argument("folder", nargs="?", default="legacy")
    args = ap.parse_args()

    t0 = time.time()
    print("1/3 planning...")
    p = planner.plan(args.folder)
    print(f"    {len(p['objects'])} objects, order: {' -> '.join(p['run_order'])}")

    print("2/3 translating in parallel...")
    translator.translate_all(p, args.folder)

    print("3/3 verifying and fixing...")
    fixer.run()

    report = json.loads(pathlib.Path("migrated/report.json").read_text())
    log = json.loads(pathlib.Path("migrated/fix_log.json").read_text())
    print("\n=========== LakeShift scorecard ===========")
    for name, r in report.items():
        fixes = [l["model"].split("/")[-1] for l in log if l["object"] == name]
        how = f"fixed by {fixes[-1]}" if fixes else "first try"
        print(f"  {r['status']:5} {name:22} {how}")
        for url in {u for l in log if l["object"] == name for u in l.get("sources", [])}:
            print(f"         cited: {url}")
    print(f"  tokens: {sum(usage.values())}   time: {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()