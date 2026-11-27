"""Sincroniza o catalogo do site com a fila de postagens.

Roda ANTES de cada publicacao (veja ciclo.sh). Compara o catalogo atual do site (tabela `produtos` no Supabase,
leitura publica) com a ultima visao guardada em instagram/catalogo_visto.json:

  * peca que SAIU do site  -> itens ainda nao publicados dela na fila viram "cancelado" (nunca mais sao postados).
                              O que ja foi postado no Instagram nao e tocado.
  * peca NOVA no site      -> baixa a foto, gera as artes (story e, se couber, feed) e coloca na fila nos proximos
                              horarios livres.
  * peca que VOLTOU (mesmo id) -> reativa e libera os itens cancelados por causa da saida.

Modos:
    python -I -X utf8 ferramentas/sincronizar_catalogo.py                   # simulacao: so mostra o que faria
    python -I -X utf8 ferramentas/sincronizar_catalogo.py --executar        # aplica
    python -I -X utf8 ferramentas/sincronizar_catalogo.py --inicializar     # cria a 1a visao a partir da planilha mestre (local)
    python -I -X utf8 ferramentas/sincronizar_catalogo.py --atualizar-mestre  # traz pecas novas para a planilha mestre (local)

Ambiente: SUPABASE_URL e SUPABASE_ANON_KEY (a chave "anon" e publica, a mesma que o site usa; so le).

Travas de seguranca: se o site nao responder, vier vazio ou com menos da metade das pecas, ou se a rodada cancelar mais
de MAX_REMOCOES pecas de uma vez, NADA e alterado (use --forcar-remocoes depois de conferir).
"""
import sys, os, re, json, argparse, datetime as dt, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import base

ROOT = base.ROOT
IG = ROOT / "instagram"
FILA = IG / "fila_postagens.json"
STATUS = IG / "status_postagens.json"
VISTO = IG / "catalogo_visto.json"
MAX_REMOCOES = 10
MARCA = "catalogo:"                       # prefixo do campo `erro` nos itens cancelados por este script
FINAIS = ("publicado", "perdido", "cancelado")
HORAS_EXTRA = ["09:40", "12:40", "14:40", "17:10", "19:40", "21:10"]   # horarios fora da grade fixa do calendario
CATEGORIA_POR_NOME = {v[0]: k for k, v in base.CATEGORIAS.items()}


def agora_utc():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def id_painel(image_url):
    """Mesmo criterio de base.montar: timestamp-id do arquivo; imagens antigas do site viram 'site-N'."""
    stem = Path(image_url.split("?")[0]).stem
    return stem if re.search(r"\d{12,13}", stem) else "site-" + stem


def ler_json(p, padrao):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else padrao


def gravar_json(p, obj, **kw):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, **kw), encoding="utf-8")


# ---------------------------------------------------------------- site
def buscar_site():
    url, chave = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_ANON_KEY", "")
    if not (url and chave):
        raise RuntimeError("faltam SUPABASE_URL e SUPABASE_ANON_KEY no ambiente")
    req = urllib.request.Request(
        url.rstrip("/") + "/rest/v1/produtos?select=id,name,price,original_price,image_url,category,is_opportunity,created_at&limit=2000",
        headers={"apikey": chave, "Authorization": "Bearer " + chave})
    with urllib.request.urlopen(req, timeout=60) as r:
        dados = json.loads(r.read().decode())
    pecas = {}
    for p in dados:
        if not p.get("image_url") or not (p.get("name") or "").strip():
            continue
        pecas[id_painel(p["image_url"])] = dict(
            nome=p["name"].strip(), categoria=(p.get("category") or "").strip(), image_url=p["image_url"],
            preco_por=base.parse_preco(p.get("price")), preco_de=base.parse_preco(p.get("original_price")),
            selo=bool(p.get("is_opportunity")), cadastro=(p.get("created_at") or "")[:10])
    return pecas


