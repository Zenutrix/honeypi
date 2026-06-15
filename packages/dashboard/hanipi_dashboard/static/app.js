'use strict';

const UNITS = {
  temperature_c: '°C', humidity_pct: '%', pressure_hpa: 'hPa',
  weight_kg: 'kg', voltage_v: 'V', illuminance_lux: 'lx',
  gas_resistance_ohm: 'Ω',
};
const LABELS = {
  weight_kg: 'Gewicht', temperature_c: 'Temperatur', humidity_pct: 'Feuchte',
  pressure_hpa: 'Luftdruck', illuminance_lux: 'Licht', gas_resistance_ohm: 'Gas',
  voltage_v: 'Spannung',
};
const HIVE_COLORS = ['#f59e0b','#10b981','#3b82f6','#8b5cf6','#ef4444','#06b6d4','#f97316'];

let chart = null;
let currentHours = 1;
let currentHiveId = null;
let customFromTs = null;
let customToTs   = null;
let hives = [];
let dayStatsCache = [];
let weightTrendCache = {};   // keyed by hive_id (or '' for all)

function fmtTime(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}
function fmtDate(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleString('de-AT', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' });
}

// ── Status ───────────────────────────────────────────────────────────────────
async function refreshStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    dot.className = 'status-dot ' + (d.active ? 'online' : 'offline');
    txt.textContent = d.active ? 'Agent aktiv' : 'Agent gestoppt';
  } catch {}

  try {
    const r = await fetch('/api/maintenance/status');
    const d = await r.json();
    const badge = document.getElementById('maintenanceBadge');
    if (badge) badge.classList.toggle('visible', !!d.active);
  } catch {}
}

// ── Hive Tabs ────────────────────────────────────────────────────────────────
async function loadHives() {
  try {
    const r = await fetch('/api/hives');
    hives = await r.json();
  } catch { hives = []; }
  renderHiveTabs();
}

function renderHiveTabs() {
  const container = document.getElementById('hiveTabs');
  if (!container) return;
  if (hives.length === 0) { container.style.display = 'none'; return; }
  container.style.display = 'flex';
  container.innerHTML = '';

  const all = document.createElement('button');
  all.className = 'hive-tab' + (currentHiveId === null ? ' active' : '');
  all.textContent = 'Alle';
  all.onclick = () => { currentHiveId = null; renderHiveTabs(); refreshData(); };
  container.appendChild(all);

  hives.forEach((h, i) => {
    const btn = document.createElement('button');
    btn.className = 'hive-tab' + (currentHiveId === h.id ? ' active' : '');
    const dot = `<span class="hive-dot" style="background:${h.color || HIVE_COLORS[i % HIVE_COLORS.length]}"></span>`;
    btn.innerHTML = dot + h.name;
    btn.onclick = () => { currentHiveId = h.id; renderHiveTabs(); refreshData(); };
    container.appendChild(btn);
  });
}

// ── Day stats & weight trend (background fetches) ─────────────────────────────
async function fetchDayStats() {
  try {
    const p = new URLSearchParams();
    if (currentHiveId) p.set('hive_id', currentHiveId);
    const r = await fetch('/api/data/day-stats?' + p);
    dayStatsCache = await r.json();
  } catch { dayStatsCache = []; }
}

async function fetchWeightTrend() {
  // Always fetch per-hive so mixed-hive views stay meaningful
  const targets = currentHiveId
    ? [currentHiveId]
    : hives.map(h => h.id);
  await Promise.all(targets.map(async id => {
    try {
      const r = await fetch('/api/data/weight-trend?hive_id=' + encodeURIComponent(id));
      weightTrendCache[id] = await r.json();
    } catch {}
  }));
}

function getDayStats(sensorName, key) {
  return dayStatsCache.find(r => r.sensor_name === sensorName && r.key === key) || null;
}

function getWeightTrend(hiveId) {
  return weightTrendCache[hiveId || ''] || null;
}

// ── Cards ────────────────────────────────────────────────────────────────────
function hiveColorFor(hiveId) {
  if (!hiveId) return '#f59e0b';
  const h = hives.find(x => x.id === hiveId);
  return h ? h.color : '#f59e0b';
}

