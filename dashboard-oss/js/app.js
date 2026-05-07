let sessionsPage = 1;
let selectedWeek = null;
let weeksList = [];
let weekTotals = [];

document.addEventListener('DOMContentLoaded', () => {
  loadAll();
  setInterval(loadAll, 30000);
});

async function loadAll() {
  try {
    const wp = selectedWeek ? `&week=${selectedWeek}` : '';
    const resp = await fetch(`/api/sessions?page=${sessionsPage}&limit=10${wp}`).then(r => r.json());
    weeksList = resp.weeks || [];
    weekTotals = resp.weekTotals || [];
    renderWeekFilter();
    renderTokenCards(resp);
    renderModelBreakdown(resp.modelBreakdown || []);
    renderSessions(resp);
    document.getElementById('last-refresh').textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.error('Load failed:', err);
  }
}

function esc(s) { const d = document.createElement('div'); d.appendChild(document.createTextNode(String(s))); return d.innerHTML; }
function fmt(n) { return n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n); }
function pct(v, m) { return m ? Math.min((v||0)/m*100, 100) : 0; }

function weekLabel(w) {
  if (!w) return 'All Weeks';
  const [y, wn] = w.split('-W').map(Number);
  const jan1 = new Date(y, 0, 1);
  const start = new Date(y, 0, 1 + (wn * 7) - jan1.getDay());
  const end = new Date(start); end.setDate(end.getDate() + 6);
  const f = d => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  return `${f(start)} - ${f(end)}, ${y}`;
}

// ── Week Filter ──

function renderWeekFilter() {
  const el = document.getElementById('week-filter');
  if (!el) return;
  const idx = selectedWeek ? weeksList.indexOf(selectedWeek) : -1;
  const wt = selectedWeek ? weekTotals.find(w => w.week === selectedWeek) : null;
  const summary = wt
    ? `<span class="week-summary">${wt.sessions} sessions &middot; $${wt.cost.toFixed(2)} &middot; ${fmt(wt.inputTokens + wt.outputTokens)} tokens</span>` : '';

  el.innerHTML = `
    <div class="week-nav">
      <button class="week-btn" onclick="navWeek(-1)" ${idx >= weeksList.length-1 ? 'disabled' : ''}>&larr;</button>
      <div class="week-label-group">
        <span class="week-current">${esc(selectedWeek ? weekLabel(selectedWeek) : 'All Weeks')}</span>
        ${summary}
      </div>
      <button class="week-btn" onclick="navWeek(1)" ${idx <= 0 && selectedWeek ? 'disabled' : ''}>&rarr;</button>
      <button class="week-btn week-btn-sm" onclick="resetWeek()" ${!selectedWeek ? 'disabled' : ''}>All</button>
    </div>
    <div class="week-chips">
      ${weeksList.slice(0,8).map(w => {
        const t = weekTotals.find(x => x.week === w);
        return `<button class="week-chip ${w===selectedWeek?'active':''}" onclick="pickWeek('${w}')">${weekLabel(w).split(',')[0]}<span class="chip-cost">${t ? '$'+t.cost.toFixed(2) : ''}</span></button>`;
      }).join('')}
    </div>`;
}

window.navWeek = d => {
  const i = selectedWeek ? weeksList.indexOf(selectedWeek) : -1;
  if (d === -1) selectedWeek = weeksList[i === -1 ? 0 : Math.min(i+1, weeksList.length-1)];
  else if (i > 0) selectedWeek = weeksList[i-1];
  else selectedWeek = null;
  sessionsPage = 1; loadAll();
};
window.pickWeek = w => { selectedWeek = selectedWeek === w ? null : w; sessionsPage = 1; loadAll(); };
window.resetWeek = () => { selectedWeek = null; sessionsPage = 1; loadAll(); };

// ── Token Cards ──