# ---------------------------------------------------------------- comparacao
def comparar(atual, visto):
    pecas = visto["pecas"]
    ativas = {i for i, v in pecas.items() if v.get("situacao", "ativa") == "ativa"}
    removidas = sorted(ativas - set(atual))
    voltaram = sorted(i for i, v in pecas.items() if v.get("situacao") == "removida" and i in atual)
    novas = sorted(i for i in atual if i not in pecas)
    return removidas, voltaram, novas, ativas


def categoria_key(peca):
    return CATEGORIA_POR_NOME.get(peca["categoria"]) or base.TIPO_PARA_CATEGORIA.get(base.tipo_do_nome(peca["nome"]))


def proximo_sku(visto, cat_key):
    code = base.CATEGORIAS[cat_key][1]
    n = max([int(v["sku"][-3:]) for v in visto["pecas"].values() if v["sku"].startswith(f"SF-{code}-")] or [0])
    return f"SF-{code}-{n + 1:03d}"


# ---------------------------------------------------------------- fila
def estado_fila():
    fila = ler_json(FILA, [])
    status = ler_json(STATUS, {})
    for it in fila:
        it.update(status.get(it["id"], {}))
    return fila, status


def skus_inativos(visto):
    return {v["sku"] for v in visto["pecas"].values() if v.get("situacao") == "removida"}


def cancelar_e_liberar(visto, executar):
    """Cancela itens pendentes que citam peca removida; libera os cancelados cujas pecas voltaram."""
    fila, status = estado_fila()
    inativos = skus_inativos(visto)
    a_cancelar, a_liberar = [], []
    for it in fila:
        usados = [s for s in it["skus"] if s in inativos]
        if usados and it["status"] not in FINAIS:
            a_cancelar.append((it, usados))
        elif not usados and it["status"] == "cancelado" and str(it.get("erro", "")).startswith(MARCA):
            a_liberar.append(it)
    if executar:
        for it, usados in a_cancelar:
            status[it["id"]] = {"status": "cancelado", "erro": f"{MARCA} peca removida do site ({', '.join(usados)})"}
        for it in a_liberar:
            status.pop(it["id"], None)
        if a_cancelar or a_liberar:
            gravar_json(STATUS, status, sort_keys=True)
    return a_cancelar, a_liberar


def horarios_livres(fila, n, agora):
    """Proximos n horarios (hora local) livres, fora da grade fixa, comecando >= 40 min a frente."""
    usados = {(it["data"], it["hora_local"]) for it in fila}
    local = agora + dt.timedelta(hours=base_calendario().UTC_OFFSET_H)
    saida = []
    for d in range(0, 8):
        dia = local.date() + dt.timedelta(days=d)
        for h in HORAS_EXTRA:
            hh, mm = map(int, h.split(":"))
            if dt.datetime.combine(dia, dt.time(hh, mm)) < local + dt.timedelta(minutes=40):
                continue
            if (str(dia), h) not in usados:
                saida.append((dia, h))
                if len(saida) == n:
                    return saida
    return saida


def base_calendario():
    import calendario
    return calendario


def montar_linha(sku, peca, idp, baixar=True):
    cat_key = categoria_key(peca)
    ext = Path(peca["image_url"].split("?")[0]).suffix or ".jpg"
    destino = base.caminho_imagem(sku, peca["nome"], cat_key, ext)
    if baixar:
        base.baixar(peca["image_url"], destino)
    r = dict(sku=sku, nome=peca["nome"], categoria=cat_key, categoria_nome=base.CATEGORIAS[cat_key][0],
             preco_de=peca["preco_de"], preco_por=peca["preco_por"], selo_oportunidade=peca["selo"],
             imagem_url_origem=peca["image_url"], id_painel=idp, data_cadastro=peca["cadastro"],
             imagem_arquivo=str(destino.relative_to(base.CAT)).replace("\\", "/"))
    return base.completar_linha(r)


