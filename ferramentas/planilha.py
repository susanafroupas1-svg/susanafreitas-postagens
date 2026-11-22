"""Gera a planilha Excel da base mestre (formulas de custo/margem ligadas a uma premissa editavel)."""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import base

ESPRESSO, PEARL, AMARELO, VERMELHO = "2F2622", "FBF8F4", "FFF4CC", "F8D7DA"

DICIONARIO = [
    ("sku", "Codigo unico da peca (SF-CATEGORIA-NNN). Nunca muda, mesmo se o nome mudar. E o SKU nos marketplaces.", "Todos"),
    ("nome / titulo_marketplace", "Titulo do anuncio. Regra pratica: tipo + modelo + cor + 'Feminino'.", "Todos"),
    ("preco_de / preco_por", "Preco cheio e preco de venda. Em promocao: de > por.", "Todos"),
    ("custo_real", "Preencha o custo pago por peca. Substitui a estimativa (preco cheio / premissa de markup).", "Interno"),
    ("margem_critica", "sim quando a margem estimada na venda esta abaixo de 25%. Nao anuncie em marketplace sem rever o preco.", "Interno"),
    ("tamanhos_disponiveis / estoque_total", "Marketplaces exigem variacao por tamanho (e cor) com estoque por variacao. Sem isso nao ha anuncio.", "Todos"),
    ("composicao_tecido / modelagem_caimento / medidas_cm", "Atributos obrigatorios ou muito pesados no ranking; tabela de medidas reduz devolucao.", "Todos"),
    ("marca_origem / fornecedor", "Marcas de terceiros podem exigir autorizacao do fabricante em alguns marketplaces. Registre a origem de cada peca.", "Amazon, Mercado Livre, Shopee"),
    ("gtin_ean", "Codigo de barras. Quando a peca nao tem, a maioria dos marketplaces aceita declarar isencao; confirme a regra atual de cada um.", "Mercado Livre, Amazon"),
    ("ncm", "Classificacao fiscal da peca, necessaria para emitir nota fiscal quando o canal ou o regime exigir.", "Fiscal"),
    ("peso_embalagem_g / dim_embalagem_cm", "Peso e dimensoes da embalagem calculam o frete.", "Todos"),
    ("imagem_arquivo", "Foto principal. Marketplaces costumam exigir fundo branco/neutro e foto sem marca d'agua na capa; as fotos atuais tem fundo de estudio e a marca SF.", "Amazon, Mercado Livre"),
    ("adequada_feed / adequada_story", "Proporcao 4:5 (feed) ou 9:16 (stories) em boa resolucao.", "Instagram"),
]


def gerar_xlsx(rows, destino):
    wb = Workbook()
    ws = wb.active
    ws.title = "Produtos"
    cols = base.COLUNAS
    ws.append(cols)
    idx = {c: i + 1 for i, c in enumerate(cols)}
    L = {c: get_column_letter(i) for c, i in idx.items()}
    for n, r in enumerate(rows, start=2):
        linha = []
        for c in cols:
            v = r.get(c)
            if isinstance(v, bool):
                v = "sim" if v else "nao"
            linha.append(v)
        ws.append(linha)
        # formulas editaveis
        ws[f"{L['custo_estimado']}{n}"] = (
            f'=IF({L["custo_real"]}{n}<>"",{L["custo_real"]}{n},'
            f'IF(IF({L["preco_de"]}{n}<>"",{L["preco_de"]}{n},{L["preco_por"]}{n})>0,'
            f'ROUND(IF({L["preco_de"]}{n}<>"",{L["preco_de"]}{n},{L["preco_por"]}{n})/Premissas!$B$2,2),""))')
        ws[f"{L['margem_estimada_pct']}{n}"] = (
            f'=IF(AND({L["preco_por"]}{n}<>"",{L["custo_estimado"]}{n}<>""),'
            f'ROUND(({L["preco_por"]}{n}-{L["custo_estimado"]}{n})/{L["preco_por"]}{n}*100,1),"")')
        ws[f"{L['margem_critica']}{n}"] = (
            f'=IF({L["margem_estimada_pct"]}{n}="","",IF({L["margem_estimada_pct"]}{n}<Premissas!$B$3,"sim","nao"))')
        for c in base.CAMPOS_PENDENTES:
            if not r.get(c):
                ws[f"{L[c]}{n}"].fill = PatternFill("solid", fgColor=AMARELO)
        for c in ("preco_de", "preco_por", "custo_estimado", "custo_real"):
            ws[f"{L[c]}{n}"].number_format = '"R$" #,##0.00'
        if r.get("margem_critica"):
            ws[f"{L['margem_estimada_pct']}{n}"].fill = PatternFill("solid", fgColor=VERMELHO)
    for c in ws[1]:
        c.font = Font(bold=True, color=PEARL)
        c.fill = PatternFill("solid", fgColor=ESPRESSO)
        c.alignment = Alignment(wrap_text=True, vertical="center")
    larg = {"sku": 14, "nome": 36, "titulo_marketplace": 38, "descricao_rascunho": 60, "palavras_chave": 40,
            "hashtags": 40, "imagem_arquivo": 44, "imagem_url_origem": 30, "campos_pendentes": 50, "link_catalogo": 30}
    for c, i in idx.items():
        ws.column_dimensions[get_column_letter(i)].width = larg.get(c, 16)
    ws.freeze_panes = ws[f"C2"]
    ws.auto_filter.ref = ws.dimensions
    ws.row_dimensions[1].height = 32

    wp = wb.create_sheet("Premissas")
    wp.append(["Premissa", "Valor", "Observacao"])
    wp.append(["Markup (preco cheio / custo)", base.MARKUP, "Voce informou 2,0 a 2,1. Edite aqui e custo/margem recalculam."])
    wp.append(["Margem minima de alerta (%)", 25, "Abaixo disso a peca e marcada como margem critica."])
    wp.append(["Cadastro de custo_real", "", "Preencha custo_real na aba Produtos para substituir a estimativa."])
    for c in wp[1]:
        c.font = Font(bold=True, color=PEARL)
        c.fill = PatternFill("solid", fgColor=ESPRESSO)
    wp.column_dimensions["A"].width = 34
    wp.column_dimensions["C"].width = 90

    wd = wb.create_sheet("Pendencias")
    wd.append(["Campo", "Pecas sem preenchimento", "% do catalogo"])
    total = len(rows) or 1
    for c in base.CAMPOS_PENDENTES + ["preco_por"]:
        falta = sum(1 for r in rows if not r.get(c))
        wd.append([c, falta, round(falta / total * 100)])
    for c in wd[1]:
        c.font = Font(bold=True, color=PEARL)
        c.fill = PatternFill("solid", fgColor=ESPRESSO)
    wd.column_dimensions["A"].width = 28
    wd.column_dimensions["B"].width = 26

    wk = wb.create_sheet("Dicionario")
    wk.append(["Campo", "Para que serve / exigencia", "Onde importa"])
    for d in DICIONARIO:
        wk.append(list(d))
    for c in wk[1]:
        c.font = Font(bold=True, color=PEARL)
        c.fill = PatternFill("solid", fgColor=ESPRESSO)
    wk.column_dimensions["A"].width = 38
    wk.column_dimensions["B"].width = 110
    wk.column_dimensions["C"].width = 30
    for w_ in (wk,):
        for row in w_.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(destino)
