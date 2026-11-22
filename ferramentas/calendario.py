"""Gera o calendario de postagens (30 dias), as artes e a fila de publicacao.

    python -I ferramentas/calendario.py --inicio 2026-11-23 --dias 30

Regras (editaveis no topo do arquivo):
  - Feed 1x/dia, Reels 3x/semana (Ter/Qui/Sab), Stories 3x/dia.
  - Prioriza pecas de maior lucro unitario e sem margem critica; rotaciona categorias;
    cobre o catalogo todo em Stories; Sabado = oportunidade; Domingo = institucional.
  - Se rodar de novo com --inicio posterior, preserva o que ja foi publicado e evita repetir pecas.
"""
import sys, json, csv, argparse, datetime as dt
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
import base, midia

ROOT = base.ROOT
IG = ROOT / "instagram"
FILA = IG / "fila_postagens.json"
REELS_DIR = IG / "midia" / "reels"
UTC_OFFSET_H = 3  # Brasilia = UTC-3 (sem horario de verao desde 2019)

HORA_FEED, HORA_FEED_DOM, HORA_REEL = "20:00", "10:30", "13:00"
HORAS_STORY = ["08:30", "15:00", "20:45"]
DIAS_REEL = {3, 4, 5}  # quinta, sexta, sabado (maior alcance nos Insights)
ROTACAO_CARROSSEL = ["Vestidos", "Blusas", "Calças", "Conjuntos & Coletes", "Saias", "Tricôs"]
DATAS_ESPECIAIS = {
    dt.date(2026, 11, 27): "black_friday",
}
FRASES = {
    "vestido": ["Um vestido para chegar bem em qualquer ocasião.", "Feminilidade com presença, sem esforço.",
                "Peça-chave para quem gosta de estar elegante com leveza."],
    "blusa": ["A peça que muda o look inteiro.", "Para combinar com o que você já tem no guarda-roupa.",
              "Simples de usar, difícil de esquecer."],
    "calca": ["Para a rotina que não para, sem perder a elegância.", "Uma base de look que rende combinações."],
    "saia": ["Leveza e elegância para compor o look.", "Uma saia para montar produções diferentes."],
    "conjunto": ["Look pronto, sem precisar pensar muito.", "Dois em um: elegância prática."],
    "colete": ["O toque final que transforma a produção.", "Para dar estrutura ao look."],
    "trico": ["Conforto e charme para as noites mais frescas.", "Tricô com elegância."],
}
FRASE_PADRAO = ["Elegância com curadoria.", "Uma escolha pensada para você."]
CTA = [
    "Quer ver de perto? Atendemos em Franca/SP e levamos até você para experimentar com calma. Chame no WhatsApp {tel} ou veja o catálogo completo em susanafreitasstore.com.br (link na bio). 🤍",
    "Prove no conforto da sua casa, em Franca/SP. Agende pelo WhatsApp {tel}. Catálogo completo: susanafreitasstore.com.br (link na bio). ✨",
    "Gostou? Chame no WhatsApp {tel} e a gente leva a peça até você. Mais opções em susanafreitasstore.com.br (link na bio). 🤍",
]
INSTITUCIONAIS = [
    ("exp_casa", "Experimente em casa.", "Em Franca/SP, levamos a curadoria até você. Prove com calma, no seu espelho, no seu tempo.",
     "Experimentar em casa muda tudo: você vê a peça no seu espelho, com a sua luz e o seu tempo. É assim que atendemos em Franca/SP. 🤍\n\nAgende sua visita pelo WhatsApp {tel} ou veja o catálogo em susanafreitasstore.com.br (link na bio)."),
    ("mais_que_moda", "Mais do que moda.", "Uma curadoria premium para mulheres maduras e seguras.",
     "Mais do que moda: uma curadoria pensada para mulheres maduras e seguras, com peças que realçam a sua melhor versão de forma autêntica e sofisticada. ✨\n\nConheça o catálogo completo em susanafreitasstore.com.br (link na bio)."),
    ("parcelamento", "Parcelamos em até 3x sem juros.", "Levando mais de uma peça, conversamos sobre condições especiais.",
     "Parcelamos em até 3x sem juros. 💳\n\nEscolha sua peça no catálogo (susanafreitasstore.com.br, link na bio) e chame no WhatsApp {tel} para agendar sua visita."),
    ("atendimento", "Atendimento próximo, humano e consultivo.", "Ajudamos você a escolher peças que realçam a sua melhor versão.",
     "Aqui o atendimento é próximo, humano e consultivo. Ajudamos você a escolher peças que realçam a sua melhor versão, sem pressa. 🤍\n\nChame no WhatsApp {tel} ou veja o catálogo em susanafreitasstore.com.br (link na bio)."),
]


