# Dedicated endpoint benchmark (Nemotron 3 Nano)

Goal: run the LakeShift Nano translation step on a **dedicated** Nebius Token Factory endpoint,
compare it with serverless, then stop the endpoint.

**Status:** done live on Oct 26, 2026, then stopped. LakeShift runs on serverless by default; the
dedicated buttons in the app stay greyed out until the two variables below are set. Budget: about 20 minutes, about **$1.50**.

## Facts (checked against the Nebius docs)

- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` is a dedicated-endpoint template (flavor `base`, FP8):
  `gpu-h100-sxm` in `eu-north1` (1, 2 or 4 GPUs) or `gpu-h200-sxm` in `us-central1`.
  Super and Ultra are not offered as dedicated templates, so they stay on serverless.
- Billing is per GPU-hour with per-minute granularity, only while the endpoint is `Ready`.
  Provisioning, `Not ready`, and a stopped endpoint are not billed.
  H100 is listed at $4.50/GPU-hour, so 1 GPU x 20 min is about $1.50.
- Inference uses the same OpenAI-compatible API. The `model` is the endpoint's **routing key**,
  and the base URL depends on the region (`eu-north1`: `https://api.tokenfactory.nebius.com/v1/`,
  `us-central1`: `https://api.tokenfactory.us-central1.nebius.com/v1/`).
- Stopping releases the GPU. You may not get the same capacity back immediately.

Docs: [overview](https://docs.tokenfactory.nebius.com/ai-models-inference/dedicated-endpoints/overview),
[deploy in UI](https://docs.tokenfactory.nebius.com/ai-models-inference/dedicated-endpoints/deploy-ui),
[deploy via API](https://docs.tokenfactory.nebius.com/ai-models-inference/dedicated-endpoints/deploy-api),
[operating](https://docs.tokenfactory.nebius.com/ai-models-inference/dedicated-endpoints/operating),
[billing](https://docs.tokenfactory.nebius.com/ai-models-inference/dedicated-endpoints/billing-policy),
[prices](https://nebius.com/prices).

## Checklist

1. **Serverless baseline first (no endpoint running yet):**
   `python -m lakeshift.bench --target serverless --runs 1`
2. **Create the endpoint:** https://tokenfactory.nebius.com/endpoints, then create a dedicated endpoint:
   model `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, flavor `base`, `gpu-h100-sxm`, **1 GPU**,
   region `eu-north1`, **min replicas 1, max replicas 1**. Note the time it turns `Ready`.
3. **Copy the routing key** from the endpoint card and set it in PowerShell:
   ```powershell
   $env:NEBIUS_NANO_MODEL = "<routing key>"
   $env:NEBIUS_DEDICATED_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
   ```
4. **Run the benchmark** (same prompts, same settings):
   `python -m lakeshift.bench --target dedicated --runs 1`
   A 404 right after `Ready` means routing is still warming up; wait a minute and retry.
5. **Optional, for the video:** with the variables set, `streamlit run app.py`, open the Dedicated endpoint
   tab and click **Run migration on dedicated endpoint** (live only while the variables are set).
6. **STOP the endpoint** right away: open the endpoint card, then Stop (or Delete). Wait until it shows
   `Stopped` / `Not ready`.
7. **Screenshot the stopped status** and save it as `docs/dedicated-stopped.png`.
8. Clear the variables so the normal pipeline goes back to serverless:
   ```powershell
   Remove-Item Env:NEBIUS_NANO_MODEL, Env:NEBIUS_DEDICATED_BASE_URL
   ```
9. Commit `migrated/bench_serverless.json`, `migrated/bench_dedicated.json` and the screenshot.

Expected cost: about **$1.50** for 20 minutes on 1 H100. Leaving it on overnight costs over $50.


## Results (Oct 26, 2026)

| | Serverless | Dedicated (1x H100) |
|---|---|---|
| Median tokens/s | 124 | 307 |
| Median time per object | 12.1 s | 8.2 s |
| Median time to first token | 0.82 s | 0.73 s |
| Cold start | none | 32 s on the first call |

About 2.5x faster generation. For LakeShift's bursty workload serverless stays cheaper; dedicated pays off only at roughly 460+ full runs per hour.

