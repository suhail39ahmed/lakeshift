import os, json, urllib.request
from dotenv import load_dotenv

load_dotenv()
TAVILY_URL = "https://api.tavily.com/search"
DOCS = ["docs.oracle.com", "docs.snowflake.com"]     # official sources only

def research(query, max_results=4):
    """Return (evidence_text, [urls]) from official Oracle/Snowflake docs."""
    body = json.dumps({"query": query, "max_results": max_results,
                       "include_domains": DOCS, "include_answer": True}).encode()
    req = urllib.request.Request(TAVILY_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except Exception as e:
        return f"(no evidence: {type(e).__name__})", []
    lines, urls = [], []
    if data.get("answer"):
        lines.append(f"Summary: {data['answer']}")
    for i, res in enumerate(data.get("results", []), 1):
        lines.append(f"[{i}] {res['title']} ({res['url']}): {res['content'][:500]}")
        urls.append(res["url"])
    return "\n".join(lines), urls

if __name__ == "__main__":
    text, urls = research("Oracle MERGE statement does not delete unmatched target rows")
    print(text, "\n\nsources:", urls)