def lucro_unit(r):
    return (r["preco_por"] or 0) - (r["custo_estimado"] or 0)


def slug_chave(r):
    return base.sem_acento(r["tipo"]).lower()


def linha_preco(r):
    if r["em_promocao"]:
        return f"De {base.brl(r['preco_de'])} por {base.brl(r['preco_por'])}. Condição especial enquanto durar o estoque."
    return f"{base.brl(r['preco_por'])}" + (" ou em até 3x sem juros." if r["preco_por"] else "")


def hashtags(r, extra=()):
    tags = r["hashtags"].split() + list(extra)
    return " ".join(list(dict.fromkeys(tags))[:8])


def legenda_single(r, i):
    chave = slug_chave(r)
    frases = FRASES.get(chave, FRASE_PADRAO)
    hook = [f"{r['nome']} ✨", f"Novidade no nosso catálogo: {r['nome']} 🤍", f"{r['nome']}, uma escolha da nossa curadoria ✨"][i % 3]
    return (f"{hook}\n\n{linha_preco(r)}\n\n{frases[i % len(frases)]}\n\n{CTA[i % len(CTA)].format(tel=base.WHATS_DISPLAY)}\n\n"
            f"{hashtags(r, ['#lookdodia'])}")


def legenda_carrossel(titulo, itens, i):
    linhas = "\n".join(f"• {r['nome']}: {base.brl(r['preco_por'])}" for r in itens)
    return (f"{titulo} 🤍\n\nDeslize e escolha a sua favorita:\n{linhas}\n\n"
            f"{CTA[i % len(CTA)].format(tel=base.WHATS_DISPLAY)}\n\n"
            f"#modafeminina #modaelegante #boutiquefeminina #modadelivery #lookdodia #francasp")


def reel_roteiro(r):
    return (f"Reel (15–25s) da peça {r['nome']}: 1) abertura com a peça inteira em movimento; 2) detalhe de tecido/acabamento; "
            f"3) combinação (calçado/acessório); 4) fecho: 'Agende sua visita, link na bio'. Música instrumental em alta; texto na tela: nome + preço.")


def legenda_reel(r, i):
    return (f"{r['nome']} em movimento ✨\n\n{linha_preco(r)}\n\n{CTA[i % len(CTA)].format(tel=base.WHATS_DISPLAY)}\n\n"
            f"{hashtags(r, ['#reels'])}")


def achar_videos():
    """Procura MP4 existentes em POSTAGENS/**/VIDEOS cujo nome comece com o nome de uma peca."""
    achados = {}
    pasta = ROOT / "POSTAGENS"
    if not pasta.exists():
        return achados
    mp4 = [p for p in pasta.rglob("*.mp4")]
    rows = base.carregar()
    for r in rows:
        s = base.slug(r["nome"])
        for p in mp4:
            if base.slug(p.stem).startswith(s):
                achados.setdefault(r["sku"], p)
    return achados


def carregar_fila():
    return json.loads(FILA.read_text(encoding="utf-8")) if FILA.exists() else []


def utc_str(data, hora):
    h, m = map(int, hora.split(":"))
    local = dt.datetime.combine(data, dt.time(h, m))
    return (local + dt.timedelta(hours=UTC_OFFSET_H)).strftime("%Y-%m-%dT%H:%M:%SZ")


