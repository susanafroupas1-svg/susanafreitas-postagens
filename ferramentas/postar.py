"""Publica itens vencidos da fila (instagram/fila_postagens.json) no Instagram.

API oficial: Instagram Graph API (login do Instagram). Gratis. Sem dependencias externas.

Modo simulacao (padrao): mostra o que seria publicado, nao chama a API.
    python -I -X utf8 ferramentas/postar.py
Modo real:
    python -I -X utf8 ferramentas/postar.py --executar

Variaveis de ambiente (nunca no codigo; no GitHub use Settings > Secrets):
    IG_USER_ID        id da conta profissional do Instagram
    IG_ACCESS_TOKEN   token de longa duracao (expira em 60 dias; veja renovar_token.py)
    MEDIA_BASE_URL    URL publica da raiz do repositorio, ex.:
                      https://raw.githubusercontent.com/USUARIO/REPO/main
    GRAPH_VERSION     opcional, padrao v21.0
"""
import sys, os, json, time, argparse, datetime as dt, urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILA = ROOT / "instagram" / "fila_postagens.json"
HOST = "https://graph.instagram.com"


class ErroAPI(Exception):
    pass


def api(metodo, caminho, params, token, versao):
    url = f"{HOST}/{versao}/{caminho}"
    params = dict(params, access_token=token)
    dados = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url + ("?" + urllib.parse.urlencode(params) if metodo == "GET" else ""),
                                 data=None if metodo == "GET" else dados, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")
        raise ErroAPI(f"HTTP {e.code}: {corpo[:400]}")


def url_midia(base_url, rel):
    return base_url.rstrip("/") + "/" + urllib.parse.quote(rel.replace("\\", "/"))


def aguardar_container(cid, token, versao, tentativas=40, espera=6):
    for _ in range(tentativas):
        st = api("GET", cid, {"fields": "status_code"}, token, versao).get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise ErroAPI(f"container {cid} com status {st}")
        time.sleep(espera)
    raise ErroAPI(f"container {cid} nao ficou pronto a tempo")


def publicar(item, cfg):
    uid, tok, ver, base_url = cfg["uid"], cfg["token"], cfg["versao"], cfg["base_url"]
    tipo = item["tipo"]
    urls = [url_midia(base_url, a) for a in item["arquivos"]]
    if item.get("creation_id"):
        cid = item["creation_id"]
    elif tipo == "feed":
        cid = api("POST", f"{uid}/media", {"image_url": urls[0], "caption": item["legenda"]}, tok, ver)["id"]
    elif tipo == "story":
        cid = api("POST", f"{uid}/media", {"image_url": urls[0], "media_type": "STORIES"}, tok, ver)["id"]
    elif tipo == "carrossel":
        filhos = [api("POST", f"{uid}/media", {"image_url": u, "is_carousel_item": "true"}, tok, ver)["id"] for u in urls]
        cid = api("POST", f"{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": item["legenda"]}, tok, ver)["id"]
    elif tipo == "reel":
        cid = api("POST", f"{uid}/media", {"media_type": "REELS", "video_url": urls[0], "caption": item["legenda"], "share_to_feed": "true"}, tok, ver)["id"]
    else:
        raise ErroAPI(f"tipo desconhecido: {tipo}")
    item["creation_id"] = cid
    if tipo in ("reel", "story") or tipo == "carrossel":
        aguardar_container(cid, tok, ver)
    res = api("POST", f"{uid}/media_publish", {"creation_id": cid}, tok, ver)
    return res["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executar", action="store_true", help="publica de verdade (sem isto e so simulacao)")
    ap.add_argument("--janela-min", type=int, default=180, help="publica itens vencidos ha ate N minutos")
    ap.add_argument("--limite", type=int, default=8, help="maximo de itens por execucao")
    ap.add_argument("--agora", help="simula horario UTC (AAAA-MM-DDTHH:MM:SSZ), para testes")
    a = ap.parse_args()

    agora = dt.datetime.strptime(a.agora, "%Y-%m-%dT%H:%M:%SZ") if a.agora else dt.datetime.utcnow()
    fila = json.loads(FILA.read_text(encoding="utf-8"))
    cfg = dict(uid=os.environ.get("IG_USER_ID", ""), token=os.environ.get("IG_ACCESS_TOKEN", ""),
               base_url=os.environ.get("MEDIA_BASE_URL", "https://exemplo.invalid"), versao=os.environ.get("GRAPH_VERSION", "v21.0"))
    if a.executar and not (cfg["uid"] and cfg["token"] and os.environ.get("MEDIA_BASE_URL")):
        sys.exit("Faltam IG_USER_ID, IG_ACCESS_TOKEN ou MEDIA_BASE_URL no ambiente.")

    vencidos = []
    for it in fila:
        if it["status"] in ("publicado", "perdido"):
            continue
        quando = dt.datetime.strptime(it["publicar_em_utc"], "%Y-%m-%dT%H:%M:%SZ")
        if quando > agora:
            continue
        if (agora - quando).total_seconds() > a.janela_min * 60:
            if a.executar:
                it["status"] = "perdido"
            continue
        falta = [x for x in it["arquivos"] if not (ROOT / x).exists()]
        if falta:
            print(f"AGUARDANDO MIDIA  {it['id']}: faltam {falta}")
            continue
        vencidos.append(it)
    print(f"{len(vencidos)} item(ns) vencido(s) na janela de {a.janela_min} min (agora={agora:%Y-%m-%d %H:%M}Z)")
    publicados = 0
    for it in vencidos[: a.limite]:
        if not a.executar:
            print(f"[SIMULACAO] {it['tipo']:9s} {it['id']}  arquivos={len(it['arquivos'])}  legenda={len(it['legenda'])} caracteres")
            continue
        try:
            it["ig_media_id"] = publicar(it, cfg)
            it["status"], it["publicado_em"] = "publicado", dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            it.pop("erro", None)
            publicados += 1
            print(f"PUBLICADO {it['id']} -> {it['ig_media_id']}")
        except Exception as e:  # registra e segue com os proximos
            it["status"], it["erro"] = "erro", str(e)[:500]
            print(f"ERRO {it['id']}: {e}")
        FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.executar:
        FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{publicados} publicado(s).")


if __name__ == "__main__":
    main()
