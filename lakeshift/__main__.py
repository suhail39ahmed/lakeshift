import argparse, json, os, pathlib, re, sys, tempfile, time
from lakeshift import planner, translator, fixer
from lakeshift.llm import usage, usage_report

TMP = pathlib.Path(tempfile.gettempdir())
LOCK = TMP / "lakeshift_run.lock"
PROGRESS = TMP / "lakeshift_progress.json"
LOGFILE = TMP / "lakeshift_run.log"
STALE_AFTER = 600          # seconds; a full run takes about 4 minutes

def pid_alive(pid):
    """Cross-platform check that a process id is still running."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259     # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True

def lock_info():
    """Return the live lock as a dict, or None. Stale locks are removed."""
    if not LOCK.exists():
        return None
    try:
        info = json.loads(LOCK.read_text(encoding="utf-8"))
        started = float(info.get("started", 0))
    except (OSError, ValueError, AttributeError):
        info, started = {}, LOCK.stat().st_mtime if LOCK.exists() else 0
    if time.time() - started > STALE_AFTER or not pid_alive(info.get("pid")):
        LOCK.unlink(missing_ok=True)
        return None
    return info

def take_lock():
    """Only one run at a time: every run resets the same demo tables."""
    if lock_info():
        print("Another migration is already running. Please wait a minute and try again.")
        sys.exit(3)
    LOCK.write_text(json.dumps({"pid": os.getpid(), "started": time.time()}), encoding="utf-8")

class Progress:
    """Turns the run's printed lines into a progress file and a plain-words activity feed."""
    def __init__(self):
        self.state = {"stage": "starting", "percent": 0, "done": 0, "total": 6,
                      "started": time.time(), "message": "Started run", "finished": False,
                      "events": [], "pid": os.getpid()}
        self.translated, self.oracle, self.fixes = set(), set(), {}
        self.event("Started run")

    def event(self, text, percent=None, stage=None):
        st = self.state
        if percent is not None:
            st["percent"] = max(st["percent"], min(100, int(percent)))
        if stage:
            st["stage"] = stage
        st["message"] = text
        st["events"].append([round(time.time() - st["started"]), text])
        st["events"] = st["events"][-60:]
        st["updated"] = time.time()
        tmp = PROGRESS.with_suffix(".tmp")
        tmp.write_text(json.dumps(st), encoding="utf-8")
        os.replace(tmp, PROGRESS)

    def line(self, raw):
        t = raw.strip(); n = self.state["total"] or 6
        m = re.match(r"(\d+) objects, order", t)
        if t.startswith("1/3"):
            self.event("Planning the migration", 2, "planning")
        elif m:
            self.state["total"] = int(m.group(1))
            self.event(f"Planned {m.group(1)} objects", 5, "planning")
        elif t.startswith("2/3"):
            self.event("Translating with Nemotron", 6, "translating")
        elif (m := re.match(r"=== (\w+) ===", t)):
            self.translated.add(m.group(1)); self.state["done"] = len(self.translated)
            self.event(f"Translated {m.group(1)}", 6 + 29 * len(self.translated) / n, "translating")
        elif t.startswith("3/3"):
            self.state["done"] = 0
            self.event("Verifying in Oracle and Snowflake", 36, "verifying")
        elif (m := re.match(r"oracle ran (\w+)", t)):
            self.oracle.add(m.group(1))
            self.event(f"Oracle ran {m.group(1)}", 36 + 24 * min(len(self.oracle), n) / n, "verifying")
        elif (m := re.match(r"snowflake check (\w+): (\w+)", t)):
            self.state["done"] += 1
            self.event(f"Snowflake check {m.group(1)}: {m.group(2)}", 60, "verifying")
        elif (m := re.match(r"researched (\w+)", t)):
            self.event(f"Researching docs for {m.group(1)}", 62, "fixing")
        elif (m := re.match(r"(\S+)\s+(\w+)\s+-> (\w+)", t)):
            k = self.fixes[m.group(2)] = self.fixes.get(m.group(2), 0) + 1
            self.event(f"Fixing {m.group(2)} (attempt {k}): {m.group(3)}",
                       62 + 30 * min(sum(self.fixes.values()), 3 * n) / (3 * n), "fixing")
        elif t.startswith("final:"):
            self.event("Snowflake checks finished", 95, "scorecard")
        elif (m := re.match(r"(PASS|FAIL)\w*\s+(\w+)", t)):
            self.event(f"Result {m.group(2)}: {m.group(1)}", 97, "scorecard")
        elif "snowflake session expired" in t:
            self.event("Reconnecting to Snowflake")

    def finish(self, ok, summary):
        self.state["finished"] = True
        self.event(summary, 100 if ok else None, "done" if ok else "failed")

class Tee:
    """Echo stdout to the console and a log file, feeding each line to Progress."""
    def __init__(self, stream, prog):
        self.stream, self.prog, self.buf = stream, prog, ""
        self.log = open(LOGFILE, "w", encoding="utf-8", buffering=1)
    def write(self, s):
        self.stream.write(s); self.log.write(s); self.buf += s
        while "\n" in self.buf:
            ln, self.buf = self.buf.split("\n", 1)
            try:
                self.prog.line(ln)
            except Exception:
                pass
        return len(s)
    def flush(self):
        self.stream.flush(); self.log.flush()

def main():
    ap = argparse.ArgumentParser(prog="lakeshift")
    ap.add_argument("command", choices=["run"])
    ap.add_argument("folder", nargs="?", default="legacy")
    args = ap.parse_args()

    take_lock()
    prog = Progress()
    out = sys.stdout
    sys.stdout = Tee(out, prog)
    ok, summary = False, "Run stopped with an error"
    try:
        run(args)
        rep = json.loads(pathlib.Path("migrated/report.json").read_text(encoding="utf-8"))
        passed = sum(r.get("status") == "PASS" for r in rep.values())
        ok, summary = True, f"Done: {passed}/{len(rep)} passed"
    except BaseException as e:
        summary = f"Run stopped: {type(e).__name__}"
        raise
    finally:
        try:
            sys.stdout.flush(); prog.finish(ok, summary)
        except Exception:
            pass
        sys.stdout = out
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
