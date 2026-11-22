"""Base mestre de produtos da Susana Freitas Store.

Funcoes compartilhadas: parsing de precos, SKU, tipo/cor, geracao de campos para
marketplaces, gravacao em JSON/CSV/XLSX e importacao do arquivo exportado do painel.

Uso:
    python -I ferramentas/base.py montar            # (re)constroi a base a partir de catalogo/fonte/painel_*.json
    python -I ferramentas/base.py montar --sem-download
"""
import sys, re, json, csv, unicodedata, urllib.request, datetime, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / "catalogo"
IMG = CAT / "imagens"
ENTRADA = CAT / "entrada"
FONTE = CAT / "fonte"
MESTRE_JSON = CAT / "produtos_mestre.json"
MESTRE_CSV = CAT / "produtos_mestre.csv"
MESTRE_XLSX = CAT / "produtos_mestre.xlsx"

MARKUP = 2.05          # premissa: preco cheio = 2,0 a 2,1 x custo (ajustavel na planilha)
SITE = "https://susanafreitasstore.com.br/"
SITE_CATALOGO = SITE + "#/catalogo"
WHATS_DISPLAY = "(16) 99378-9775"   # numero publico configurado no site
WHATS_LINK = "https://wa.me/5516993789775"

CATEGORIAS = {
    "BLUSAS": ("Blusas", "BLU"),
    "VESTIDOS": ("Vestidos", "VES"),
    "CALÇAS": ("Calças", "CAL"),
    "SAIAS": ("Saias", "SAI"),
    "CONJUNTOS & COLETES": ("Conjuntos & Coletes", "CJT"),
    "TRICÔS": ("Tricôs", "TRI"),
}
CODE_TO_KEY = {v[1]: k for k, v in CATEGORIAS.items()}

TIPO_PARA_CATEGORIA = {
    "vestido": "VESTIDOS", "macacao": "VESTIDOS", "blusa": "BLUSAS", "top": "BLUSAS", "regata": "BLUSAS",
    "polo": "BLUSAS", "camisa": "BLUSAS", "cropped": "BLUSAS", "t-shirt": "BLUSAS", "chemise": "BLUSAS",
    "calca": "CALÇAS", "shorts": "CALÇAS", "saia": "SAIAS", "conjunto": "CONJUNTOS & COLETES",
    "colete": "CONJUNTOS & COLETES", "casaco": "CONJUNTOS & COLETES", "trico": "TRICÔS",
}

CORES = [
    ("off-white", "Off-white"), ("off white", "Off-white"), ("branco", "Branco"), ("preto", "Preto"),
    ("marinho", "Azul-marinho"), ("azul", "Azul"), ("verde", "Verde"), ("vermelho", "Vermelho"),
    ("rosa", "Rosa"), ("bege", "Bege"), ("marrom", "Marrom"), ("cafe", "Café"), ("espresso", "Espresso"),
    ("chumbo", "Cinza-chumbo"), ("cinza", "Cinza"), ("vanilla", "Vanilla"), ("natural", "Natural"),
    ("olivia", None),
]
DETALHES = ["listrad", "vichy", "poa", "risca de giz", "estampad", "bordad", "renda", "gorgorao", "trico",
            "jeans", "laise", "babado", "recorte", "alfaiataria", "midi", "longo", "cropped", "balloon", "barrel"]

HASHTAGS_TIPO = {
    "vestido": ["#vestidofeminino", "#vestidoselegantes"], "blusa": ["#blusafeminina", "#blusaselegantes"],
    "calca": ["#calcafeminina", "#calcas"], "saia": ["#saiafeminina", "#saias"],
    "conjunto": ["#conjuntofeminino", "#conjuntoelegante"], "colete": ["#colete", "#conjuntoelegante"],
    "top": ["#topfeminino"], "regata": ["#regata"], "shorts": ["#shortsfeminino"], "polo": ["#polofeminina"],
    "camisa": ["#camisafeminina"], "casaco": ["#casacofeminino"], "macacao": ["#macacao"],
    "trico": ["#tricot", "#modainverno"], "t-shirt": ["#tshirt"], "cropped": ["#cropped"], "chemise": ["#chemise"],
}
HASHTAGS_BASE = ["#modafeminina", "#modaelegante", "#boutiquefeminina", "#modadelivery", "#francasp"]