def gerar(inicio, dias):
    rows = base.carregar()
    por_sku = {r["sku"]: r for r in rows}
    fila_antiga = carregar_fila()
    fim = inicio + dt.timedelta(days=dias)
    mantidos = [it for it in fila_antiga if not (str(inicio) <= it["data"] < str(fim))]
    uso_feed, uso_story = Counter(), Counter()
    for it in mantidos:
        for s in it.get("skus", []):
            (uso_feed if it["tipo"] in ("feed", "carrossel", "reel") else uso_story)[s] += 1
    videos = achar_videos()

    # ordens de prioridade
    elegiveis_feed = [r for r in rows if not r["margem_critica"] and r["adequada_feed"] and r["preco_por"]]
    elegiveis_feed.sort(key=lambda r: -lucro_unit(r))
    promos_boas = sorted([r for r in rows if r["em_promocao"] and not r["margem_critica"] and r["preco_por"]],
                         key=lambda r: -r["margem_estimada_pct"])
    usados_feed = set(s for s, c in uso_feed.items() if c)
    novos = []

    def pegar_feed(filtro=lambda r: True, n=1, relax=False, pad=False):
        """Pega n pecas ainda nao usadas no Feed. relax: completa com qualquer categoria. pad: recicla se faltar."""
        livres = [r for r in elegiveis_feed if r["sku"] not in usados_feed]
        sel = [r for r in livres if filtro(r)][:n]
        if len(sel) < n and relax:
            sel += [r for r in livres if r not in sel][:n - len(sel)]
        if len(sel) < n and (pad or not sel):
            extras = sorted([r for r in elegiveis_feed if r not in sel], key=lambda r: uso_feed[r["sku"]])
            sel += extras[:n - len(sel)]
        for r in sel:
            usados_feed.add(r["sku"])
            uso_feed[r["sku"]] += 1
        return sel

    def item(data, hora, tipo, skus, arquivos, legenda, status="pronto", obs="", titulo=""):
        novos.append(dict(id=f"{data}_{hora.replace(':', '')}_{tipo}_{len(novos):03d}", data=str(data), hora_local=hora,
                          publicar_em_utc=utc_str(data, hora), plataforma="instagram", tipo=tipo, skus=skus,
                          titulo=titulo, arquivos=arquivos, legenda=legenda, status=status, observacao=obs))

    cat_idx = Counter()
    bf_skus = {r["sku"] for r in promos_boas[:5]}
    sabados = sorted([r for r in rows if r["em_promocao"] and (r["margem_estimada_pct"] or 0) >= 15 and r["sku"] not in bf_skus],
                     key=lambda r: -r["margem_estimada_pct"])
    carr_n = 0
    reel_n = 0
    inst_n = 0
    single_n = 0
    story_pool = sorted(rows, key=lambda r: (uso_story[r["sku"]], -lucro_unit(r)))
    pendente_stories = []
    for d in range(dias):
        data = inicio + dt.timedelta(days=d)
        wd = data.weekday()
        especial = DATAS_ESPECIAIS.get(data)
        feed_skus = []
        # ---------- FEED ----------
        if especial == "black_friday":
            sel = (promos_boas[:5])
            for r in sel:
                uso_feed[r["sku"]] += 1
                usados_feed.add(r["sku"])
            arqs = [str(midia.arte_feed(r).relative_to(ROOT)).replace("\\", "/") for r in sel]
            arqs.append(str(midia.cartao("cta_carrossel.jpg", "Gostou de alguma peça?", "Agende sua visita: levamos até você para experimentar.", rodape=True, esc=True).relative_to(ROOT)).replace("\\", "/"))
            leg = ("Black Friday Susana Freitas Store 🖤\n\nOportunidades selecionadas, com condição especial enquanto durar o estoque:\n"
                   + "\n".join(f"• {r['nome']}: de {base.brl(r['preco_de'])} por {base.brl(r['preco_por'])}" for r in sel)
                   + f"\n\nChame no WhatsApp {base.WHATS_DISPLAY} e agende sua visita. Catálogo completo: susanafreitasstore.com.br (link na bio).\n\n#blackfriday #modafeminina #modaelegante #boutiquefeminina #modadelivery #oportunidade")
            item(data, HORA_FEED, "carrossel", [r["sku"] for r in sel], arqs, leg, titulo="Black Friday: oportunidades",
                 obs="Usa so itens ja em OPORTUNIDADE, escolhidos entre os de melhor retorno. Nao criar desconto novo sem recalcular a margem.")
            feed_skus = [r["sku"] for r in sel]
        elif wd == 6:  # domingo institucional
            cod, tit, corpo, leg = INSTITUCIONAIS[inst_n % len(INSTITUCIONAIS)]
            arq = midia.cartao(f"feed_{cod}.jpg", tit, corpo)
            item(data, HORA_FEED_DOM, "feed", [], [str(arq.relative_to(ROOT)).replace("\\", "/")],
                 leg.format(tel=base.WHATS_DISPLAY) + "\n\n#modafeminina #modaelegante #boutiquefeminina #modadelivery",
                 titulo=f"Institucional: {tit}")
            inst_n += 1
        elif wd == 5:  # sabado: oportunidade
            r = next((x for x in sabados if x["sku"] not in usados_feed), None) or (min(sabados, key=lambda x: uso_feed[x["sku"]]) if sabados else None)
            if r:
                usados_feed.add(r["sku"]); uso_feed[r["sku"]] += 1
                item(data, HORA_FEED, "feed", [r["sku"]], [str(midia.arte_feed(r).relative_to(ROOT)).replace("\\", "/")],
                     legenda_single(r, single_n), titulo=f"Oportunidade: {r['nome']}")
                single_n += 1; feed_skus = [r["sku"]]
        elif wd in (1, 3):  # terca/quinta: carrossel por categoria
            cat = ROTACAO_CARROSSEL[carr_n % len(ROTACAO_CARROSSEL)]
            sel = pegar_feed(lambda r: r["categoria"] == cat, 5)
            if len(sel) < 3:
                sel += pegar_feed(lambda r: True, 5 - len(sel), relax=True)
                cat = "Seleção da semana"
            arqs = [str(midia.arte_feed(r).relative_to(ROOT)).replace("\\", "/") for r in sel]
            arqs.append(str(midia.cartao("cta_carrossel.jpg", "Gostou de alguma peça?", "Agende sua visita: levamos até você para experimentar.", rodape=True, esc=True).relative_to(ROOT)).replace("\\", "/"))
            titulo = f"Seleção: {cat}" if cat != "Seleção da semana" else cat
            item(data, HORA_FEED, "carrossel", [r["sku"] for r in sel], arqs, legenda_carrossel(titulo, sel, carr_n), titulo=titulo)
            feed_skus = [r["sku"] for r in sel]; carr_n += 1
        else:  # segunda, quarta, sexta: peca em destaque
            r = pegar_feed(lambda x: x["categoria"] == ["Vestidos", "Conjuntos & Coletes", "Blusas"][single_n % 3], 1, relax=True)[0]
            item(data, HORA_FEED, "feed", [r["sku"]], [str(midia.arte_feed(r).relative_to(ROOT)).replace("\\", "/")],
                 legenda_single(r, single_n), titulo=f"Destaque: {r['nome']}")
            single_n += 1; feed_skus = [r["sku"]]
        # ---------- REELS (producao manual) ----------
        if wd in DIAS_REEL:
            com_video = [r for r in rows if r["sku"] in videos and uso_feed[r["sku"] + "_reel"] == 0]
            if com_video:
                r = com_video[0]; uso_feed[r["sku"] + "_reel"] += 1
                destino = REELS_DIR / f"{r['sku']}.mp4"
                obs = f"Video ja existente em POSTAGENS ({videos[r['sku']].name}). Copie para {destino.relative_to(ROOT)} e confirme formato 9:16 / MP4 e direito de uso (video de fornecedor)."
                status = "aguardando_midia"
            else:
                cand = [x for x in elegiveis_feed if uso_feed[x["sku"] + "_reel"] == 0 and x["sku"] not in feed_skus]
                r = cand[0] if cand else elegiveis_feed[reel_n % len(elegiveis_feed)]
                uso_feed[r["sku"] + "_reel"] += 1
                destino = REELS_DIR / f"{r['sku']}.mp4"
                obs = "Gravar/editar o video e salvar em " + str(destino.relative_to(ROOT)) + ". Roteiro: " + reel_roteiro(r)
                status = "aguardando_midia"
            item(data, HORA_REEL, "reel", [r["sku"]], [str(destino.relative_to(ROOT)).replace("\\", "/")],
                 legenda_reel(r, reel_n), status=status, obs=obs, titulo=f"Reel: {r['nome']}")
            reel_n += 1
        pendente_stories.append((data, wd, feed_skus))
    # ---------- STORIES (segunda passada: prioriza o que ainda nao apareceu) ----------
    for data, wd, feed_skus in pendente_stories:
        usados_hoje = set(feed_skus)
        stories_hoje = []
        story_pool.sort(key=lambda r: (uso_story[r["sku"]] + (1 if uso_feed[r["sku"]] else 0), -lucro_unit(r)))
        for r in story_pool:
            if len(stories_hoje) == 2:
                break
            if r["sku"] in usados_hoje or not r["preco_por"]:
                continue
            stories_hoje.append(r)
            uso_story[r["sku"]] += 1
            usados_hoje.add(r["sku"])
        story_pool.sort(key=lambda r: (uso_story[r["sku"]] + (1 if uso_feed[r["sku"]] else 0), -lucro_unit(r)))
        for hora, r in zip(HORAS_STORY[:2], stories_hoje):
            item(data, hora, "story", [r["sku"]], [str(midia.arte_story(r).relative_to(ROOT)).replace("\\", "/")], "",
                 titulo=f"Story: {r['nome']}")
        if wd == 6 or not feed_skus:
            arq = midia.cartao("story_agende.jpg", "Agende sua visita.", f"Levamos a curadoria até você. WhatsApp {base.WHATS_DISPLAY}.", largura=1080, altura=1920, rodape=True, esc=True)
            item(data, HORAS_STORY[2], "story", [], [str(arq.relative_to(ROOT)).replace("\\", "/")], "", titulo="Story: agende sua visita")
        else:
            r = por_sku[feed_skus[0]]
            item(data, HORAS_STORY[2], "story", [r["sku"]], [str(midia.arte_story(r).relative_to(ROOT)).replace("\\", "/")], "",
                 titulo=f"Story (chamada para o feed): {r['nome']}", obs="Antes de publicar manualmente: adicionar figurinha de link/enquete (a API nao cria figurinhas).")
    fila = sorted(mantidos + novos, key=lambda it: (it["data"], it["hora_local"], it["tipo"]))
    # a fila publica (vai ao GitHub) nao leva observacoes internas; elas ficam so nas planilhas
    publica = [{k: v for k, v in it.items() if k != "observacao"} for it in fila]
    FILA.write_text(json.dumps(publica, ensure_ascii=False, indent=1), encoding="utf-8")
    exportar(fila, por_sku)
    return fila, novos


