#!/usr/bin/env bash
# Vigia a fila minuto a minuto durante $1 minutos (padrao 165). Cada publicacao e registrada e enviada ao GitHub na hora.
# Motivo: o agendador (cron) do GitHub atrasa de 45 a 95 min; este laco garante a pontualidade dentro de cada execucao.
# Antes de cada publicacao, sincroniza o catalogo do site: pecas removidas saem da fila, pecas novas entram.
set -u
DURACAO_MIN="${1:-165}"
fim=$((SECONDS + DURACAO_MIN * 60))
while [ "$SECONDS" -lt "$fim" ]; do
  git pull -q --rebase || echo "aviso: git pull falhou (segue com a copia local)"
  python ferramentas/sincronizar_catalogo.py --executar || echo "aviso: sincronizar_catalogo.py retornou erro (segue sem sincronizar)"
  python ferramentas/postar.py --executar || echo "aviso: postar.py retornou erro"
  git add instagram/status_postagens.json instagram/fila_postagens.json instagram/catalogo_visto.json instagram/midia/feed instagram/midia/stories
  if ! git diff --cached --quiet; then
    git commit -q -m "chore: atualiza status das postagens e sincroniza catalogo"
    for t in 1 2 3; do
      git pull -q --rebase && git push -q && break
      sleep 5
    done
  fi
  sleep 60
done
