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
const SENSOR_KEYS = {
  hx711:   ['weight_kg'],
  ds18b20: ['temperature_c'],
  bme280:  ['temperature_c', 'humidity_pct', 'pressure_hpa'],
  bme680:  ['temperature_c', 'humidity_pct', 'pressure_hpa', 'gas_resistance_ohm'],
  bh1750:  ['illuminance_lux'],
  ina3221: ['voltage_v'],
};
const SENSOR_ICONS = {
  hx711:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8h18M3 3h18M12 3v5"/><path d="M8 8v13M16 8v13M5 21h14"/><circle cx="12" cy="17" r="1.5" fill="currentColor" stroke="none"/></svg>`,
  ds18b20: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>`,
  bme280:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/></svg>`,
  bme680:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="6.3" y1="4.3" x2="7.7" y2="5.7"/><line x1="17.7" y1="4.3" x2="16.3" y2="5.7"/></svg>`,
  bh1750:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="6.76" y2="6.76"/><line x1="17.24" y1="17.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="6.76" y2="17.24"/><line x1="17.24" y1="6.76" x2="19.07" y2="4.93"/></svg>`,
  ina3221: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/></svg>`,
};

const HIVE_COLORS = ['#f59e0b','#10b981','#3b82f6','#8b5cf6','#ef4444','#06b6d4','#f97316'];

let currentHours = 1;
let currentHiveId = null;
let customFromTs = null;
let customToTs   = null;
let hives = [];
let dayStatsCache = [];
let weightTrendCache = {};
let configSensors = [];
let _sparkId = 0;

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
    const wrap = document.createElement('div');
    wrap.className = 'hive-tab-wrap';

    const btn = document.createElement('button');
    btn.className = 'hive-tab' + (currentHiveId === h.id ? ' active' : '');
    const dot = `<span class="hive-dot" style="background:${h.color || HIVE_COLORS[i % HIVE_COLORS.length]}"></span>`;
    btn.innerHTML = dot + h.name;
    btn.onclick = () => { currentHiveId = h.id; renderHiveTabs(); refreshData(); };

    const link = document.createElement('a');
    link.className = 'hive-tab-detail';
    link.href = `/hives/${h.id}`;
    link.title = `${h.name} Details`;
    link.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="12" height="12"><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`;

    wrap.appendChild(btn);
    wrap.appendChild(link);
    container.appendChild(wrap);
  });
}

// ── Background fetches ────────────────────────────────────────────────────────
async function fetchDayStats() {
  try {
    const p = new URLSearchParams();
    if (currentHiveId) p.set('hive_id', currentHiveId);
    const r = await fetch('/api/data/day-stats?' + p);
    dayStatsCache = await r.json();
  } catch { dayStatsCache = []; }
}

async function fetchWeightTrend() {
  const targets = currentHiveId ? [currentHiveId] : hives.map(h => h.id);
  await Promise.all(targets.map(async id => {
    try {
      const r = await fetch('/api/data/weight-trend?hive_id=' + encodeURIComponent(id));
      weightTrendCache[id] = await r.json();
    } catch {}
  }));
}

async function fetchConfigSensors() {
  try {
    const r = await fetch('/api/config');
    const cfg = await r.json();
    configSensors = cfg.sensors || [];
  } catch { configSensors = []; }
}

function getDayStats(sensorName, key) {
  return dayStatsCache.find(r => r.sensor_name === sensorName && r.key === key) || null;
}
function getWeightTrend(hiveId) {
  return weightTrendCache[hiveId || ''] || null;
}
function hiveColorFor(hiveId) {
  if (!hiveId) return '#f59e0b';
  const h = hives.find(x => x.id === hiveId);
  return h ? h.color : '#f59e0b';
}

// ── Sparkline ─────────────────────────────────────────────────────────────────
function downsample(arr, n = 52) {
  if (arr.length <= n) return arr;
  const step = (arr.length - 1) / (n - 1);
  return Array.from({ length: n }, (_, i) => arr[Math.round(i * step)]);
}

