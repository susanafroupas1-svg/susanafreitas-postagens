"""Registra pecas novas colocadas em catalogo/entrada/ na base mestre.

Como usar (veja catalogo/entrada/LEIA-ME.txt):
    1. Salve a foto em catalogo/entrada/ (ou em catalogo/entrada/vestidos|blusas|calcas|saias|conjuntos|tricos).
    2. Nome do arquivo no seu padrao atual:
         Vestido Lara 339,90.jpg                    -> preco de venda
         Vestido Lara DE 557,00 POR 339,90.jpg      -> promocao
         Vestido Verde (sem valor por enquanto).jpg -> sem preco ainda
    3. python -I -X utf8 ferramentas/registrar_novas.py
"""
import sys, re, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import base
from base import CATEGORIAS, TIPO_PARA_CATEGORIA

EXT = {".jpg", ".jpeg", ".png"}
PASTAS = {base.slug(v[0]): k for k, v in CATEGORIAS.items()}
PASTAS.update({"calcas": "CALÇAS", "conjuntos": "CONJUNTOS & COLETES", "tricos": "TRICÔS", "conjuntos-coletes": "CONJUNTOS & COLETES"})


def parse_nome(stem):
    s = re.sub(r"\(.*?\)", "", stem).strip()
    s = re.sub(r"\s*-\s*(FEED|STORIES)\b.*$", "", s, flags=re.I).strip()
    de = por = None
    m = re.search(r"\bDE\s+([\d.]*\d,\d{2})\s+POR\s+([\d.]*\d,\d{2})$", s, re.I)
    if m:
        de, por = base.parse_preco(m.group(1)), base.parse_preco(m.group(2))
        s = s[:m.start()].strip()
    else:
        m = re.search(r"\s([\d.]*\d,\d{2})$", s)
        if m:
            por = base.parse_preco(m.group(1))
            s = s[:m.start()].strip()
    return s, de, por


def main():
    arquivos = [p for p in base.ENTRADA.rglob("*") if p.is_file() and p.suffix.lower() in EXT]
    if not arquivos:
        print("Nada novo em catalogo/entrada/.")
        return
    rows = base.carregar()
    existentes = {base.slug(r["nome"]) for r in rows}
    novos = 0
    for p in sorted(arquivos):
        nome, de, por = parse_nome(p.stem)
        if not nome:
            print(f"IGNORADO (sem nome): {p.name}")
            continue
        if base.slug(nome) in existentes:
            print(f"IGNORADO (ja cadastrada): {nome}  -> renomeie o arquivo ou apague-o")
            continue
        cat_key = PASTAS.get(base.slug(p.parent.name)) if p.parent != base.ENTRADA else None
        cat_key = cat_key or TIPO_PARA_CATEGORIA.get(base.tipo_do_nome(nome))
        if not cat_key:
            print(f"IGNORADO (categoria desconhecida): {p.name} -> coloque em uma subpasta (vestidos, blusas, calcas, saias, conjuntos, tricos)")
            continue
        sku = base.proximo_sku(rows, cat_key)
        destino = base.caminho_imagem(sku, nome, cat_key, p.suffix.lower())
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(destino))
        r = dict(sku=sku, nome=nome, categoria=CATEGORIAS[cat_key][0], categoria_nome=CATEGORIAS[cat_key][0],
                 preco_de=de, preco_por=por, selo_oportunidade=False, imagem_url_origem="", id_painel="",
                 imagem_arquivo=str(destino.relative_to(base.CAT)).replace("\\", "/"))
        import datetime
        r["data_cadastro"] = datetime.date.today().isoformat()
        base.completar_linha(r)
        r.pop("categoria_nome", None)
        rows.append(r)
        existentes.add(base.slug(nome))
        novos += 1
        print(f"OK {sku}  {nome}  {base.brl(por) if por else '(sem preco)'}")
    if novos:
        base.salvar(rows)
        print(f"\n{novos} peca(s) registradas. Proximos passos:\n"
              "  1) Cadastre a peca no painel do site (foto, nome, categoria, preco).\n"
              "  2) Abra catalogo/produtos_mestre.xlsx e preencha tamanhos, estoque, tecido, custo (celulas amarelas).\n"
              "  3) Para entrar no calendario: python -I -X utf8 ferramentas/calendario.py --inicio AAAA-MM-DD --dias 30")


if __name__ == "__main__":
    main()