NOMES_DIA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def exportar(fila, por_sku):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    cols = ["data", "dia", "hora_local", "tipo", "titulo", "skus", "arquivos", "legenda", "status", "observacao"]
    with open(IG / "calendario_30_dias.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for it in fila:
            dia = NOMES_DIA[dt.date.fromisoformat(it["data"]).weekday()]
            w.writerow([it["data"], dia, it["hora_local"], it["tipo"], it["titulo"], ",".join(it["skus"]),
                        " | ".join(it["arquivos"]), it["legenda"], it["status"], it["observacao"]])
    wb = Workbook()
    ws = wb.active
    ws.title = "Calendario"
    ws.append(["Data", "Dia", "Hora (Brasilia)", "Formato", "Conteudo", "SKUs", "Arquivos", "Legenda", "Status", "Observacao"])
    cor = {"feed": "FFFFFF", "carrossel": "F3ECE4", "reel": "E6D8CC", "story": "FBF8F4"}
    for it in fila:
        dia = NOMES_DIA[dt.date.fromisoformat(it["data"]).weekday()]
        ws.append([dt.date.fromisoformat(it["data"]), dia, it["hora_local"], it["tipo"].capitalize(), it["titulo"],
                   ", ".join(it["skus"]), "\n".join(it["arquivos"]), it["legenda"], it["status"], it["observacao"]])
        for c in ws[ws.max_row]:
            c.fill = PatternFill("solid", fgColor=cor.get(it["tipo"], "FFFFFF"))
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(ws.max_row, 1).number_format = "dd/mm/yyyy"
    for c in ws[1]:
        c.font = Font(bold=True, color="FBF8F4")
        c.fill = PatternFill("solid", fgColor="2F2622")
    for col, w_ in zip("ABCDEFGHIJ", [12, 10, 10, 11, 34, 22, 46, 70, 17, 60]):
        ws.column_dimensions[col].width = w_
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    resumo = wb.create_sheet("Resumo")
    cont = Counter(it["tipo"] for it in fila)
    resumo.append(["Formato", "Quantidade"])
    for k, v in cont.items():
        resumo.append([k, v])
    resumo.append(["TOTAL", sum(cont.values())])
    resumo.append([])
    skus_unicos = {s for it in fila for s in it["skus"]}
    resumo.append(["Pecas distintas divulgadas", len(skus_unicos)])
    resumo.append(["Pecas do catalogo", len(por_sku)])
    resumo.append(["Pecas ainda nao divulgadas", len(set(por_sku) - skus_unicos)])
    hip = wb.create_sheet("Horarios (hipoteses)")
    for linha in [
        ["Slot", "Horario (Brasilia)", "Racional (hipotese a testar com os Insights do Instagram)"],
        ["Feed (seg-sab)", HORA_FEED, "Insights (mid. recentes): 20h teve o melhor engajamento da noite; cliente em casa apos a rotina."],
        ["Feed (domingo)", HORA_FEED_DOM, "Domingo de manha: consumo mais calmo; conteudo institucional."],
        ["Reels (qui/sex/sab)", HORA_REEL, "Insights: 13h foi a melhor faixa de engajamento; qui/sex/sab tem alcance 2-3x maior (media 150-270 vs ~80 contas/dia)."],
        ["Story 1", HORAS_STORY[0], "Primeira olhada do dia."],
        ["Story 2", HORAS_STORY[1], "Tarde (15h): segunda melhor faixa de engajamento; nao colide com o Reel das 13h."],
        ["Story 3", HORAS_STORY[2], "Chamada para o feed do dia + WhatsApp no horario de maior conversa."],
        ["Como calibrar", "", "Depois de 14 dias, abrir Insights > Audiencia > Horarios mais ativos e mover os posts para os picos reais dos seus 1.754 seguidores."],
    ]:
        hip.append(linha)
    hip.column_dimensions["A"].width = 22; hip.column_dimensions["B"].width = 18; hip.column_dimensions["C"].width = 110
    wb.save(IG / "calendario_30_dias.xlsx")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2026-11-23")
    ap.add_argument("--dias", type=int, default=30)
    a = ap.parse_args()
    fila, novos = gerar(dt.date.fromisoformat(a.inicio), a.dias)
    print(Counter(i["tipo"] for i in novos), "total", len(novos))
    print("pecas distintas:", len({s for i in novos for s in i["skus"]}), "de", len(base.carregar()))