function renderTokenCards(resp) {
  const el = document.getElementById('token-cards');
  let d;
  if (selectedWeek) {
    const wt = weekTotals.find(w => w.week === selectedWeek);
    d = wt || { cost:0, inputTokens:0, outputTokens:0, cacheCreate:0, cacheRead:0, sessions:0 };
  } else {
    d = weekTotals.reduce((a, w) => {
      a.cost += w.cost; a.inputTokens += w.inputTokens; a.outputTokens += w.outputTokens;
      a.cacheRead += w.cacheRead; a.cacheCreate += w.cacheCreate; a.sessions += w.sessions;
      return a;
    }, { cost:0, inputTokens:0, outputTokens:0, cacheRead:0, cacheCreate:0, sessions:0 });
  }

  const mx = Math.max(d.inputTokens, d.outputTokens, d.cacheCreate, d.cacheRead, 1);
  const period = selectedWeek ? weekLabel(selectedWeek) : 'All Sessions';
  const badge = d.sessions ? `<span class="sessions-badge">${d.sessions} session${d.sessions!==1?'s':''}</span>` : '';

  el.innerHTML = `
    <div class="card card-accent">
      <div class="card-label">Total Cost</div>
      <div class="card-value">$${(d.cost||0).toFixed(4)}</div>
      <div class="card-desc">${badge} ${esc(period)}</div>
    </div>
    <div class="card">
      <div class="card-label">Input Tokens</div>
      <div class="card-value">${fmt(d.inputTokens||0)}</div>
      <div class="bar"><div class="bar-fill bar-input" style="width:${pct(d.inputTokens,mx)}%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Output Tokens</div>
      <div class="card-value">${fmt(d.outputTokens||0)}</div>
      <div class="bar"><div class="bar-fill bar-output" style="width:${pct(d.outputTokens,mx)}%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Cache Created</div>
      <div class="card-value">${fmt(d.cacheCreate||0)}</div>
      <div class="bar"><div class="bar-fill bar-cache-w" style="width:${pct(d.cacheCreate,mx)}%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Cache Read</div>
      <div class="card-value">${fmt(d.cacheRead||0)}</div>
      <div class="bar"><div class="bar-fill bar-cache-r" style="width:${pct(d.cacheRead,mx)}%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Avg Cost / Session</div>
      <div class="card-value">$${d.sessions ? (d.cost/d.sessions).toFixed(4) : '0.0000'}</div>
      <div class="card-desc">Across ${d.sessions||0} sessions</div>
    </div>`;
}

// ── Model Breakdown ──

function renderModelBreakdown(models) {
  const el = document.getElementById('model-usage');
  if (!models.length) { el.innerHTML = '<p class="muted">No model data yet.</p>'; return; }
  el.innerHTML = `
    <table class="data-table">
      <thead><tr><th>Model</th><th>Sessions</th><th>Input</th><th>Output</th><th>Cost</th></tr></thead>
      <tbody>${models.map(m => `
        <tr>
          <td><strong>${esc(m.model)}</strong></td>
          <td>${m.sessions}</td>
          <td>${fmt(m.inputTokens)}</td>
          <td>${fmt(m.outputTokens)}</td>
          <td style="font-weight:600">$${m.cost.toFixed(4)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

// ── Sessions Table ──

function renderSessions(resp) {
  const el = document.getElementById('sessions-table');
  const ss = resp.sessions || [];
  const { total, page, totalPages } = resp;
  if (!ss.length) { el.innerHTML = '<p class="muted">No sessions found.</p>'; return; }

  const pag = totalPages > 1 ? `
    <div class="pagination">
      <button class="page-btn" onclick="goPage(${page-1})" ${page<=1?'disabled':''}>&larr; Prev</button>
      <span class="page-info">Page ${page} of ${totalPages} (${total} sessions)</span>
      <button class="page-btn" onclick="goPage(${page+1})" ${page>=totalPages?'disabled':''}>Next &rarr;</button>
    </div>` : `<div class="pagination"><span class="page-info">${total} session${total!==1?'s':''}</span></div>`;

  el.innerHTML = `${pag}
    <table class="data-table">
      <thead><tr><th>Date</th><th>Session</th><th>Project</th><th>Model</th><th>Msgs</th><th>Cost</th><th>In</th><th>Out</th></tr></thead>
      <tbody>${ss.map(s => {
        const dt = s.startedAt ? new Date(s.startedAt) : null;
        const date = dt ? dt.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : '-';
        const time = dt ? dt.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}) : '';
        const cc = (s.cost||0) > 1 ? 'var(--red)' : (s.cost||0) > 0.5 ? 'var(--orange)' : 'var(--fg)';
        return `<tr>
          <td><div class="date-main">${esc(date)}</div><div class="date-sub">${esc(time)}</div></td>
          <td><code>${esc(s.id.substring(0,12))}</code></td>
          <td class="col-project">${esc(s.project||'-')}</td>
          <td><span class="model-chip">${esc(s.model||'unknown')}</span></td>
          <td>${s.messages||0}</td>
          <td style="font-weight:600;color:${cc}">$${(s.cost||0).toFixed(4)}</td>
          <td>${fmt(s.inputTokens||0)}</td>
          <td>${fmt(s.outputTokens||0)}</td>
        </tr>`;}).join('')}
      </tbody>
    </table>${pag}`;
}

window.goPage = p => { if (p >= 1) { sessionsPage = p; loadAll(); } };
