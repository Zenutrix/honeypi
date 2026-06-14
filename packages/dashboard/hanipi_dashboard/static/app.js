'use strict';

const COLORS = ['#f59e0b','#3b82f6','#10b981','#8b5cf6','#ef4444','#06b6d4','#f97316','#84cc16','#ec4899','#14b8a6'];

const UNITS = {
  temperature_c:      '°C',
  humidity_pct:       '%',
  pressure_hpa:       'hPa',
  weight_kg:          'kg',
  voltage_v:          'V',
  illuminance_lux:    'lx',
  gas_resistance_ohm: 'Ω',
};

const ICONS = {
  temperature_c:      '🌡',
  humidity_pct:       '💧',
  pressure_hpa:       '🌬',
  weight_kg:          '⚖',
  voltage_v:          '🔋',
  illuminance_lux:    '☀',
  gas_resistance_ohm: '💨',
};

let chartInst = null;
let currentHours = 6;

function fmtValue(key, val) {
  const n = parseFloat(val);
  if (isNaN(n)) return val;
  if (key === 'weight_kg') return n.toFixed(3);
  if (key === 'pressure_hpa') return n.toFixed(1);
  if (key === 'gas_resistance_ohm') return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : n.toFixed(0);
  return n.toFixed(1);
}

function humanLabel(key) {
  const map = {
    temperature_c: 'Temperatur',
    humidity_pct: 'Feuchte',
    pressure_hpa: 'Luftdruck',
    weight_kg: 'Gewicht',
    voltage_v: 'Spannung',
    illuminance_lux: 'Helligkeit',
    gas_resistance_ohm: 'Gaswiederstand',
  };
  return map[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

async function loadStatus() {
  try {
    const s = await fetch('/api/status').then(r => r.json());
    const dot = document.getElementById('sdot');
    const txt = document.getElementById('stext');
    if (s.active) {
      dot.className = 'dot pulse';
      txt.textContent = 'Aktiv';
    } else {
      dot.className = 'dot red';
      txt.textContent = s.status || 'Gestoppt';
    }
  } catch { /* server unreachable */ }
}

async function loadLatest() {
  try {
    const data = await fetch('/api/data/latest').then(r => r.json());
    const box = document.getElementById('cards');
    const chartCard = document.getElementById('chart-card');
    box.innerHTML = '';

    if (!data.length) {
      box.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🍯</div>
          <h3>Noch keine Messwerte</h3>
          <p>Sensoren in den <a href="/config-ui">Einstellungen</a> hinzufügen und speichern.<br>
          Der Agent sammelt dann automatisch Daten.</p>
        </div>`;
      chartCard.style.display = 'none';
      return;
    }

    data.forEach(row => {
      const unit = UNITS[row.key] ?? '';
      const icon = ICONS[row.key] ?? '📊';
      const card = document.createElement('div');
      card.className = 'metric-card';
      card.innerHTML = `
        <div class="metric-icon">${icon}</div>
        <div class="metric-label">${humanLabel(row.key)}</div>
        <div class="metric-value">${fmtValue(row.key, row.value)}<span class="metric-unit">${unit}</span></div>
        <div class="metric-sensor">${row.sensor_name}</div>`;
      box.appendChild(card);
    });

    chartCard.style.display = '';
    document.getElementById('ts').textContent =
      'Aktualisiert ' + new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
  } catch (e) { console.error(e); }
}

async function loadChart(hours) {
  try {
    const data = await fetch(`/api/data/history?hours=${hours}`).then(r => r.json());
    if (chartInst) { chartInst.destroy(); chartInst = null; }
    if (!data.length) return;

    // Build datasets grouped by sensor/key
    const dsMap = {};
    const tsSet = new Set();
    data.forEach(r => {
      const dk = `${r.sensor_name} – ${humanLabel(r.key)}`;
      if (!dsMap[dk]) dsMap[dk] = {};
      dsMap[dk][r.timestamp] = r.value;
      tsSet.add(r.timestamp);
    });

    const tsList = [...tsSet].sort((a, b) => a - b);
    const labels = tsList.map(t => {
      const d = new Date(t * 1000);
      return hours <= 6
        ? d.toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'})
        : d.toLocaleDateString('de-DE', {weekday:'short', hour:'2-digit', minute:'2-digit'});
    });

    const datasets = Object.entries(dsMap).map(([label, pts], i) => ({
      label,
      data: tsList.map(t => pts[t] ?? null),
      spanGaps: true,
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: COLORS[i % COLORS.length] + '18',
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.35,
      fill: false,
    }));

    chartInst = new Chart(document.getElementById('chart'), {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 }, padding: 12 } },
          tooltip: {
            callbacks: {
              label: ctx => {
                if (ctx.parsed.y === null) return null;
                const rawKey = data.find(r =>
                  `${r.sensor_name} – ${humanLabel(r.key)}` === ctx.dataset.label
                )?.key ?? '';
                const unit = UNITS[rawKey] ?? '';
                return ` ${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(2)} ${unit}`;
              }
            }
          }
        },
        scales: {
          x: { ticks: { maxTicksLimit: 8, font: { size: 11 } }, grid: { display: false } },
          y: { ticks: { font: { size: 11 } }, grid: { color: '#ede9e3' } },
        },
      },
    });
  } catch (e) { console.error(e); }
}

function setRange(h, el) {
  currentHours = h;
  document.querySelectorAll('.btn-range').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  loadChart(h);
}

async function refresh() {
  await loadStatus();
  await loadLatest();
}

refresh();
loadChart(currentHours);
setInterval(refresh, 30_000);
setInterval(() => loadChart(currentHours), 5 * 60_000);
