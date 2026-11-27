# Susana Freitas Store: base de dados + automação do Instagram

## O que existe aqui

```
catalogo/
  produtos_mestre.xlsx     <- planilha mestre (95 peças). Células amarelas = dado que falta.
  produtos_mestre.csv/json <- mesma base para os scripts
  imagens/<categoria>/SF-XXX-NNN_nome.jpg
  entrada/                 <- COLOQUE AQUI as fotos das peças novas (veja LEIA-ME.txt)
  fonte/painel_AAAA-MM-DD.json  <- cópia do que estava no painel do site
instagram/
  calendario_30_dias.xlsx/csv   <- 23/11/2026 a 22/12/2026 (133 itens)
  fila_postagens.json           <- a mesma agenda em formato de máquina
  midia/feed|stories|cartoes    <- artes geradas (Feed 4:5, Stories 9:16, cartões)
  destaques/                    <- capas, slides, ROTEIRO.md e mapa
ferramentas/                    <- scripts (Python 3.13 + Pillow + openpyxl)
POSTAGENS/                      <- sua pasta atual de edição (não é alterada)
```

## Rotina quando chegar peça nova

1. Foto na pasta `catalogo/entrada/`, nome no seu padrão: `Vestido Lara 339,90.jpg` ou `Vestido Lara DE 557,00 POR 339,90.jpg`.
2. `python -I -X utf8 ferramentas/registrar_novas.py`
3. Cadastrar a peça no painel do site.
4. Abrir `produtos_mestre.xlsx` e completar tamanhos, estoque, tecido, custo real, medidas.
5. Gerar mais calendário: `python -I -X utf8 ferramentas/calendario.py --inicio 2026-12-23 --dias 30` (preserva o que já foi publicado e evita repetir peças).

Se mexer em preços direto no site: `node ferramentas/exportar_do_painel.js` (veja o cabeçalho do arquivo) e depois `python -I -X utf8 ferramentas/base.py montar`. Os campos preenchidos à mão são preservados.

## Publicação automática (grátis)

O Publora no plano gratuito permite 15 posts/mês, 3 agendados por vez e agenda a 7 dias. O calendário tem 133 itens/mês, então não cabe. A alternativa gratuita é a **API oficial do Instagram + GitHub Actions** (`ferramentas/postar.py` + `.github/workflows/postar.yml`).

Estado atual: pronto e testado em **simulação**. Falta a configuração da Meta (só você pode fazer, exige login):

1. Conta do Instagram **profissional** (a loja aparece como "Vestuário (marca)", então provavelmente já é).
2. Criar um app em developers.facebook.com, adicionar o produto **Instagram** (API com login do Instagram), adicionar a conta da loja e gerar o token com as permissões de publicação (`instagram_business_basic`, `instagram_business_content_publish`; confirmar os nomes no console).
3. Criar repositório **público** no GitHub (as imagens precisam de URL pública; `catalogo/` e `POSTAGENS/` ficam de fora pelo `.gitignore`, então custos e margens não sobem).
4. Em *Settings > Secrets > Actions*: `IG_USER_ID` e `IG_ACCESS_TOKEN`.
5. Testar com `Run workflow` e acompanhar a aba Actions. O token vale 60 dias: renove com `ferramentas/renovar_token.py`.

Limites conhecidos: a API não publica **figurinhas** (enquete, link, caixinha), não cria **Destaques** e não posta **Reels sem o vídeo** (eles ficam em `aguardando_midia` até o MP4 existir em `instagram/midia/reels/`).

## Calendário em uma linha

Feed todo dia às 19:30 (domingo 10:30), Reels ter/qui/sáb às 12:00, Stories às 08:30, 13:00 e 20:45. Terça/quinta carrossel por categoria, sábado oportunidade, domingo institucional, Black Friday em 27/11. As 95 peças aparecem pelo menos uma vez. Os horários são hipóteses: ajuste depois de 14 dias olhando *Insights > Audiência*.

## Sincronização automática com o catálogo do site

Antes de cada publicação, `ferramentas/sincronizar_catalogo.py` (chamado pelo `ciclo.sh`) compara o site (tabela `produtos` do Supabase, leitura pública) com `instagram/catalogo_visto.json`:

- **Peça removida do site** → itens ainda não publicados dela na fila viram `cancelado` (o que já foi postado fica). Se a peça voltar (mesmo id), os itens são liberados.
- **Peça nova** → baixa a foto, gera story (e feed, se a foto servir e a margem permitir) e enfileira nos próximos horários livres (HH:40/HH:10, fora da grade fixa). Depois, localmente, rode `python -I -X utf8 ferramentas/sincronizar_catalogo.py --atualizar-mestre` para trazê-la à planilha mestre e preencher tamanhos/estoque/custo.
- **Travas:** se o site falhar, vier vazio/com menos da metade das peças, ou houver mais de 10 remoções numa rodada, nada é alterado.
- `calendario.py` ignora peças removidas ao gerar novos dias.
- Teste sem alterar nada: `python -I -X utf8 ferramentas/sincronizar_catalogo.py` (precisa de `SUPABASE_URL` e `SUPABASE_ANON_KEY` no ambiente).
- No GitHub: criar os secrets `SUPABASE_URL` e `SUPABASE_ANON_KEY` (os mesmos valores públicos que o site usa).
