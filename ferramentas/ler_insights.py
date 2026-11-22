"""Le os Insights do perfil (audiencia ativa por hora, alcance por dia) e salva em catalogo/fonte/insights.json
(pasta ignorada pelo git: os dados nao vao para o GitHub publico). Nao imprime o token.

    $env:IG_ACCESS_TOKEN = Read-Host "Token"; $env:IG_USER_ID = "17841401368090740"
    python -I -X utf8 ferramentas/ler_insights.py
"""
import os, sys, json, time, urllib.request, urllib.parse, urllib.error
from pathlib import Path

tok, uid = os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("IG_USER_ID")
host = os.environ.get("GRAPH_HOST", "https://graph.facebook.com")
ver = os.environ.get("GRAPH_VERSION", "v21.0")
if not (tok and uid):
    sys.exit("Defina IG_ACCESS_TOKEN e IG_USER_ID.")
OUT = Path(__file__).resolve().parent.parent / "catalogo" / "fonte" / "insights.json"


def get(path, **p):
    p["access_token"] = tok
    try:
        with urllib.request.urlopen(f"{host}/{ver}/{path}?" + urllib.parse.urlencode(p), timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"erro": e.code, "detalhe": e.read().decode(errors="replace")[:400]}


res = {}
res["perfil"] = get(uid, fields="username,followers_count,media_count")
res["online_followers"] = get(f"{uid}/insights", metric="online_followers", period="lifetime", timeframe="last_14_days") \
    if False else get(f"{uid}/insights", metric="online_followers", period="lifetime")
now = int(time.time())
res["reach_dia"] = get(f"{uid}/insights", metric="reach", period="day", since=now - 29 * 86400, until=now)
res["views_dia"] = get(f"{uid}/insights", metric="views", period="day", metric_type="total_value", since=now - 29 * 86400, until=now)
res["midias"] = get(f"{uid}/media", fields="id,media_type,media_product_type,timestamp,like_count,comments_count", limit=50)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in res.items():
    print(k, "-> ERRO " + v["detalhe"][:200] if isinstance(v, dict) and "erro" in v else "-> ok")
print("Salvo em", OUT)