function sparklineSVG(values, color = '#f59e0b') {
  if (!values || values.length < 2) return '';
  const uid = 'sg' + (++_sparkId);
  const W = 200, H = 46;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = H - 5 - ((v - min) / range) * (H - 12);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const fillPts = `0,${H} ${pts.join(' ')} ${W},${H}`;
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="spark-svg" aria-hidden="true">
    <defs>
      <linearGradient id="${uid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.28"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <polygon points="${fillPts}" fill="url(#${uid})"/>
    <polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

// ── Card builder ──────────────────────────────────────────────────────────────
function buildCard(sensor, key, latestRow, sparkVals, color) {
  const unit  = UNITS[key]  || '';
  const label = LABELS[key] || key.replace(/_/g, ' ');
  const icon  = SENSOR_ICONS[sensor.type] || '';

  const card = document.createElement('div');
  card.className = 'sensor-card' + (latestRow ? '' : ' no-data');
  card.style.setProperty('--card-accent', color);

  if (!latestRow) {
    card.innerHTML = `
      <div class="card-head">
        <div class="card-icon">${icon}</div>
        <div class="card-label">${label}</div>
        <div class="card-sensor-name">${sensor.name}</div>
      </div>
      <div class="card-empty">
        <div class="card-empty-dot"></div>
        <div class="card-empty-text">Warte auf erste<br>Messung…</div>
      </div>`;
    return card;
  }

  const val = parseFloat(latestRow.value);
  const displayVal = isNaN(val) ? '—' : (Number.isInteger(val) ? val : val.toFixed(1));

  const stats = getDayStats(latestRow.sensor_name, key);
  const minMaxText = stats
    ? `↓${parseFloat(stats.min_val).toFixed(1)}  ↑${parseFloat(stats.max_val).toFixed(1)} ${unit}`
    : '';

  let trendArrow = '';
  let deltaHtml  = '';
  if (key === 'weight_kg') {
    const trend = getWeightTrend(latestRow.hive_id);
    if (trend && trend.delta_1d !== null && trend.delta_1d !== undefined) {
      const up   = trend.delta_1d >= 0;
      const cls  = up ? 'up' : 'down';
      const sign = up ? '+' : '';
      trendArrow = `<span class="card-trend-arrow ${cls}">${up ? '↑' : '↓'}</span>`;
      deltaHtml  = `<div class="card-delta"><span class="${cls}">${sign}${trend.delta_1d.toFixed(2)} kg heute</span>`;
      if (trend.honey_7d > 0)
        deltaHtml += ` <span class="honey">+${trend.honey_7d.toFixed(2)} kg Honig (7T)</span>`;
      deltaHtml += '</div>';
    }
  }

  const spark = sparkVals.length >= 2 ? sparklineSVG(sparkVals, color) : '';

  card.innerHTML = `
    <div class="card-head">
      <div class="card-icon">${icon}</div>
      <div class="card-label">${label}</div>
      <div class="card-sensor-name">${sensor.name}</div>
    </div>
    <div class="card-body">
      <div class="card-value-row">
        <span class="card-value">${displayVal}</span><span class="card-unit">${unit}</span>
        ${trendArrow}
      </div>
      ${deltaHtml}
    </div>
    ${spark ? `<div class="card-spark">${spark}</div>` : ''}
    <div class="card-foot">
      <span class="card-minmax">${minMaxText}</span>
      <span class="card-time">${fmtTime(latestRow.timestamp)}</span>
    </div>`;

  card.onclick = () => openChartModal(latestRow.sensor_name, key, label, unit, color);
  return card;
}

// ── Data refresh ──────────────────────────────────────────────────────────────
async function refreshData() {
  const ts = document.getElementById('lastUpdated');
  if (ts) ts.classList.add('refreshing');
  await Promise.all([fetchDayStats(), fetchWeightTrend(), fetchConfigSensors()]);

  const params = new URLSearchParams();
  if (currentHiveId) params.set('hive_id', currentHiveId);

  let latestRows = [];
  try {
    const r = await fetch('/api/data/latest?' + params);
    latestRows = await r.json();
  } catch {}

  // Fetch 24h history for all sensors at once (sparklines)
  let historyRows = [];
  try {
    const hp = new URLSearchParams({ hours: 24 });
    if (currentHiveId) hp.set('hive_id', currentHiveId);
    const r = await fetch('/api/data/history?' + hp);
    historyRows = await r.json();
  } catch {}

  // Build lookup maps
  const latestMap  = {};  // `${name}:${key}` → row
  const historyMap = {};  // `${name}:${key}` → [float values, chronological]
  latestRows.forEach(r  => { latestMap[`${r.sensor_name}:${r.key}`] = r; });
  historyRows.forEach(r => {
    const k = `${r.sensor_name}:${r.key}`;
    if (!historyMap[k]) historyMap[k] = [];
    historyMap[k].push(parseFloat(r.value));
  });

  const grid = document.getElementById('cardsGrid');
  if (!grid) return;
  grid.innerHTML = '';

  // Filter config sensors by current hive view
  const filteredCfg = configSensors.filter(s => {
    if (!currentHiveId) return true;
    return !s.hive_id || s.hive_id === currentHiveId;
  });

  const shownKeys = new Set();
  const cards = [];

  // Configured sensors first (with or without data)
  filteredCfg.forEach(sensor => {
    const keys = SENSOR_KEYS[sensor.type] || [];
    keys.forEach(key => {
      const mapKey = `${sensor.name}:${key}`;
      shownKeys.add(mapKey);
      const latest    = latestMap[mapKey] || null;
      const sparkVals = downsample(historyMap[mapKey] || []);
      const color     = hiveColorFor(sensor.hive_id);
      cards.push(buildCard(sensor, key, latest, sparkVals, color));
    });
  });

  // Any data rows not covered by config (sensor removed from config but still has data)
  latestRows.forEach(r => {
    const mapKey = `${r.sensor_name}:${r.key}`;
    if (shownKeys.has(mapKey)) return;
    const sparkVals = downsample(historyMap[mapKey] || []);
    const color     = hiveColorFor(r.hive_id);
    cards.push(buildCard({ name: r.sensor_name, type: null }, r.key, r, sparkVals, color));
  });

  if (cards.length === 0) {
    grid.innerHTML = `<div class="empty-state">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1"/></svg>
      <p>Noch keine Sensoren konfiguriert.</p>
      <p>Sensoren in den <a href="/config-ui">Einstellungen</a> konfigurieren.</p>
    </div>`;
    return;
  }

  cards.forEach(el => grid.appendChild(el));

  if (ts) {
    ts.classList.remove('refreshing');
    ts.textContent = new Date().toLocaleTimeString('de-AT');
  }

  updateCsvLink();
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
}

function clearCustomRange() {
  customFromTs = null;
  customToTs   = null;
}

// ── Chart Modal ───────────────────────────────────────────────────────────────
let _modalChart = null;
let _modalSensor = null;
let _modalKey = null;
let _modalUnit = '';
let _modalColor = '#f59e0b';
let _modalHours = 6;

async function openChartModal(sensorName, key, label, unit, color) {
  _modalSensor = sensorName;
  _modalKey    = key;
  _modalUnit   = unit || '';
  _modalColor  = color || '#f59e0b';

  const titleEl = document.getElementById('chartModalTitle');
  if (titleEl) titleEl.textContent = `${label || key} — ${sensorName}`;

  // Sync range buttons to current modal hours
  document.querySelectorAll('#chartModalRange .time-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.h) === _modalHours);
  });

  document.getElementById('chartModal')?.classList.add('open');
  await _renderModalChart();
}

