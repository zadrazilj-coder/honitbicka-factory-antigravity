// HONBIČKA FACTORY - Dashboard Frontend Logic

let allGames = [];
let currentGame = null;

document.addEventListener("DOMContentLoaded", () => {
  mermaid.initialize({ startOnLoad: false, theme: 'dark' });
  loadCatalog();
  loadMapy();
});

function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));

  document.getElementById(`tab-${tabId}`).classList.add('active');
  const navBtn = document.getElementById(`nav-${tabId}`);
  if (navBtn) navBtn.classList.add('active');
}

function switchSubtab(subtabId) {
  document.querySelectorAll('.subtab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.subtab-btn').forEach(el => el.classList.remove('active'));

  document.getElementById(`subtab-${subtabId}`).classList.add('active');
  event.target.classList.add('active');

  if (subtabId === 'mapa' && currentGame && currentGame.mermaid) {
    renderMermaid(currentGame.mermaid);
  }
}

async function loadCatalog() {
  try {
    const res = await fetch('/api/games');
    allGames = await res.json();
    renderCatalog(allGames);
  } catch (err) {
    document.getElementById('games-grid').innerHTML = `<div class="loading-spinner">Chyba při načítání her: ${err}</div>`;
  }
}

function renderCatalog(games) {
  const grid = document.getElementById('games-grid');
  if (!games || games.length === 0) {
    grid.innerHTML = '<div class="loading-spinner">Žádné vygenerované hry nenalezeny.</div>';
    return;
  }

  grid.innerHTML = games.map(game => `
    <div class="game-card">
      <div>
        <div class="card-top">
          <h3 class="card-title">${escapeHtml(game.tema)}</h3>
          <span class="badge badge-ok">${game.stav}</span>
        </div>
        <div class="card-meta">
          <span class="badge badge-archetype">${game.archetyp || 'A1'}</span>
          <span class="tag">Seed: ${game.seed || '42'}</span>
          <span class="tag">${game.slug}</span>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn-sm btn-primary-sm" onclick="openDetail('${game.slug}')">🗺️ Detail & Mapa</button>
        ${game.pdf_soubory && game.pdf_soubory.length > 0 ? `
          <a class="btn-sm" href="/${game.pdf_soubory[0].cesta}" target="_blank">📄 Stáhnout PDF</a>
        ` : ''}
      </div>
    </div>
  `).join('');
}

function filterGames() {
  const query = document.getElementById('search-input').value.lowerCase || document.getElementById('search-input').value.toLowerCase();
  const vek = document.getElementById('filter-vek').value;
  const format = document.getElementById('filter-format').value;

  const filtered = allGames.filter(g => {
    const matchQuery = !query || g.tema.toLowerCase().includes(query) || g.slug.toLowerCase().includes(query);
    const matchVek = !vek || g.vek === vek;
    const matchFormat = !format || g.format_hracu === format;
    return matchQuery && matchVek && matchFormat;
  });

  renderCatalog(filtered);
}

async function openDetail(slug) {
  switchTab('detail');
  document.getElementById('detail-title').innerText = "Načítám detail...";

  try {
    const res = await fetch(`/api/games/${slug}`);
    currentGame = await res.json();

    document.getElementById('detail-title').innerText = currentGame.slug;
    document.getElementById('detail-badges').innerHTML = `
      <span class="badge badge-ok">STAV: OK</span>
    `;

    // 1. Render Cards
    if (currentGame.karty) {
      document.getElementById('cards-container').innerHTML = currentGame.karty.map(k => `
        <div class="card-item">
          <h4>KARTA #${k.cislo}: ${escapeHtml(k.nazev)}</h4>
          <p><strong>Typ:</strong> ${k.typ}</p>
          <p style="margin-top:0.4rem; color:#9ca3af;"><em>${escapeHtml(k.atmosfera || '')}</em></p>
          <p style="margin-top:0.4rem;">${escapeHtml(k.uvod || '')}</p>
        </div>
      `).join('');
    } else {
      document.getElementById('cards-container').innerHTML = '<p class="subtext">Karty nejsou k dispozici.</p>';
    }

    // 2. Render Posudek
    if (currentGame.report && currentGame.report.editorial_report) {
      document.getElementById('posudek-container').innerHTML = currentGame.report.editorial_report.map(r => `
        <div class="card-item" style="margin-bottom:0.75rem;">
          <div class="flex-between">
            <strong>Check ${r.check}</strong>
            <span class="badge badge-ok">${r.verdikt ? 'PASS' : 'FAIL'}</span>
          </div>
          <p style="margin-top:0.4rem; font-size:0.85rem; color:#d1d5db;">${escapeHtml(r.zduvodneni)}</p>
        </div>
      `).join('');
    } else {
      document.getElementById('posudek-container').innerHTML = '<p class="subtext">Posudek není k dispozici.</p>';
    }

    // 3. Render Soubory
    if (currentGame.soubory) {
      document.getElementById('soubory-container').innerHTML = currentGame.soubory.map(f => `
        <div class="file-card">
          <span>📄 ${f.nazev}</span>
          <a class="btn-sm" href="/${f.cesta}" target="_blank">Otevřít</a>
        </div>
      `).join('');
    }

    // 4. Render Mermaid
    if (currentGame.mermaid) {
      renderMermaid(currentGame.mermaid);
    }

  } catch (err) {
    document.getElementById('detail-title').innerText = "Chyba při načítání detailu";
  }
}

async function renderMermaid(graphDefinition) {
  const container = document.getElementById('mermaid-container');
  container.innerHTML = '<div class="loading-spinner">Renderuji mapu...</div>';

  try {
    const id = 'mermaid-svg-' + Date.now();
    const { svg } = await mermaid.render(id, graphDefinition);
    container.innerHTML = svg;
  } catch (err) {
    container.innerHTML = `<pre style="color:#f87171;">Chyba renderu Mermaid mapy: ${err}</pre>`;
  }
}

async function loadMapy() {
  try {
    const res = await fetch('/api/mapy');
    const mapy = await res.json();
    document.getElementById('mapy-list').innerHTML = mapy.map(m => `
      <div class="file-card">
        <span>🌐 ${m.nazev}</span>
        <a class="btn-sm btn-primary-sm" href="/${m.cesta}" download>Stáhnout .twee</a>
      </div>
    `).join('');
  } catch (err) {
    document.getElementById('mapy-list').innerHTML = `<p class="subtext">Chyba: ${err}</p>`;
  }
}

async function handleGenerate(e) {
  e.preventDefault();
  const statusBox = document.getElementById('gen-status');
  statusBox.style.display = 'block';
  statusBox.innerHTML = '⏳ Odosílám zadání a spouštím generování...';

  const params = {
    tema: document.getElementById('gen-tema').value,
    vek: document.getElementById('gen-vek').value,
    format_hracu: document.getElementById('gen-format').value,
    obtiznost: document.getElementById('gen-obtiznost').value,
    ton: document.getElementById('gen-ton').value,
    prostredi: ["les", "park"]
  };

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    const data = await res.json();
    statusBox.innerHTML = `✅ ${data.message}! Generování běží v pozadí. Za pár minut obnovte katalog her.`;
  } catch (err) {
    statusBox.innerHTML = `❌ Chyba při generování: ${err}`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
