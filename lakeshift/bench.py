"""Benchmark Nemotron Nano translation on serverless vs a dedicated endpoint.

    python -m lakeshift.bench --target serverless --runs 1
    python -m lakeshift.bench --target dedicated --runs 3

Translation only: no Oracle or Snowflake needed. Writes migrated/bench_<target>.json.
"""
import argparse, datetime, json, os, pathlib, statistics, time
from dotenv import load_dotenv
from openai import OpenAI
from lakeshift.llm import SERVERLESS_BASE_URL, DEFAULT_NANO
from lakeshift.translator import SYSTEM

load_dotenv()


def endpoint(target):
    if target == "serverless":
        return SERVERLESS_BASE_URL, DEFAULT_NANO
    base = os.getenv("NEBIUS_DEDICATED_BASE_URL")
    model = os.getenv("NEBIUS_NANO_MODEL")
    if not base or not model:
        raise SystemExit("Set NEBIUS_DEDICATED_BASE_URL and NEBIUS_NANO_MODEL "
                         "(the endpoint's routing key) first. See docs/dedicated-endpoint.md")
    return base, model


def one_call(client, model, prompt, max_tokens):
    t0 = time.perf_counter()
    ttft, chunks, usage = None, [], None
    stream = client.chat.completions.create(
        model=model, temperature=0, max_tokens=max_tokens, stream=True,
        stream_options={"include_usage": True},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": prompt}])
    for ev in stream:
        if ev.usage:
            usage = ev.usage
        if ev.choices:
            d = ev.choices[0].delta
            piece = (getattr(d, "content", None) or getattr(d, "reasoning_content", None)
                     or getattr(d, "reasoning", None))
            if piece:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                chunks.append(piece)
    total = time.perf_counter() - t0
    out_tok = usage.completion_tokens if usage else 0
    gen_time = total - (ttft or 0)
    return {"latency_s": round(total, 3),
            "ttft_s": round(ttft, 3) if ttft is not None else None,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": out_tok,
            "tokens_per_s": round(out_tok / gen_time, 1) if gen_time > 0 else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["serverless", "dedicated"], required=True)
    ap.add_argument("--runs", type=int, default=1, help="calls per object")
    ap.add_argument("--limit", type=int, default=0, help="only the first N objects")
    ap.add_argument("--max-tokens", type=int, default=12000)
    a = ap.parse_args()

    base, model = endpoint(a.target)
    client = OpenAI(base_url=base, api_key=os.environ["NEBIUS_API_KEY"])
    objs = json.loads(pathlib.Path("migrated/plan.json").read_text(encoding="utf-8"))["objects"]
    if a.limit:
        objs = objs[:a.limit]

    calls = []
    for o in objs:
        src = pathlib.Path("legacy", o["file"]).read_text(encoding="utf-8")
        prompt = f"Risks to handle: {o['risks']}\n\nProcedure:\n{src}"
        for i in range(a.runs):
            r = one_call(client, model, prompt, a.max_tokens)
            r.update(object=o["name"], run=i + 1)
            calls.append(r)
            print(f"{o['name']:<22} run {i+1}: {r['latency_s']:>6.2f}s  ttft {r['ttft_s']}s  "
                  f"{r['completion_tokens']} out tok  {r['tokens_per_s']} tok/s")

    def med(k):
        v = [c[k] for c in calls if c[k] is not None]
        return round(statistics.median(v), 3) if v else None

    summary = {"calls": len(calls), "median_latency_s": med("latency_s"),
               "median_ttft_s": med("ttft_s"), "median_tokens_per_s": med("tokens_per_s"),
               "total_prompt_tokens": sum(c["prompt_tokens"] for c in calls),
               "total_completion_tokens": sum(c["completion_tokens"] for c in calls)}
    out = {"target": a.target, "model": model if a.target == "serverless" else "dedicated Nano",
           "max_tokens": a.max_tokens,
           "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
           "summary": summary, "calls": calls}
    path = pathlib.Path("migrated", f"bench_{a.target}.json")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(json.dumps(out, indent=2).encode("utf-8"))
    print("\nsummary:", json.dumps(summary), "\nwrote", path)


if __name__ == "__main__":
    main()