function closeChartModal(e) {
  if (e && e.target !== document.getElementById('chartModal')) return;
  document.getElementById('chartModal')?.classList.remove('open');
  if (_modalChart) { _modalChart.destroy(); _modalChart = null; }
}

async function _renderModalChart() {
  let history = [];
  try {
    const p = new URLSearchParams({ sensor: _modalSensor, hours: _modalHours });
    if (currentHiveId) p.set('hive_id', currentHiveId);
    const r = await fetch('/api/data/history?' + p);
    history = await r.json();
  } catch {}

  const canvas = document.getElementById('chartModalCanvas');
  if (!canvas) return;

  const filtered = history.filter(r => r.sensor_name === _modalSensor && r.key === _modalKey);

  if (_modalChart) { _modalChart.destroy(); _modalChart = null; }

  if (filtered.length === 0) {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  const labels = filtered.map(r => fmtDate(r.timestamp));
  const data   = filtered.map(r => parseFloat(r.value));

  _modalChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: `${_modalSensor} · ${_modalKey}`,
        data,
        borderColor: _modalColor,
        backgroundColor: _modalColor.startsWith('#')
          ? _modalColor + '12'
          : 'rgba(245,158,11,0.07)',
        borderWidth: 1.8,
        pointRadius: filtered.length > 100 ? 0 : 2.5,
        pointBackgroundColor: _modalColor,
        tension: 0.35,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a1814',
          borderColor: 'rgba(255,255,255,0.12)',
          borderWidth: 1,
          titleColor: '#faf6ed',
          bodyColor: 'rgba(250,246,237,0.5)',
          callbacks: { label: ctx => `${ctx.parsed.y.toFixed(2)} ${_modalUnit}` },
        },
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 8, font: { size: 10.5 }, color: 'rgba(250,246,237,0.3)' },
          grid:  { color: 'rgba(255,255,255,0.05)' },
          border:{ color: 'rgba(255,255,255,0.07)' },
        },
        y: {
          ticks: { callback: v => `${v} ${_modalUnit}`, font: { size: 10.5 }, color: 'rgba(250,246,237,0.3)' },
          grid:  { color: 'rgba(255,255,255,0.05)' },
          border:{ color: 'rgba(255,255,255,0.07)' },
        },
      },
    },
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('#chartModalRange .time-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    _modalHours = parseInt(btn.dataset.h);
    document.querySelectorAll('#chartModalRange .time-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    await _renderModalChart();
  });
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeChartModal();
});

document.querySelectorAll('.time-btn').forEach(btn => {
  if (btn.closest('#chartModalRange')) return;   // skip modal range buttons
  btn.addEventListener('click', () => {
    if (btn.id === 'customRangeToggle') {
      document.getElementById('dateRangeRow')?.classList.toggle('hidden');
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
  setInterval(refreshData, 60000);
  setInterval(refreshStatus, 60000);
}

init();