CAMPOS_PENDENTES = [
    "tamanhos_disponiveis", "estoque_total", "composicao_tecido", "modelagem_caimento", "medidas_cm",
    "marca_origem", "fornecedor", "custo_real", "peso_embalagem_g", "dim_embalagem_cm", "ncm", "gtin_ean",
]
COLUNAS = [
    "sku", "nome", "categoria", "tipo", "cor", "detalhes_no_nome", "preco_de", "preco_por", "em_promocao",
    "selo_oportunidade", "desconto_pct", "custo_estimado", "margem_estimada_pct", "margem_critica",
    "imagem_arquivo", "imagem_largura", "imagem_altura", "proporcao", "adequada_feed", "adequada_story",
    "imagem_url_origem", "id_painel", "data_cadastro", "titulo_marketplace", "descricao_rascunho",
    "palavras_chave", "hashtags", "link_catalogo",
] + CAMPOS_PENDENTES + ["status_dados", "campos_pendentes", "alertas_cadastro"]


def sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(s).lower()).strip("-")


def parse_preco(s):
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})", s or "")
    if not m:
        return None
    t = m.group(1)
    return float(t.replace(".", "").replace(",", ".")) if "," in t else float(t)


def brl(v):
    if v is None or v == "":
        return ""
    return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tipo_do_nome(nome):
    t = sem_acento(nome).lower().split()[0] if nome.strip() else ""
    return "trico" if t == "tricot" else t


def tipo_legivel(t):
    return {"trico": "Tricô", "macacao": "Macacão", "calca": "Calça", "t-shirt": "T-Shirt"}.get(t, t.capitalize())


def cor_do_nome(nome):
    n = " " + sem_acento(nome).lower() + " "
    for chave, rotulo in CORES:
        if rotulo and f" {chave} " in n:
            return rotulo
    return ""


def detalhes_do_nome(nome):
    n = sem_acento(nome).lower()
    return ", ".join(sorted({d.rstrip("d") if d in ("estampad", "bordad", "listrad") else d for d in DETALHES if d in n}))


