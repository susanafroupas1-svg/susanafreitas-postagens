"""Cria capas dos Destaques, slides informativos e o roteiro de montagem.

O Instagram NAO permite criar Destaques por API: eles sao montados a partir de Stories ja publicados.
Este script entrega as capas, os slides prontos e o mapa de quais Stories vao em cada Destaque.

    python -I -X utf8 ferramentas/destaques.py
"""
import sys, csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageDraw
import base, midia

ROOT = base.ROOT
DEST = ROOT / "instagram" / "destaques"
CAPAS = DEST / "capas"
SLIDES = DEST / "slides"

DESTAQUES = [
    # nome (max ~10 caracteres), tipo de conteudo, descricao
    ("Novidades", "manual", "Stories das pecas que acabaram de chegar. Adicione os novos Stories de produto (arquivos em instagram/midia/stories) sempre que cadastrar peca nova."),
    ("Provador", "slides", "Como funciona o atendimento (5 slides prontos em instagram/destaques/slides/provador_*.jpg)."),
    ("Vestidos", "categoria:Vestidos", "Stories de produto da categoria Vestidos."),
    ("Blusas", "categoria:Blusas", "Stories de produto da categoria Blusas."),
    ("Calças", "categoria:Calças", "Stories de produto da categoria Calças."),
    ("Conjuntos", "categoria:Conjuntos & Coletes", "Stories de produto de Conjuntos & Coletes."),
    ("Promo", "categoria:promo", "Pecas com selo OPORTUNIDADE / preco de-por (ja existe o Destaque PROMO: so troque a capa e atualize)."),
    ("Pagamento", "slides", "Parcelamento em ate 3x sem juros (slide pronto: pagamento_*.jpg)."),
    ("Clientes", "manual", "Prova social: prints de elogios no WhatsApp e fotos de clientes, SEMPRE com autorizacao. Nao pode ser gerado automaticamente."),
]

SLIDES_INFO = [
    ("provador_1", "Como funciona.", "Atendimento próximo, humano e consultivo, em Franca/SP.", True),
    ("provador_2", "1. Escolha.", "Veja o catálogo no link da bio e separe as peças que você gostou.", False),
    ("provador_3", "2. Agende.", "Chame no WhatsApp e combine o melhor dia e horário para você.", True),
    ("provador_4", "3. Prove em casa.", "Levamos as peças até você. Prove com calma, no seu espelho, no seu tempo.", False),
    ("provador_5", "Gostou? É sua.", "Parcelamos em até 3x sem juros.", True),
    ("pagamento_1", "Parcelamos em até 3x sem juros.", "Levando mais de uma peça, conversamos sobre condições especiais.", True),
]


def capa(nome, bordo=False):
    im = Image.new("RGB", (1080, 1920), midia.BORDO if bordo else midia.ESPRESSO)
    d = ImageDraw.Draw(im)
    cx, cy, r = 540, 960, 330
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=midia.FENDI, width=4)
    d.ellipse((cx - r + 22, cy - r + 22, cx + r - 22, cy + r - 22), outline=midia.MOCHA, width=2)
    f = midia.fonte(midia.SERIF, 104)
    while d.textlength(nome, font=f) > 520 and f.size > 50:
        f = midia.fonte(midia.SERIF, f.size - 6)
    midia.centralizado(d, cy - f.size * 0.62, nome, f, midia.PEARL)
    midia.texto_espacado(d, (0, cy + 150), "SF", midia.fonte(midia.SANS_B, 40), midia.FENDI, 10, centro_em=cx)
    destino = CAPAS / f"capa_{base.slug(nome)}.png"
    CAPAS.mkdir(parents=True, exist_ok=True)
    im.save(destino)
    return destino


def main():
    rows = base.carregar()
    SLIDES.mkdir(parents=True, exist_ok=True)
    capas = [capa(n, bordo=(n == "Promo")) for n, *_ in DESTAQUES]
    for nome, titulo, corpo, esc in SLIDES_INFO:
        midia.cartao(f"../../destaques/slides/{nome}.jpg", titulo, corpo, largura=1080, altura=1920, rodape=True, esc=esc, forcar=True)
    # mapa de conteudo
    mapa = []
    for nome, tipo, desc in DESTAQUES:
        arqs = []
        if tipo.startswith("categoria:"):
            alvo = tipo.split(":", 1)[1]
            sel = [r for r in rows if r["em_promocao"]] if alvo == "promo" else [r for r in rows if r["categoria"] == alvo]
            arqs = [str(midia.arte_story(r).relative_to(ROOT)).replace("\\", "/") for r in sel]
        elif nome == "Provador":
            arqs = [f"instagram/destaques/slides/provador_{i}.jpg" for i in range(1, 6)]
        elif nome == "Pagamento":
            arqs = ["instagram/destaques/slides/pagamento_1.jpg"]
        mapa.append((nome, tipo.split(":")[0], desc, f"instagram/destaques/capas/capa_{base.slug(nome)}.png", len(arqs), " | ".join(arqs)))
    with open(DEST / "destaques_mapa.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["destaque", "origem", "o que colocar", "capa", "n_stories", "arquivos"])
        w.writerows(mapa)
    (DEST / "ROTEIRO.md").write_text(roteiro(mapa), encoding="utf-8")
    print(len(capas), "capas;", len(SLIDES_INFO), "slides;", sum(m[4] for m in mapa), "stories mapeados")


def roteiro(mapa):
    linhas = ["# Como montar os Destaques (passo a passo)", "",
              "O Instagram não deixa criar Destaques por automação. Eles nascem de Stories publicados. O caminho mais rápido:", "",
              "1. **Publique uma vez** os Stories de cada Destaque (use `Criar > Story` no celular e escolha as imagens indicadas abaixo).",
              "2. Em cada Story, toque em **Destaque** (ícone de coração) > **Novo** > escreva o nome > **Editar capa** > **Adicionar da galeria** e escolha a capa da lista.",
              "3. Para a categoria, publique de 6 a 10 stories de uma vez (não precisa ser todos). Os próximos entram pelo Arquivo de Stories.",
              "4. Mantenha o Destaque **PROMO** que já existe: só troque a capa e atualize o conteúdo.",
              "5. O Destaque *Out/Inv 2026 ✨* pode ser renomeado para *Coleção* quando a estação virar.",
              "", "## Ordem sugerida na barra", "", "Novidades, Provador, Promo, Vestidos, Blusas, Calças, Conjuntos, Pagamento, Clientes.", "",
              "## Conteúdo de cada um", ""]
    for nome, origem, desc, capa_, n, arqs in mapa:
        linhas.append(f"### {nome}")
        linhas.append(f"- {desc}")
        linhas.append(f"- Capa: `{capa_}`")
        linhas.append(f"- Stories prontos: {n}" + (" (lista completa em `destaques_mapa.csv`)" if n else " (conteúdo manual)"))
        linhas.append("")
    linhas += ["## Observações", "",
               "- As capas usam o centro da imagem (o Instagram corta em círculo). Texto fica dentro da área segura.",
               "- Os slides do *Provador* usam só o que está no site/bio: atendimento em casa, parcelamento em até 3x sem juros. Se algo mudar (ex.: política de devolução, regiões atendidas), edite o texto em `ferramentas/destaques.py` e rode de novo.",
               "- *Clientes* depende de material real: peça autorização por escrito antes de publicar prints ou fotos.", ""]
    return "\n".join(linhas)


if __name__ == "__main__":
    main()