async function refreshData() {
  await Promise.all([fetchDayStats(), fetchWeightTrend()]);

  const params = new URLSearchParams();
  if (currentHiveId) params.set('hive_id', currentHiveId);
  let rows = [];
  try {
    const r = await fetch('/api/data/latest?' + params);
    rows = await r.json();
  } catch {}

  const grid = document.getElementById('cardsGrid');
  if (!grid) return;

  if (rows.length === 0) {
    grid.innerHTML = `<div class="empty-state">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1"/></svg>
      <p>Noch keine Messdaten vorhanden.</p>
      <p>Sensoren in den <a href="/config-ui">Einstellungen</a> konfigurieren.</p>
    </div>`;
    document.getElementById('chartCard')?.classList.add('hidden');
    return;
  }

  grid.innerHTML = '';
  rows.forEach(row => {
    const unit  = UNITS[row.key] || '';
    const label = LABELS[row.key] || row.key.replace(/_/g, ' ');
    const color = hiveColorFor(row.hive_id);
    const val   = parseFloat(row.value);
    const displayVal = Number.isInteger(val) ? val : val.toFixed(1);

    // Min/max today
    const stats = getDayStats(row.sensor_name, row.key);
    let statsHtml = '';
    if (stats) {
      const mn = parseFloat(stats.min_val).toFixed(1);
      const mx = parseFloat(stats.max_val).toFixed(1);
      statsHtml = `<div class="card-minmax">Min ${mn}${unit} · Max ${mx}${unit}</div>`;
    }

    // Weight trend (only for weight_kg cards)
    let trendHtml = '';
    if (row.key === 'weight_kg') {
      const trend = getWeightTrend(row.hive_id);
      if (trend) {
        const parts = [];
        if (trend.delta_1d !== null) {
          const sign = trend.delta_1d >= 0 ? '+' : '';
          const arrow = trend.delta_1d >= 0 ? '↑' : '↓';
          const cls = trend.delta_1d >= 0 ? 'trend-up' : 'trend-down';
          parts.push(`<span class="${cls}">${arrow} ${sign}${trend.delta_1d.toFixed(2)} kg heute</span>`);
        }
        if (trend.honey_7d !== null && trend.honey_7d > 0) {
          parts.push(`<span class="trend-honey">+${trend.honey_7d.toFixed(2)} kg Honig (7T)</span>`);
        }
        if (parts.length) {
          trendHtml = `<div class="card-trend">${parts.join('<span class="trend-sep">·</span>')}</div>`;
        }
      }
    }

    const card = document.createElement('div');
    card.className = 'sensor-card';
    card.style.setProperty('--card-accent', color);
    card.innerHTML = `
      <div class="card-label">${label}</div>
      <div class="card-value">${displayVal}<span class="card-unit">${unit}</span></div>
      ${statsHtml}
      ${trendHtml}
      <div class="card-meta">${row.sensor_name} · ${fmtTime(row.timestamp)}</div>`;
    card.onclick = () => loadChart(row.sensor_name, row.key);
    grid.appendChild(card);
  });

  const ts = document.getElementById('lastUpdated');
  if (ts) ts.textContent = 'Aktualisiert: ' + new Date().toLocaleTimeString('de-AT');

  updateCsvLink();
  loadChartAuto(rows);
}

// ── CSV export ────────────────────────────────────────────────────────────────
function updateCsvLink() {
  const link = document.getElementById('csvLink');
  if (!link) return;
  const p = new URLSearchParams();
  if (currentHiveId) p.set('hive_id', currentHiveId);
  if (customFromTs && customToTs) {
    p.set('from_ts', customFromTs);
    p.set('to_ts', customToTs);
  } else {
    p.set('hours', currentHours || 24);
  }
  link.href = '/api/data/export.csv?' + p;
  link.download = '';
}

// ── Date range ────────────────────────────────────────────────────────────────
function applyDateRange() {
  const from = document.getElementById('fromDate').value;
  const to   = document.getElementById('toDate').value;
  if (!from || !to) return;
  customFromTs = new Date(from).getTime() / 1000;
  customToTs   = new Date(to).getTime()   / 1000;
  document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('customRangeToggle')?.classList.add('active');
  refreshData();
  loadChartCustom(null, null);  // will be called inside refreshData via loadChartAuto
}

function clearCustomRange() {
  customFromTs = null;
  customToTs   = null;
}

// ── Chart ─────────────────────────────────────────────────────────────────────
async function loadChartAuto(rows) {
  if (rows.length === 0) return;
  await loadChart(rows[0].sensor_name, rows[0].key);
}

async function loadChart(sensor, key) {
  let history = [];
  try {
    const p = new URLSearchParams({ sensor });
    if (currentHiveId) p.set('hive_id', currentHiveId);
    if (customFromTs && customToTs) {
      p.set('from_ts', customFromTs);
      p.set('to_ts', customToTs);
    } else {
      p.set('hours', currentHours);
    }
    const r = await fetch('/api/data/history?' + p);
    history = await r.json();
  } catch {}

  const card = document.getElementById('chartCard');
  const canvas = document.getElementById('chart');
  if (!card || !canvas) return;

  const filtered = history.filter(r => r.sensor_name === sensor && r.key === key);
  if (filtered.length === 0) { card.classList.add('hidden'); return; }

  card.classList.remove('hidden');
  const labels = filtered.map(r => fmtDate(r.timestamp));
  const data   = filtered.map(r => r.value);
  const unit   = UNITS[key] || '';

  if (chart) chart.destroy();
  chart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: `${sensor} · ${key}`,
        data,
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,.08)',
        borderWidth: 2,
        pointRadius: filtered.length > 100 ? 0 : 3,
        pointBackgroundColor: '#f59e0b',
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#2c2c2e',
          borderColor: '#48484a',
          borderWidth: 1,
          titleColor: '#ffffff',
          bodyColor: '#8e8e93',
          callbacks: { label: ctx => `${ctx.parsed.y.toFixed(2)} ${unit}` },
        },
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 8, font: { size: 11 }, color: '#48484a' },
          grid: { color: '#3a3a3c' },
          border: { color: '#48484a' },
        },
        y: {
          ticks: { callback: v => `${v} ${unit}`, font: { size: 11 }, color: '#48484a' },
          grid: { color: '#3a3a3c' },
          border: { color: '#48484a' },
        },
      },
    },
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.time-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.id === 'customRangeToggle') {
      const row = document.getElementById('dateRangeRow');
      row?.classList.toggle('hidden');
      return;
    }
    document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentHours = parseInt(btn.dataset.h);
    clearCustomRange();
    document.getElementById('dateRangeRow')?.classList.add('hidden');
    refreshData();
  });
});

async function init() {
  await loadHives();
  await refreshData();
  await refreshStatus();
  setInterval(refreshData, 30000);
  setInterval(refreshStatus, 60000);
}

init();