def data_do_arquivo(url_ou_nome):
    m = re.search(r"(\d{12,13})", url_ou_nome or "")
    if not m:
        return ""
    return datetime.datetime.fromtimestamp(int(m.group(1)) / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")


def dimensoes(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (0, 0)


def completar_linha(r):
    """Recalcula todos os campos derivados de uma linha (sem tocar nos campos manuais)."""
    nome = r["nome"].strip()
    t = tipo_do_nome(nome)
    r["tipo"] = tipo_legivel(t)
    r["cor"] = r.get("cor") or cor_do_nome(nome)
    r["detalhes_no_nome"] = detalhes_do_nome(nome)
    de, por = r.get("preco_de") or None, r.get("preco_por") or None
    cheio = de or por
    r["em_promocao"] = bool(de and por and de > por)
    r["desconto_pct"] = round((1 - por / de) * 100, 1) if r["em_promocao"] else 0
    custo_real = r.get("custo_real") or None
    custo = custo_real or (round(cheio / MARKUP, 2) if cheio else None)
    r["custo_estimado"] = custo
    r["margem_estimada_pct"] = round((por - custo) / por * 100, 1) if (por and custo) else None
    r["margem_critica"] = bool(r["margem_estimada_pct"] is not None and r["margem_estimada_pct"] < 25)
    ext = Path(r.get("imagem_arquivo", "")).suffix
    p = ROOT / "catalogo" / r["imagem_arquivo"] if r.get("imagem_arquivo") else None
    if p and p.exists():
        w, h = dimensoes(p)
        r["imagem_largura"], r["imagem_altura"] = w, h
        r["proporcao"] = round(w / h, 3) if h else None
        r["adequada_feed"] = bool(h and w >= 1000 and 0.75 <= w / h <= 0.82)
        r["adequada_story"] = bool(h and w >= 1000 and 0.55 <= w / h <= 0.58)
    r["titulo_marketplace"] = (nome + " Feminino")[:60]
    corr = f" Cor: {r['cor']}." if r["cor"] else ""
    r["descricao_rascunho"] = (f"{nome}. {tipo_legivel(t)} feminino com curadoria Susana Freitas Store.{corr} "
                               "[REVISAR: tecido, modelagem e cuidados]")
    kw = [nome.lower(), r["categoria_nome"].lower() if r.get("categoria_nome") else "", r["cor"].lower(), "feminino", "moda feminina", "elegante"]
    r["palavras_chave"] = ", ".join(dict.fromkeys(k for k in kw if k))
    r["hashtags"] = " ".join(dict.fromkeys(HASHTAGS_TIPO.get(t, []) + HASHTAGS_BASE))
    r["link_catalogo"] = SITE_CATALOGO
    pend = [c for c in CAMPOS_PENDENTES if not r.get(c)]
    if not r.get("preco_por"):
        pend.insert(0, "preco_por")
    r["campos_pendentes"] = ", ".join(pend)
    r["status_dados"] = "COMPLETO" if not pend else ("BASICO" if len(pend) >= 6 else "QUASE COMPLETO")
    r["alertas_cadastro"] = "; ".join(alertas_da_linha(r, t))
    return r


def alertas_da_linha(r, t):
    cat = r.get("categoria_nome") or r.get("categoria")
    a = []
    esperado = {"vestido": {"Vestidos"}, "blusa": {"Blusas", "Tricôs"}, "top": {"Blusas", "Conjuntos & Coletes"},
                "regata": {"Blusas"}, "camisa": {"Blusas"}, "calca": {"Calças"}, "saia": {"Saias"}}
    if t in esperado and cat not in esperado[t]:
        a.append(f"Categoria no site ({cat}) nao combina com o tipo ({r['tipo']})")
    if "tricoline" in sem_acento(r["nome"]).lower() and cat == "Tricôs":
        a.append("Tricoline e tecido plano, nao tricô: revisar categoria")
    if r.get("margem_critica"):
        a.append(f"Margem estimada {r['margem_estimada_pct']}% (desconto {r['desconto_pct']}%)")
    return a


def proximo_sku(rows, cat_key):
    code = CATEGORIAS[cat_key][1]
    n = max([int(r["sku"][-3:]) for r in rows if r["sku"].startswith(f"SF-{code}-")] or [0])
    return f"SF-{code}-{n + 1:03d}"


def baixar(url, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size > 0:
        return True
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(destino, "wb") as f:
        f.write(resp.read())
    return True


def pasta_categoria(cat_key):
    return IMG / slug(CATEGORIAS[cat_key][0])


def caminho_imagem(sku, nome, cat_key, ext):
    return pasta_categoria(cat_key) / f"{sku}_{slug(nome)}{ext}"


def carregar():
    if MESTRE_JSON.exists():
        return json.loads(MESTRE_JSON.read_text(encoding="utf-8"))
    return []


def salvar(rows):
    rows = sorted(rows, key=lambda r: r["sku"])
    MESTRE_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(MESTRE_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("sim" if v is True else "nao" if v is False else ("" if v is None else v)) for k, v in r.items()})
    from planilha import gerar_xlsx
    gerar_xlsx(rows, MESTRE_XLSX)
    return rows


def parse_linhas_card(lines):
    """['OPORTUNIDADE','Nome','R$ de','R$ por'] ou ['Nome','R$ por'] -> (nome, de, por, selo)"""
    selo = any(l.upper() == "OPORTUNIDADE" for l in lines)
    resto = [l for l in lines if l.upper() != "OPORTUNIDADE"]
    nome = resto[0].strip()
    precos = [parse_preco(l) for l in resto[1:] if parse_preco(l) is not None]
    if len(precos) >= 2:
        return nome, max(precos[:2]), min(precos[:2]), selo
    return nome, None, (precos[0] if precos else None), selo


def montar(sem_download=False):
    fontes = sorted(FONTE.glob("painel_*.json"))
    if not fontes:
        sys.exit("Nenhum arquivo catalogo/fonte/painel_*.json encontrado.")
    fonte = json.loads(fontes[-1].read_text(encoding="utf-8"))
    atuais = {r["id_painel"]: r for r in carregar() if r.get("id_painel")}
    manuais = {slug(r["nome"]): r for r in carregar() if not r.get("id_painel")}
    def _ts(c):
        m = re.search(r"(\d{12,13})", c["src"])
        return m.group(1) if m else "0" + Path(c["src"]).stem.zfill(12)
    ordem = sorted(fonte, key=_ts)
    rows = []
    contadores = {}
    for r in list(manuais.values()) + list(atuais.values()):
        k = CODE_TO_KEY.get(r["sku"][3:6])
        contadores[k] = max(contadores.get(k, 0), int(r["sku"][-3:]))
    for card in ordem:
        idp = Path(card["src"]).stem
        if not re.search(r"\d{12,13}", idp):
            idp = "site-" + idp
        nome, de, por, selo = parse_linhas_card(card["lines"])
        cat_key = card["categoria"]
        if idp in atuais:
            r = atuais[idp]
        elif slug(nome) in manuais:  # peca cadastrada na pasta entrada que agora apareceu no painel
            r = manuais.pop(slug(nome))
        else:
            contadores[cat_key] = contadores.get(cat_key, 0) + 1
            r = {"sku": f"SF-{CATEGORIAS[cat_key][1]}-{contadores[cat_key]:03d}"}
        ext = Path(card["src"].split("?")[0]).suffix or ".jpg"
        r.update(nome=nome, categoria=cat_key, categoria_nome=CATEGORIAS[cat_key][0], preco_de=de, preco_por=por,
                 selo_oportunidade=selo, imagem_url_origem=card["src"], id_painel=idp,
                 data_cadastro=data_do_arquivo(card["src"]))
        destino = caminho_imagem(r["sku"], nome, cat_key, ext)
        antigo = CAT / r["imagem_arquivo"] if r.get("imagem_arquivo") else None
        r["imagem_arquivo"] = str(destino.relative_to(CAT)).replace("\\", "/")
        if not sem_download:
            baixar(card["src"], destino)
            if antigo and antigo != destino and antigo.exists():
                antigo.unlink()
        completar_linha(r)
        rows.append(r)
    for r in manuais.values():  # pecas ainda so na pasta entrada (nao estao no site)
        completar_linha(r)
        rows.append(r)
    for r in rows:
        r.pop("categoria_nome", None)
        r["categoria"] = CATEGORIAS[r["categoria"]][0] if r["categoria"] in CATEGORIAS else r["categoria"]
    nomes = {}
    for r in rows:
        nomes.setdefault(slug(r["nome"]), []).append(r)
    for grupo in nomes.values():
        if len(grupo) > 1:
            for r in grupo:
                extra = "Nome duplicado no catalogo: " + ", ".join(x["sku"] for x in grupo if x is not r)
                r["alertas_cadastro"] = (r["alertas_cadastro"] + "; " if r["alertas_cadastro"] else "") + extra
    rows = salvar(rows)
    print(f"{len(rows)} produtos na base mestre -> {MESTRE_XLSX}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["montar"])
    ap.add_argument("--sem-download", action="store_true")
    a = ap.parse_args()
    montar(a.sem_download)
