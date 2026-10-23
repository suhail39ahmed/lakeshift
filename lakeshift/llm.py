import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                api_key=os.environ["NEBIUS_API_KEY"])

ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
usage = {}

def chat(model, system, user):
    r = client.chat.completions.create(
        model=model, temperature=0,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    usage[model] = usage.get(model, 0) + r.usage.total_tokens
    return r.choices[0].message.content