def publicar_novas(novas, atual, visto, executar):
    """Registra pecas novas na visao, gera artes e enfileira. Em simulacao so descreve."""
    resumo = []
    cal = None
    fila_pub = ler_json(FILA, [])
    for idp in novas:
        peca = atual[idp]
        cat_key = categoria_key(peca)
        if not cat_key or not peca["preco_por"]:
            resumo.append((idp, peca, None, "IGNORADA: sem categoria reconhecida ou sem preco (nao entra na fila)"))
            if executar:  # registra mesmo assim para nao reaparecer como "nova" todo minuto
                visto["pecas"][idp] = dict(peca, sku=f"PENDENTE-{idp}", situacao="ativa", pendente=True)
            continue
        sku = proximo_sku(visto, cat_key)
        if not executar:
            resumo.append((idp, peca, sku, "geraria story + feed (se a foto servir) e enfileiraria"))
            visto["pecas"][idp] = dict(peca, sku=sku, situacao="ativa")   # reserva o numero p/ proxima peca da simulacao
            continue
        import midia
        cal = cal or base_calendario()
        r = montar_linha(sku, peca, idp)
        arte_story = midia.arte_story(r)
        arquivos = [(("story", arte_story))]
        if r["adequada_feed"] and not r["margem_critica"]:
            arquivos.append(("feed", midia.arte_feed(r)))
        slots = horarios_livres(fila_pub, len(arquivos), agora_utc())
        for (tipo, arq), (dia, hora) in zip(arquivos, slots):
            fila_pub.append(dict(
                id=f"{dia}_{hora.replace(':', '')}_{tipo}_novo_{sku}", data=str(dia), hora_local=hora,
                publicar_em_utc=cal.utc_str(dia, hora), plataforma="instagram", tipo=tipo, skus=[sku],
                titulo=f"Novidade: {peca['nome']}", arquivos=[str(arq.relative_to(ROOT)).replace("\\", "/")],
                legenda="" if tipo == "story" else cal.legenda_single(r, 0), status="pronto"))
        visto["pecas"][idp] = dict(peca, sku=sku, situacao="ativa")
        resumo.append((idp, peca, sku, f"{len(slots)} post(s) enfileirado(s): " +
                       ", ".join(f"{t} {d} {h}" for (t, _), (d, h) in zip(arquivos, slots))))
    if executar and novas:
        fila_pub.sort(key=lambda it: (it["data"], it["hora_local"], it["tipo"]))
        gravar_json(FILA, fila_pub)
    return resumo


# ---------------------------------------------------------------- comandos
def inicializar():
    mestre = base.carregar()
    if not mestre:
        sys.exit("catalogo/produtos_mestre.json nao encontrado (rode localmente).")
    if VISTO.exists():
        sys.exit(f"{VISTO} ja existe; apague-o se quiser recriar.")
    pecas = {r["id_painel"]: dict(sku=r["sku"], nome=r["nome"], categoria=r["categoria"], image_url=r["imagem_url_origem"],
                                  preco_por=r["preco_por"], preco_de=r["preco_de"], selo=bool(r["selo_oportunidade"]),
                                  cadastro=r["data_cadastro"], situacao="ativa") for r in mestre if r.get("id_painel")}
    gravar_json(VISTO, dict(atualizado_em=agora_utc().strftime("%Y-%m-%dT%H:%M:%SZ"), pecas=pecas))
    print(f"Visao inicial criada com {len(pecas)} pecas -> {VISTO}")


