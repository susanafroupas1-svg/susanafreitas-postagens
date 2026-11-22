"""Confere se o token e o ID da conta do Instagram estao corretos, SEM imprimir o token.

PowerShell:
    $env:IG_ACCESS_TOKEN = Read-Host "Cole o token"
    $env:IG_USER_ID = "17841401368090740"
    python -I -X utf8 ferramentas/verificar_conexao.py

Mostra o @ da conta, o limite de publicacoes do dia e se o token consegue ler o perfil.
"""
import os, sys, json, urllib.request, urllib.parse, urllib.error

tok = os.environ.get("IG_ACCESS_TOKEN")
uid = os.environ.get("IG_USER_ID")
host = os.environ.get("GRAPH_HOST", "https://graph.facebook.com")
ver = os.environ.get("GRAPH_VERSION", "v21.0")
if not (tok and uid):
    sys.exit("Defina IG_ACCESS_TOKEN e IG_USER_ID no ambiente.")


def get(path, **params):
    params["access_token"] = tok
    url = f"{host}/{ver}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"erro": e.code, "detalhe": e.read().decode(errors="replace")[:300]}


perfil = get(uid, fields="id,username,name")
print("perfil:", {k: v for k, v in perfil.items()})
limite = get(f"{uid}/content_publishing_limit", fields="quota_usage,config")
print("limite de publicacao:", limite)
print("OK" if perfil.get("username") else "FALHOU: confira o ID, as permissoes e se a conta foi atribuida ao usuario do sistema.")
