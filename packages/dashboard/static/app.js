const COLORS = ['#f5a623','#4a90d9','#7ed321','#9b59b6','#e74c3c','#1abc9c'];

async function loadLatest() {
  const data = await fetch('/api/data/latest').then(r => r.json());
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  data.forEach(row => {
    const div = document.createElement('div');
    div.className = 'card';
    const val = parseFloat(row.value).toFixed(2);
    div.innerHTML = `
      <div class="label">${row.key.replace(/_/g,' ')}</div>
      <div class="value">${val}</div>
      <div class="sensor">${row.sensor_name}</div>
    `;
    cards.appendChild(div);
  });
}

async function loadChart() {
  const data = await fetch('/api/data/history?hours=24').then(r => r.json());
  const byKey = {};
  data.forEach(row => {
    const k = `${row.sensor_name}/${row.key}`;
    if (!byKey[k]) byKey[k] = { labels: [], values: [] };
    byKey[k].labels.push(new Date(row.timestamp * 1000).toLocaleTimeString());
    byKey[k].values.push(row.value);
  });

  const keys = Object.keys(byKey);
  new Chart(document.getElementById('chart'), {
    type: 'line',
    data: {
      labels: byKey[keys[0]]?.labels ?? [],
      datasets: keys.map((k, i) => ({
        label: k.replace('/', ' – '),
        data: byKey[k].values,
        borderColor: COLORS[i % COLORS.length],
        tension: 0.3,
        pointRadius: 0,
      })),
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom' } },
      scales: { y: { beginAtZero: false } },
    },
  });
}

loadLatest();
loadChart();
setInterval(loadLatest, 30000);
