"""Gera artes (Feed 1080x1350, Stories 1080x1920, cartoes institucionais) no padrao da marca."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import base

ROOT = base.ROOT
MIDIA = ROOT / "instagram" / "midia"
FEED_DIR, STORY_DIR, CARD_DIR = MIDIA / "feed", MIDIA / "stories", MIDIA / "cartoes"

PEARL, ESPRESSO, MOCHA, FENDI, BORDO = (251, 248, 244), (47, 38, 34), (122, 96, 81), (217, 199, 184), (107, 45, 60)
FONTS = Path("C:/Windows/Fonts")


def fonte(nome, tam):
    for f in (nome, "georgia.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(str(FONTS / f), tam)
        except OSError:
            continue
    return ImageFont.load_default()


SERIF, SERIF_B, SERIF_I = "georgia.ttf", "georgiab.ttf", "georgiai.ttf"
SANS, SANS_B = "calibri.ttf", "calibrib.ttf"


def texto_espacado(d, xy, txt, f, fill, espaco=6, centro_em=None):
    larguras = [d.textlength(c, font=f) for c in txt]
    total = sum(larguras) + espaco * (len(txt) - 1)
    x, y = xy
    if centro_em:
        x = centro_em - total / 2
    for c, w in zip(txt, larguras):
        d.text((x, y), c, font=f, fill=fill)
        x += w + espaco
    return total


def centralizado(d, y, txt, f, fill, largura=1080):
    w = d.textlength(txt, font=f)
    d.text(((largura - w) / 2, y), txt, font=f, fill=fill)
    return w


def quebrar(d, txt, f, largura_max):
    palavras, linhas, atual = txt.split(), [], ""
    for p in palavras:
        t = (atual + " " + p).strip()
        if d.textlength(t, font=f) <= largura_max:
            atual = t
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def abrir(row):
    return Image.open(base.CAT / row["imagem_arquivo"]).convert("RGB")


def cobrir(im, w, h, ancora_y=0.3):
    """Redimensiona para cobrir w x h (corte). ancora_y: 0=topo, 1=base."""
    r = max(w / im.width, h / im.height)
    im2 = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x = (im2.width - w) // 2
    y = round((im2.height - h) * ancora_y)
    return im2.crop((x, y, x + w, y + h))


def fundo_desfocado(im, w, h):
    bg = cobrir(im, w, h).filter(ImageFilter.GaussianBlur(38))
    return Image.blend(bg, Image.new("RGB", (w, h), ESPRESSO), 0.38)


def arte_feed(row, forcar=False):
    destino = FEED_DIR / f"{row['sku']}.jpg"
    if destino.exists() and not forcar:
        return destino
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    im = abrir(row)
    ratio = im.width / im.height
    if 0.78 <= ratio <= 0.82:
        out = im.resize((1080, 1350), Image.LANCZOS)
    elif ratio >= 0.70:
        out = cobrir(im, 1080, 1350, ancora_y=0.2)
    else:
        bg = fundo_desfocado(im, 1080, 1350)
        h = 1350
        w = round(im.width * h / im.height)
        out = bg
        out.paste(im.resize((w, h), Image.LANCZOS), ((1080 - w) // 2, 0))
    out.save(destino, quality=92, subsampling=0)
    return destino


def arte_story(row, rotulo=None, forcar=False):
    """Story de produto: foto + nome + preco + chamada para o WhatsApp."""
    destino = STORY_DIR / f"{row['sku']}{'_' + rotulo if rotulo else ''}.jpg"
    if destino.exists() and not forcar:
        return destino
    STORY_DIR.mkdir(parents=True, exist_ok=True)
    im = abrir(row)
    ratio = im.width / im.height
    if ratio < 0.6:  # 9:16 -> tela cheia + degrade
        tela = cobrir(im, 1080, 1920, ancora_y=0.15)
        grad = Image.new("L", (1080, 1920), 0)
        gd = ImageDraw.Draw(grad)
        for y in range(1250, 1920):
            gd.line([(0, y), (1080, y)], fill=int(205 * (y - 1250) / 670))
        tela = Image.composite(Image.new("RGB", (1080, 1920), ESPRESSO), tela, grad)
        foto_box = None
    else:
        tela = fundo_desfocado(im, 1080, 1920)
        w = 960
        h = round(im.height * w / im.width)
        foto = im.resize((w, h), Image.LANCZOS)
        foto_box = (60, 300, 60 + w, 300 + h)
        sombra = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rectangle((40, 40, w + 40, h + 40), fill=(0, 0, 0, 120))
        sombra = sombra.filter(ImageFilter.GaussianBlur(22))
        tela.paste(sombra, (20, 260), sombra)
        tela.paste(foto, foto_box[:2])
    d = ImageDraw.Draw(tela)
    texto_espacado(d, (0, 215), "SUSANA FREITAS STORE", fonte(SANS_B, 28), PEARL, 7, centro_em=540)
    por, de = row.get("preco_por"), row.get("preco_de")
    if row.get("selo_oportunidade"):
        bx = (foto_box[2] - 270, foto_box[1] + 20) if foto_box else (770, 330)
        d.rectangle((bx[0], bx[1], bx[0] + 250, bx[1] + 50), fill=BORDO)
        texto_espacado(d, (0, bx[1] + 11), "OPORTUNIDADE", fonte(SANS_B, 26), PEARL, 4, centro_em=bx[0] + 125)
    y0 = (foto_box[3] + 38) if foto_box else 1500
    y0 = min(y0, 1560)
    nome = row["nome"]
    f_nome = fonte(SERIF, 52)
    while d.textlength(nome, font=f_nome) > 960 and f_nome.size > 34:
        f_nome = fonte(SERIF, f_nome.size - 2)
    centralizado(d, y0, nome, f_nome, PEARL)
    if por:
        yp = y0 + 76
        f_p = fonte(SERIF_B, 56)
        if de and row.get("em_promocao"):
            f_de = fonte(SANS, 36)
            t_de, t_por = f"de {base.brl(de)}", f"por {base.brl(por)}"
            w1, w2 = d.textlength(t_de, font=f_de), d.textlength(t_por, font=f_p)
            x = (1080 - (w1 + 34 + w2)) / 2
            d.text((x, yp + 14), t_de, font=f_de, fill=FENDI)
            d.line([(x, yp + 38), (x + w1, yp + 38)], fill=FENDI, width=3)
            d.text((x + w1 + 34, yp), t_por, font=f_p, fill=PEARL)
        else:
            centralizado(d, yp, base.brl(por), f_p, PEARL)
    centralizado(d, min(y0 + 168, 1740), "Agende sua visita pelo WhatsApp", fonte(SANS, 34), FENDI)
    tela.save(destino, quality=92, subsampling=0)
    return destino


def cartao(nome_arquivo, titulo, corpo, largura=1080, altura=1350, rodape=True, forcar=False, esc=False, topo_extra=0):
    """Cartao de texto institucional (feed 4:5 ou story 9:16)."""
    destino = CARD_DIR / nome_arquivo
    if destino.exists() and not forcar:
        return destino
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    bg, fg, ac = (ESPRESSO, PEARL, FENDI) if esc else (PEARL, ESPRESSO, MOCHA)
    im = Image.new("RGB", (largura, altura), bg)
    d = ImageDraw.Draw(im)
    safe_top = 250 if altura == 1920 else 120
    safe_bot = 380 if altura == 1920 else 200
    texto_espacado(d, (0, safe_top), "SUSANA FREITAS STORE", fonte(SANS_B, 30), ac, 8, centro_em=largura / 2)
    d.line([(largura / 2 - 60, safe_top + 58), (largura / 2 + 60, safe_top + 58)], fill=ac, width=3)
    f_t = fonte(SERIF, 86)
    linhas = quebrar(d, titulo, f_t, largura - 200)
    f_c = fonte(SANS, 44)
    linhas_c = quebrar(d, corpo, f_c, largura - 240)
    bloco = len(linhas) * 108 + 50 + len(linhas_c) * 62
    y = (safe_top + 90 + (altura - safe_bot)) / 2 - bloco / 2 + 20
    for l in linhas:
        centralizado(d, y, l, f_t, fg, largura)
        y += 108
    y += 50
    for l in linhas_c:
        centralizado(d, y, l, f_c, ac if not esc else FENDI, largura)
        y += 62
    if rodape:
        centralizado(d, altura - safe_bot + 30, f"WhatsApp {base.WHATS_DISPLAY}", fonte(SANS_B, 38), fg, largura)
        centralizado(d, altura - safe_bot + 86, "Link na bio", fonte(SANS, 32), ac, largura)
    im.save(destino, quality=92, subsampling=0)
    return destino


if __name__ == "__main__":
    rows = base.carregar()
    r = next(x for x in rows if x["em_promocao"])
    print(arte_feed(r, True), arte_story(r, forcar=True))
    r2 = next(x for x in rows if x["adequada_story"])
    print(arte_story(r2, forcar=True))
    print(cartao("teste_feed.jpg", "Experimente em casa.", "Levamos a curadoria até você. Prove com calma, no seu tempo.", forcar=True))
