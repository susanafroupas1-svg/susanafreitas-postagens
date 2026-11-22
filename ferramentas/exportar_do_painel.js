// Exporta o catalogo atual do painel do site para catalogo/fonte/painel_AAAA-MM-DD.json
// e depois voce roda: python -I -X utf8 ferramentas/base.py montar
//
// Requisitos (uma vez):   cd ferramentas && npm i playwright-core
// Uso (PowerShell):       $env:SF_ADMIN_SENHA="sua-senha"; node ferramentas/exportar_do_painel.js
// A senha vem do ambiente; nunca a grave neste arquivo.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const SENHA = process.env.SF_ADMIN_SENHA;
if (!SENHA) { console.error('Defina a variavel SF_ADMIN_SENHA.'); process.exit(1); }
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const CATS = ['BLUSAS', 'VESTIDOS', 'CALÇAS', 'SAIAS', 'CONJUNTOS & COLETES', 'TRICÔS'];

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  await page.goto('https://susanafreitasstore.com.br/#/admin', { waitUntil: 'networkidle' });
  const pw = page.locator('input[type="password"]');
  if (await pw.count()) { await pw.first().fill(SENHA); await pw.first().press('Enter'); await page.waitForTimeout(3000); }
  const grab = () => page.evaluate(() => [...document.querySelectorAll('div.group.relative')].filter(c => c.querySelector('img')).map(c => {
    const img = c.querySelector('img');
    return { alt: img.alt.trim(), src: img.currentSrc || img.src, lines: (c.innerText || '').split('\n').map(s => s.trim()).filter(Boolean) };
  }));
  const all = await grab();
  const catOf = {};
  for (const c of CATS) {
    await page.locator('button', { hasText: new RegExp('^\\s*' + c.replace('&', '\\&') + '\\s*$', 'i') }).first().click();
    await page.waitForTimeout(1200);
    for (const it of await grab()) catOf[it.src] = c;
  }
  all.forEach(a => a.categoria = catOf[a.src] || '?');
  const hoje = new Date().toISOString().slice(0, 10);
  const destino = path.join(__dirname, '..', 'catalogo', 'fonte', `painel_${hoje}.json`);
  fs.writeFileSync(destino, JSON.stringify(all, null, 1));
  console.log(`${all.length} produtos exportados -> ${destino}`);
  await browser.close();
})();