def atualizar_mestre():
    """Local: traz para a planilha mestre as pecas que o robo enfileirou (usa os SKUs ja definidos em catalogo_visto)."""
    visto = ler_json(VISTO, None) or sys.exit("sem catalogo_visto.json")
    rows = base.carregar()
    skus = {r["sku"] for r in rows}
    novos = 0
    for idp, v in visto["pecas"].items():
        if v["sku"] in skus or v.get("pendente") or v.get("situacao") != "ativa":
            continue
        rows.append(montar_linha(v["sku"], v, idp))
        novos += 1
        print("mestre +", v["sku"], v["nome"])
    for r in rows:
        r.pop("categoria_nome", None)
        r["categoria"] = base.CATEGORIAS[r["categoria"]][0] if r["categoria"] in base.CATEGORIAS else r["categoria"]
    if novos:
        base.salvar(rows)
    print(f"{novos} peca(s) nova(s) na planilha mestre. Complete tamanhos/estoque/custo nas celulas amarelas.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executar", action="store_true", help="aplica as mudancas (sem isto e so simulacao)")
    ap.add_argument("--inicializar", action="store_true")
    ap.add_argument("--atualizar-mestre", action="store_true")
    ap.add_argument("--forcar-remocoes", action="store_true", help="ignora o teto de remocoes por rodada")
    a = ap.parse_args()
    if a.inicializar:
        return inicializar()
    if a.atualizar_mestre:
        return atualizar_mestre()

    visto = ler_json(VISTO, None)
    if not visto:
        print("AVISO: instagram/catalogo_visto.json nao existe; rode --inicializar uma vez. Nada feito.")
        return 0
    try:
        atual = buscar_site()
    except Exception as e:
        print(f"AVISO: nao consegui ler o catalogo do site ({e}). Nada foi alterado; a fila segue como esta.")
        return 0
    removidas, voltaram, novas, ativas = comparar(atual, visto)
    modo = "EXECUTANDO" if a.executar else "SIMULACAO"
    print(f"[{modo}] site={len(atual)} pecas | visao anterior={len(ativas)} ativas | "
          f"removidas={len(removidas)} voltaram={len(voltaram)} novas={len(novas)}")
    if len(atual) < max(1, len(ativas) // 2):
        print(f"ABORTADO: o site devolveu so {len(atual)} peca(s) (esperado ~{len(ativas)}). Parece falha de leitura; nada alterado.")
        return 0
    if len(removidas) > MAX_REMOCOES and not a.forcar_remocoes:
        print(f"ABORTADO: {len(removidas)} remocoes numa rodada (teto {MAX_REMOCOES}). Confira a lista e rode com --forcar-remocoes:")
        for i in removidas:
            print(f"   - {visto['pecas'][i]['sku']}  {visto['pecas'][i]['nome']}")
        return 0

    hoje = agora_utc().strftime("%Y-%m-%d")
    for i in removidas:
        visto["pecas"][i].update(situacao="removida", removida_em=hoje)
    for i in voltaram:
        visto["pecas"][i].update(situacao="ativa")
        visto["pecas"][i].pop("removida_em", None)
    for i in set(atual) & ativas:   # mantem nome/preco/foto atualizados
        visto["pecas"][i].update({k: atual[i][k] for k in ("nome", "preco_por", "preco_de", "selo", "image_url")})

    for i in removidas:
        v = visto["pecas"][i]
        print(f"  SAIU   {v['sku']}  {v['nome']}  (R$ {v['preco_por']})")
    for i in voltaram:
        print(f"  VOLTOU {visto['pecas'][i]['sku']}  {visto['pecas'][i]['nome']}")

    canc, lib = cancelar_e_liberar(visto, a.executar)
    for it, usados in canc:
        print(f"  {'CANCELADO' if a.executar else 'cancelaria'}  {it['id']:42s} {it['tipo']:9s} {it['data']} {it['hora_local']}  ({', '.join(usados)})")
    for it in lib:
        print(f"  {'LIBERADO' if a.executar else 'liberaria'}   {it['id']}")
    ja_postados = []
    fila, _ = estado_fila()
    inat = skus_inativos(visto)
    for it in fila:
        if it["status"] == "publicado" and any(s in inat for s in it["skus"]):
            ja_postados.append(it)
    if ja_postados:
        print(f"  (mantidos no Instagram, ja publicados: {len(ja_postados)} -> " + ", ".join(it["id"] for it in ja_postados) + ")")

    for idp, peca, sku, msg in publicar_novas(novas, atual, visto, a.executar):
        print(f"  NOVA   {sku or '-':11s} {peca['nome']}  R$ {peca['preco_por']}  [{peca['categoria']}]  -> {msg}")

    if a.executar:
        visto["atualizado_em"] = agora_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        gravar_json(VISTO, visto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
