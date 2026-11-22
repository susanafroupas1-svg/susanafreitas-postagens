"""Renova o token de longa duracao do Instagram (vale 60 dias; renove a cada ~45).

    $env:IG_ACCESS_TOKEN="token-atual"; python -I -X utf8 ferramentas/renovar_token.py

Imprime o novo token. Depois atualize o secret IG_ACCESS_TOKEN no GitHub
(Settings > Secrets and variables > Actions). Nao grave o token em arquivos do projeto.
"""
import os, sys, json, urllib.request, urllib.parse

tok = os.environ.get("IG_ACCESS_TOKEN")
if not tok:
    sys.exit("Defina IG_ACCESS_TOKEN no ambiente.")
url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": tok})
with urllib.request.urlopen(url, timeout=60) as r:
    d = json.loads(r.read().decode())
print("Novo token:", d["access_token"])
print("Expira em (dias):", round(d["expires_in"] / 86400))
