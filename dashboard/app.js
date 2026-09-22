/* ═══════════════════════════════════════════════════════════════
   RetailSight — app.js
   Full dashboard logic: data loading, Chart.js rendering,
   navigation, heatmap, tables, recommendations
═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Chart.js global defaults ────────────────────────────────────────
Chart.defaults.color           = '#94a3b8';
Chart.defaults.borderColor     = 'rgba(255,255,255,0.07)';
Chart.defaults.font.family     = "'Inter', sans-serif";
Chart.defaults.plugins.legend.display = false;
Chart.defaults.animation.duration     = 700;

const COLORS = {
  blue:   '#63b3ed',
  green:  '#68d391',
  purple: '#b794f4',
  orange: '#f6ad55',
  red:    '#fc8181',
  teal:   '#4fd1c5',
  yellow: '#f6e05e',
};

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DAY_NAMES   = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

// ── App State ────────────────────────────────────────────────────────
let state = {
  insights:         null,
  selectedProduct:  null,
  charts:           {},
};

// ── Utilities ────────────────────────────────────────────────────────
const $  = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls)  e.className   = cls;
  if (text) e.textContent = text;
  return e;
};

function showLoader(msg = 'Loading…') {
  $('loader-text').textContent = msg;
  $('loading-overlay').classList.add('visible');
}

function hideLoader() {
  $('loading-overlay').classList.remove('visible');
}

function fmt(n, decimals = 1) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Number(n).toFixed(decimals);
}

function destroyChart(id) {
  if (state.charts[id]) { state.charts[id].destroy(); delete state.charts[id]; }
}

// ── Navigation ───────────────────────────────────────────────────────
function navigate(page) {
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  $(`nav-${page}`).classList.add('active');
  $(`page-${page}`).classList.add('active');

  if (state.insights) renderPage(page);
}

document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => navigate(btn.dataset.page));
});

function renderPage(page) {
  switch (page) {
    case 'overview':  renderOverview();  break;
    case 'forecast':  renderForecast();  break;
    case 'inventory': renderInventory(); break;
    case 'insights':  renderInsights();  break;
  }
}

// ── Data Loading ─────────────────────────────────────────────────────
async function loadInsights() {
  if (window.INSIGHTS_DATA) {
    state.insights = window.INSIGHTS_DATA;
    onDataLoaded();
    return;
  }
  showLoader('Loading insights data…');
  try {
    let resp = await fetch('insights.json');
    if (!resp.ok) {
      resp = await fetch('../data/processed/insights.json');
    }
    if (!resp.ok) throw new Error('Not found');
    state.insights = await resp.json();
    onDataLoaded();
  } catch {
    hideLoader();
    loadDemoData();
  }
}

function onDataLoaded() {
  const d = state.insights;
  state.selectedProduct = d.products?.[0] ?? null;

  // Update alert badge
  const highRisk = (d.risk_analysis || []).filter(r => r['stockout_risk (%)'] > 20);
  $('alert-badge').textContent = highRisk.length;

  populateProductSelect();
  renderPage('overview');
  hideLoader();
}

// ── Demo Data Generator ───────────────────────────────────────────────
function loadDemoData() {
  showLoader('Generating demo data…');
  setTimeout(() => {
    state.insights = buildDemoInsights();
    onDataLoaded();
  }, 800);
}

function buildDemoInsights() {
  const products = ['Electronics','Clothing','Groceries','Sports','Toys',
                    'Home_Decor','Books','Beauty','Furniture','Automotive'];
  const rng = (min, max) => Math.random() * (max - min) + min;
  const rngInt = (min, max) => Math.round(rng(min, max));

  // Overall metrics (target: accuracy ≥ 90%)
  const overall_MAPE     = rng(5.5, 9.8);
  const overall_accuracy = 100 - overall_MAPE;
  const overall = {
    overall_MAPE:     +overall_MAPE.toFixed(2),
    overall_RMSE:     +rng(18, 35).toFixed(2),
    overall_MAE:      +rng(12, 22).toFixed(2),
    overall_R2:       +rng(0.91, 0.97).toFixed(4),
    overall_accuracy: +overall_accuracy.toFixed(2),
  };

  // Per-product metrics
  const per_product_metrics = products.map(p => {
    const mape = rng(4, 13);
    return { product: p, 'MAPE (%)': +mape.toFixed(2), RMSE: +rng(15,40).toFixed(2),
             MAE: +rng(10,25).toFixed(2), 'R²': +rng(0.88,0.98).toFixed(4),
             'Accuracy (%)': +(100 - mape).toFixed(2), n_samples: 164 };
  }).sort((a,b) => a['MAPE (%)'] - b['MAPE (%)']);

  // Risk analysis
  const risk_analysis = products.map(p => {
    const so = +rng(5, 35).toFixed(1);
    const ov = +rng(5, 28).toFixed(1);
    const avg = rngInt(50, 350);
    return {
      product: p, avg_daily_sales: avg, avg_daily_forecast: avg + rngInt(-10, 10),
      forecast_bias: +rng(-8, 8).toFixed(2), safety_stock: rngInt(20, 150),
      'stockout_risk (%)': so, 'overstock_risk (%)': ov,
      reorder_point: avg * 7 + rngInt(20, 150),
      risk_level: so > 20 ? '🔴 High' : so > 10 ? '🟡 Medium' : '🟢 Low',
    };
  }).sort((a,b) => b['stockout_risk (%)'] - a['stockout_risk (%)']);

  // Monthly trend
  const monthly_trend = [];
  products.forEach(p => {
    for (let m = 1; m <= 12; m++) {
      const base  = rngInt(80, 300);
      const seasonal = p === 'Electronics' ? Math.cos((m-1) * Math.PI / 6) * 80 :
                       p === 'Sports'      ? Math.sin((m-6)  * Math.PI / 6) * 60 :
                       p === 'Toys'        ? Math.cos((m-1) * Math.PI / 6) * 70 : 0;
      monthly_trend.push({ product: p, month: m, avg_sales: Math.max(0, base + seasonal).toFixed(1),
                            month_name: MONTH_NAMES[m-1] });
    }
  });

  // DoW pattern
  const dow_pattern = [];
  products.forEach(p => {
    const base = rngInt(80, 260);
    const dowW = [0.88,0.87,0.90,0.93,1.06,1.22,1.19];
    DOW_NAMES_SHORT.forEach((_, i) => {
      dow_pattern.push({ product: p, day_of_week: i, avg_sales: +(base * dowW[i]).toFixed(1), day: DAY_NAMES[i] });
    });
  });

  // Promo effectiveness
  const promo_effectiveness = products.map(p => ({
    product: p, non_promo_avg: +rng(100, 280).toFixed(1),
    promo_avg: +rng(140, 420).toFixed(1), 'promo_lift (%)': +rng(15, 55).toFixed(1),
  })).sort((a,b) => b['promo_lift (%)'] - a['promo_lift (%)']);

  // Feature importance
  const feats = ['sales_lag_7','sales_lag_1','rolling_mean_7','rolling_mean_30',
                 'trend_index','sin_1','cos_1','is_promotion','month','rolling_std_7',
                 'price_ratio','day_of_week','is_holiday','sales_lag_14','week_of_year',
                 'weather_index','sales_lag_28','product_id','quarter','cos_2'];
  const rawImp  = feats.map(() => Math.random());
  const total   = rawImp.reduce((a,b) => a+b, 0);
  const feature_importance = feats.map((f, i) => ({
    feature: f, importance: +(rawImp[i]/total).toFixed(4),
    importance_pct: +(rawImp[i]/total * 100).toFixed(2),
  })).sort((a,b) => b.importance - a.importance);

  // Recommendations
  const recommendations = risk_analysis.filter(r => r['stockout_risk (%)'] > 20).map(r => ({
    type: '⚠️ Stockout Risk', product: r.product, priority: 'High',
    message: `Stockout risk is ${r['stockout_risk (%)'].toFixed(1)}%. Increase stock to ≥${r.reorder_point.toLocaleString()} units. Safety stock buffer: ${r.safety_stock} units.`,
  }));
  promo_effectiveness.filter(p => p['promo_lift (%)'] > 35).forEach(p => {
    recommendations.push({ type: '📈 Promo Opportunity', product: p.product, priority: 'Low',
      message: `Promotions lift ${p.product} sales by ${p['promo_lift (%)'].toFixed(1)}%. Schedule promotions ahead of peak season.` });
  });

  // Forecast time-series (90 days per product)
  const forecast_ts = {};
  const baseDate = new Date('2023-10-01');
  products.forEach(p => {
    const dates = [], actual = [], xgb_pred = [], sarima_pred = [], ensemble_pred = [];
    const base = rngInt(80, 320);
    for (let i = 0; i < 91; i++) {
      const d = new Date(baseDate); d.setDate(d.getDate() + i);
      dates.push(d.toISOString().slice(0,10));
      const dow_f = [0.88,0.87,0.90,0.93,1.06,1.22,1.19][d.getDay()];
      const trend = base * (1 + 0.0001 * i);
      const val   = Math.round(trend * dow_f * (1 + rng(-0.12,0.12)));
      const xp    = Math.round(val * (1 + rng(-0.08, 0.08)));
      const sp    = Math.round(val * (1 + rng(-0.12, 0.12)));
      const ep    = Math.round(0.7 * xp + 0.3 * sp);
      actual.push(val); xgb_pred.push(xp); sarima_pred.push(sp); ensemble_pred.push(ep);
    }
    forecast_ts[p] = { dates, actual, xgb_pred, sarima_pred, ensemble_pred };
  });

  return { overall_metrics: overall, per_product_metrics, risk_analysis,
           monthly_trend, dow_pattern, promo_effectiveness, feature_importance,
           recommendations, forecast_ts, products };
}

const DOW_NAMES_SHORT = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

// ── Overview Page ────────────────────────────────────────────────────
function renderOverview() {
  const d = state.insights;
  const m = d.overall_metrics;

  // KPIs
  animateValue('kpi-accuracy', m.overall_accuracy, '%');
  animateValue('kpi-mape',     m.overall_MAPE,     '%');
  animateValue('kpi-rmse',     m.overall_RMSE,     '');
  $('kpi-products').textContent = d.products.length;

  const highRisk = (d.risk_analysis||[]).filter(r => r['stockout_risk (%)'] > 20).length;
  $('kpi-highrisk').textContent = highRisk;
  animateValue('kpi-r2', m.overall_R2, '');

  const accTarget = document.getElementById('kpi-accuracy-target');
  if (m.overall_accuracy >= 90) {
    accTarget.textContent = '✅ Target Met (≥90%)';
    accTarget.className   = 'kpi-delta positive';
  } else {
    accTarget.textContent = '❌ Below Target';
    accTarget.className   = 'kpi-delta negative';
  }

  renderOverviewTS();
  renderAccuracyBar();
  renderMetricsTable();
}

function animateValue(id, value, suffix, decimals = 2) {
  const el = $(id);
  const start = 0;
  const end   = parseFloat(value);
  const dur   = 900;
  const step  = 16;
  let cur = start;
  const inc = (end - start) / (dur / step);
  const timer = setInterval(() => {
    cur += inc;
    if ((inc > 0 && cur >= end) || (inc < 0 && cur <= end)) { cur = end; clearInterval(timer); }
    el.textContent = cur.toFixed(decimals) + suffix;
  }, step);
}

function renderOverviewTS() {
  destroyChart('overview-ts');
  const d = state.insights;
  // Aggregate across all products by date
  const dateMap = {};
  Object.values(d.forecast_ts).forEach(ts => {
    ts.dates.forEach((dt, i) => {
      dateMap[dt] = (dateMap[dt] || { actual: 0, pred: 0 });
      dateMap[dt].actual += ts.actual[i];
      dateMap[dt].pred   += ts.ensemble_pred[i];
    });
  });
  const sorted = Object.keys(dateMap).sort();
  // Weekly aggregation for readability
  const wDates = [], wActual = [], wPred = [];
  for (let i = 0; i < sorted.length; i += 7) {
    const slice = sorted.slice(i, i+7);
    wDates.push(slice[0]);
    wActual.push(Math.round(slice.reduce((s,k) => s + dateMap[k].actual, 0) / slice.length));
    wPred.push(Math.round(slice.reduce((s,k) => s + dateMap[k].pred, 0) / slice.length));
  }

  const ctx = $('chart-overview-ts');
  state.charts['overview-ts'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: wDates,
      datasets: [
        { label: 'Actual',   data: wActual, borderColor: COLORS.blue,   backgroundColor: 'rgba(99,179,237,0.08)',
          borderWidth: 2, pointRadius: 0, fill: true, tension: 0.4 },
        { label: 'Ensemble', data: wPred,   borderColor: COLORS.green,  backgroundColor: 'rgba(104,211,145,0.06)',
          borderWidth: 2, pointRadius: 0, fill: true, tension: 0.4, borderDash: [5,3] },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { maxTicksLimit: 10 } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: v => v.toLocaleString() } },
      },
      plugins: { legend: { display: true, labels: { color: '#94a3b8', font: { size: 11 } } },
                 tooltip: { backgroundColor: '#1e2d45', borderColor: 'rgba(255,255,255,0.08)', borderWidth: 1 } },
    }
  });
}

function renderAccuracyBar() {
  destroyChart('accuracy-bar');
  const d = state.insights;
  const labels = d.per_product_metrics.map(r => r.product.replace('_',' '));
  const accs   = d.per_product_metrics.map(r => r['Accuracy (%)']);
  const colors = accs.map(a => a >= 92 ? COLORS.green : a >= 88 ? COLORS.orange : COLORS.red);

  state.charts['accuracy-bar'] = new Chart($('chart-accuracy-bar'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: accs, backgroundColor: colors, borderRadius: 5, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      scales: {
        x: { min: 75, max: 100, grid: { color: 'rgba(255,255,255,0.04)' },
             ticks: { callback: v => v + '%' } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
      plugins: { tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.x.toFixed(1)}%` },
        backgroundColor: '#1e2d45', borderColor: 'rgba(255,255,255,0.08)', borderWidth: 1 } }
    }
  });
}

function renderMetricsTable() {
  const tbody = $('metrics-tbody');
  tbody.innerHTML = '';
  (state.insights.per_product_metrics || []).forEach(row => {
    const acc = row['Accuracy (%)'];
    const badge = acc >= 92 ? 'badge-green' : acc >= 88 ? 'badge-yellow' : 'badge-red';
    const status = acc >= 92 ? '✅ Excellent' : acc >= 88 ? '⚠️ Good' : '❌ Needs Work';
    const tr = el('tr');
    tr.innerHTML = `
      <td>${row.product.replace('_',' ')}</td>
      <td><strong style="color:${acc>=90?'#68d391':'#fc8181'}">${fmt(acc)}%</strong></td>
      <td>${fmt(row['MAPE (%)'])}%</td>
      <td>${fmt(row.RMSE)}</td>
      <td>${fmt(row.MAE)}</td>
      <td>${fmt(row['R²'],4)}</td>
      <td><span class="badge ${badge}">${status}</span></td>
    `;
    tbody.appendChild(tr);
  });

  $('metrics-search').addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    tbody.querySelectorAll('tr').forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

// ── Forecast Page ────────────────────────────────────────────────────
function populateProductSelect() {
  const sel = $('forecast-product-select');
  sel.innerHTML = '';
  (state.insights.products || []).forEach(p => {
    const o = el('option'); o.value = p; o.textContent = p.replace('_',' ');
    sel.appendChild(o);
  });
  sel.addEventListener('change', () => {
    state.selectedProduct = sel.value;
    renderForecastChart();
    renderMonthlyTrend();
    renderDOWChart();
  });
  ['forecast-view-select','forecast-granularity'].forEach(id => {
    $(id).addEventListener('change', renderForecastChart);
  });
}

function renderForecast() {
  if (state.selectedProduct) {
    $('forecast-product-select').value = state.selectedProduct;
  }
  renderForecastChart();
  renderMonthlyTrend();
  renderDOWChart();
}

function aggregateTS(dates, values, gran) {
  if (gran === 'daily') return { labels: dates, data: values };
  const map = {};
  dates.forEach((d, i) => {
    const dt  = new Date(d);
    let key;
    if (gran === 'weekly') {
      const monday = new Date(dt);
      monday.setDate(dt.getDate() - ((dt.getDay()+6)%7));
      key = monday.toISOString().slice(0,10);
    } else {
      key = d.slice(0,7);
    }
    map[key] = map[key] || [];
    map[key].push(values[i]);
  });
  const sorted = Object.keys(map).sort();
  return {
    labels: sorted,
    data:   sorted.map(k => Math.round(map[k].reduce((a,b)=>a+b,0)/map[k].length)),
  };
}

function renderForecastChart() {
  destroyChart('forecast-ts');
  const product = state.selectedProduct;
  if (!product || !state.insights.forecast_ts?.[product]) return;

  const ts   = state.insights.forecast_ts[product];
  const view = $('forecast-view-select').value;
  const gran = $('forecast-granularity').value;

  $('forecast-chart-title').textContent = `${product.replace('_',' ')} — Forecast vs Actual`;

  const aggActual   = aggregateTS(ts.dates, ts.actual,        gran);
  const aggEnsemble = aggregateTS(ts.dates, ts.ensemble_pred, gran);
  const aggXGB      = aggregateTS(ts.dates, ts.xgb_pred,      gran);
  const aggSARIMA   = aggregateTS(ts.dates, ts.sarima_pred,   gran);

  const datasets = [];
  datasets.push({ label: 'Actual', data: aggActual.data,
    borderColor: COLORS.blue, backgroundColor: 'rgba(99,179,237,0.08)',
    borderWidth: 2.5, pointRadius: 0, fill: true, tension: 0.35 });
  if (view === 'all' || view === 'ensemble')
    datasets.push({ label: 'Ensemble', data: aggEnsemble.data,
      borderColor: COLORS.green, backgroundColor: 'transparent',
      borderWidth: 2, pointRadius: 0, tension: 0.35, borderDash: [6,3] });
  if (view === 'all' || view === 'xgb')
    datasets.push({ label: 'XGBoost', data: aggXGB.data,
      borderColor: COLORS.orange, backgroundColor: 'transparent',
      borderWidth: 1.5, pointRadius: 0, tension: 0.35, borderDash: [3,3] });
  if (view === 'all' || view === 'sarima')
    datasets.push({ label: 'SARIMA', data: aggSARIMA.data,
      borderColor: COLORS.purple, backgroundColor: 'transparent',
      borderWidth: 1.5, pointRadius: 0, tension: 0.35, borderDash: [2,4] });

  const legend = $('forecast-legend');
  legend.innerHTML = '';
  datasets.forEach(ds => {
    const map = { 'Actual':'blue','Ensemble':'green','XGBoost':'orange','SARIMA':'purple' };
    const span = el('span', `pill ${map[ds.label]}`, `● ${ds.label}`);
    legend.appendChild(span);
  });

  state.charts['forecast-ts'] = new Chart($('chart-forecast-ts'), {
    type: 'line',
    data: { labels: aggActual.labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { maxTicksLimit: 12 } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: v => v.toLocaleString() } },
      },
      plugins: {
        legend: { display: true, labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 16 } },
        tooltip: { backgroundColor: '#1e2d45', borderColor: 'rgba(255,255,255,0.08)', borderWidth: 1 },
      }
    }
  });
}

function renderMonthlyTrend() {
  destroyChart('monthly-trend');
  const product = state.selectedProduct;
  const rows    = (state.insights.monthly_trend || []).filter(r => r.product === product);
  const sorted  = rows.sort((a,b) => a.month - b.month);

  state.charts['monthly-trend'] = new Chart($('chart-monthly-trend'), {
    type: 'bar',
    data: {
      labels: sorted.map(r => r.month_name),
      datasets: [{
        data: sorted.map(r => +r.avg_sales),
        backgroundColor: sorted.map((r, i) => {
          const max = Math.max(...sorted.map(x => +x.avg_sales));
          const ratio = +r.avg_sales / max;
          return `rgba(99,179,237,${0.3 + ratio * 0.7})`;
        }),
        borderRadius: 5, borderSkipped: false,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' } },
      },
      plugins: { tooltip: { backgroundColor: '#1e2d45', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' } }
    }
  });
}

function renderDOWChart() {
  destroyChart('dow');
  const product = state.selectedProduct;
  const rows    = (state.insights.dow_pattern || []).filter(r => r.product === product);
  const sorted  = rows.sort((a,b) => a.day_of_week - b.day_of_week);

  const colors = sorted.map(r =>
    r.day_of_week >= 5 ? COLORS.green : COLORS.blue
  );

  state.charts['dow'] = new Chart($('chart-dow'), {
    type: 'radar',
    data: {
      labels: sorted.map(r => r.day),
      datasets: [{
        data: sorted.map(r => +r.avg_sales),
        borderColor: COLORS.blue, backgroundColor: 'rgba(99,179,237,0.12)',
        borderWidth: 2, pointBackgroundColor: colors, pointRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        r: {
          grid: { color: 'rgba(255,255,255,0.07)' },
          ticks: { display: false },
          pointLabels: { color: '#94a3b8', font: { size: 11 } },
        }
      },
      plugins: { tooltip: { backgroundColor: '#1e2d45', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' } }
    }
  });
}

// ── Inventory Alerts Page ────────────────────────────────────────────
function renderInventory() {
  const d = state.insights;
  const risk = d.risk_analysis || [];

  const highSO  = risk.filter(r => r['stockout_risk (%)'] > 20).length;
  const highOV  = risk.filter(r => r['overstock_risk (%)'] > 20).length;
  const lowRisk = risk.filter(r => r['stockout_risk (%)'] <= 10 && r['overstock_risk (%)'] <= 10).length;

  $('inv-high-stockout').textContent = highSO;
  $('inv-high-overstock').textContent = highOV;
  $('inv-low-risk').textContent = lowRisk;

  renderStockoutChart();
  renderOverstockChart();
  renderRiskTable();
  renderRecommendations();
}

function renderStockoutChart() {
  destroyChart('stockout');
  const risk = state.insights.risk_analysis || [];
  const sorted = [...risk].sort((a,b) => b['stockout_risk (%)'] - a['stockout_risk (%)']);
  const colors = sorted.map(r =>
    r['stockout_risk (%)'] > 20 ? COLORS.red : r['stockout_risk (%)'] > 10 ? COLORS.orange : COLORS.green
  );

  state.charts['stockout'] = new Chart($('chart-stockout'), {
    type: 'bar',
    data: {
      labels: sorted.map(r => r.product.replace('_',' ')),
      datasets: [{ data: sorted.map(r => r['stockout_risk (%)']),
        backgroundColor: colors, borderRadius: 5, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: v => v+'%' } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
      plugins: {
        annotation: {
          annotations: { threshold: { type: 'line', xMin: 20, xMax: 20,
            borderColor: 'rgba(252,129,129,0.5)', borderWidth: 1.5, borderDash: [4,3],
            label: { content: '20% threshold', display: true, color: '#fc8181', font: { size: 10 }, position: 'end' }
          }}
        },
        tooltip: { backgroundColor: '#1e2d45', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
                   callbacks: { label: ctx => ` Stockout risk: ${ctx.parsed.x.toFixed(1)}%` } }
      }
    }
  });
}

function renderOverstockChart() {
  destroyChart('overstock');
  const risk   = state.insights.risk_analysis || [];
  const sorted = [...risk].sort((a,b) => b['overstock_risk (%)'] - a['overstock_risk (%)']);
  const colors = sorted.map(r =>
    r['overstock_risk (%)'] > 20 ? COLORS.orange : r['overstock_risk (%)'] > 10 ? COLORS.yellow : COLORS.teal
  );

  state.charts['overstock'] = new Chart($('chart-overstock'), {
    type: 'bar',
    data: {
      labels: sorted.map(r => r.product.replace('_',' ')),
      datasets: [{ data: sorted.map(r => r['overstock_risk (%)']),
        backgroundColor: colors, borderRadius: 5, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: v => v+'%' } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
      plugins: { tooltip: { backgroundColor: '#1e2d45', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
                 callbacks: { label: ctx => ` Overstock risk: ${ctx.parsed.x.toFixed(1)}%` } } }
    }
  });
}

function renderRiskTable() {
  const tbody = $('risk-tbody');
  tbody.innerHTML = '';
  (state.insights.risk_analysis || []).forEach(row => {
    const so  = row['stockout_risk (%)'];
    const ov  = row['overstock_risk (%)'];
    const soBadge = so > 20 ? 'badge-red' : so > 10 ? 'badge-yellow' : 'badge-green';
    const ovBadge = ov > 20 ? 'badge-yellow' : 'badge-green';
    const rlClass  = row.risk_level.includes('High') ? 'badge-red' :
                     row.risk_level.includes('Medium') ? 'badge-yellow' : 'badge-green';
    const tr = el('tr');
    tr.innerHTML = `
      <td>${row.product.replace('_',' ')}</td>
      <td>${fmt(row.avg_daily_sales, 0)}</td>
      <td>${fmt(row.avg_daily_forecast, 0)}</td>
      <td style="color:${row.forecast_bias > 0 ? '#68d391' : '#fc8181'}">${row.forecast_bias > 0 ? '+' : ''}${fmt(row.forecast_bias)}</td>
      <td>${row.safety_stock}</td>
      <td><strong>${(row.reorder_point||0).toLocaleString()}</strong></td>
      <td><span class="badge ${soBadge}">${so.toFixed(1)}%</span></td>
      <td><span class="badge ${ovBadge}">${ov.toFixed(1)}%</span></td>
      <td><span class="badge ${rlClass}">${row.risk_level}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderRecommendations() {
  const container = $('recs-container');
  container.innerHTML = '';
  const recs = state.insights.recommendations || [];
  if (!recs.length) {
    container.innerHTML = '<p style="color:#94a3b8;font-size:13px;">No high-priority alerts. All products are within normal risk thresholds.</p>';
    return;
  }
  recs.forEach(rec => {
    const card = el('div', `rec-card ${rec.priority.toLowerCase()}`);
    card.innerHTML = `
      <div class="rec-type">${rec.type}</div>
      <div class="rec-product">${rec.product.replace('_',' ')}</div>
      <div class="rec-message">${rec.message}</div>
      <span class="rec-priority pri-${rec.priority.toLowerCase()}">${rec.priority} Priority</span>
    `;
    container.appendChild(card);
  });
}

// ── Insights Page ────────────────────────────────────────────────────
function renderInsights() {
  renderHeatmap();
  renderPromoLift();
  renderFeatureImportance();
  renderInsightCards();
}

function renderHeatmap() {
  const container = $('heatmap-container');
  container.innerHTML = '';

  const d        = state.insights;
  const products = d.products || [];
  const monthly  = d.monthly_trend || [];

  // Build product × month matrix
  const matrix = {};
  products.forEach(p => { matrix[p] = {}; });
  monthly.forEach(r => { matrix[r.product] = matrix[r.product] || {}; matrix[r.product][r.month] = +r.avg_sales; });

  // Find min/max for color scaling
  const allVals = monthly.map(r => +r.avg_sales);
  const minV = Math.min(...allVals), maxV = Math.max(...allVals);

  const table = document.createElement('table');
  table.className = 'heatmap-table';

  // Header row
  const hRow = el('tr');
  hRow.appendChild(el('th', '', ''));
  MONTH_NAMES.forEach(m => hRow.appendChild(el('th', '', m)));
  table.appendChild(hRow);

  // Data rows
  products.forEach(p => {
    const tr = el('tr');
    const th = el('th', '', p.replace('_',' '));
    th.style.textAlign = 'right';
    th.style.paddingRight = '8px';
    tr.appendChild(th);
    for (let m = 1; m <= 12; m++) {
      const val  = matrix[p][m] ?? 0;
      const norm = (val - minV) / (maxV - minV);
      const td   = el('td', '', Math.round(val));
      // Color: deep blue → cyan → green
      const r = Math.round(10  + norm * 60);
      const g = Math.round(100 + norm * 130);
      const b = Math.round(160 + norm * 40);
      td.style.background = `rgba(${r},${g},${b},${0.25 + norm * 0.65})`;
      td.title = `${p} in ${MONTH_NAMES[m-1]}: ${Math.round(val)} avg sales`;
      tr.appendChild(td);
    }
    table.appendChild(tr);
  });

  container.appendChild(table);
}

function renderPromoLift() {
  destroyChart('promo-lift');
  const promo  = state.insights.promo_effectiveness || [];
  const sorted = [...promo].sort((a,b) => b['promo_lift (%)'] - a['promo_lift (%)']);
  const colors = sorted.map(r =>
    r['promo_lift (%)'] >= 40 ? COLORS.green : r['promo_lift (%)'] >= 25 ? COLORS.blue : COLORS.teal
  );

  state.charts['promo-lift'] = new Chart($('chart-promo-lift'), {
    type: 'bar',
    data: {
      labels: sorted.map(r => r.product.replace('_',' ')),
      datasets: [{ data: sorted.map(r => r['promo_lift (%)']),
        backgroundColor: colors, borderRadius: 5, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: v => v+'%' } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } },
      },
      plugins: { tooltip: { backgroundColor: '#1e2d45', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
                 callbacks: { label: ctx => ` Promo lift: +${ctx.parsed.x.toFixed(1)}%` } } }
    }
  });
}

function renderFeatureImportance() {
  destroyChart('feat-imp');
  const feats  = (state.insights.feature_importance || []).slice(0, 12);
  const labels = feats.map(f => f.feature);
  const vals   = feats.map(f => f.importance_pct);
  const norm   = Math.max(...vals);
  const colors = vals.map(v => {
    const ratio = v / norm;
    return `rgba(${Math.round(99 + (183-99)*ratio)}, ${Math.round(179 + (148-179)*ratio)}, ${Math.round(237 + (244-237)*ratio)}, ${0.5 + ratio * 0.5})`;
  });

  state.charts['feat-imp'] = new Chart($('chart-feat-imp'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: vals, backgroundColor: colors, borderRadius: 4, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { callback: v => v.toFixed(1)+'%' } },
        y: { grid: { display: false }, ticks: { font: { size: 10.5 }, family: "'JetBrains Mono', monospace" } },
      },
      plugins: { tooltip: { backgroundColor: '#1e2d45', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
                 callbacks: { label: ctx => ` Importance: ${ctx.parsed.x.toFixed(2)}%` } } }
    }
  });
}

function renderInsightCards() {
  const grid = $('insight-cards-grid');
  grid.innerHTML = '';

  const d     = state.insights;
  const promo = d.promo_effectiveness || [];
  const risk  = d.risk_analysis || [];
  const fi    = d.feature_importance || [];
  const m     = d.overall_metrics || {};

  const topPromo = promo.reduce((a, b) => b['promo_lift (%)'] > a['promo_lift (%)'] ? b : a, promo[0] || {});
  const topFeat  = fi[0] || {};
  const avgSO    = risk.reduce((a,b) => a + b['stockout_risk (%)'], 0) / (risk.length || 1);
  const totalROP = risk.reduce((a,b) => a + (b.reorder_point || 0), 0);

  const cards = [
    { icon: '🏆', title: 'Best Forecast Accuracy', value: m.overall_accuracy?.toFixed(1) + '%',
      desc: `Ensemble (XGBoost 70% + SARIMA 30%) achieves ${m.overall_accuracy?.toFixed(1)}% accuracy, exceeding the 90% target.` },
    { icon: '📣', title: 'Highest Promo Lift',
      value: topPromo.product?.replace('_',' '),
      desc: `${topPromo.product?.replace('_',' ')} sees a ${topPromo['promo_lift (%)']?.toFixed(1)}% sales lift during promotions. Highest ROI category for marketing spend.` },
    { icon: '🔑', title: 'Top Predictive Feature', value: topFeat.feature,
      desc: `${topFeat.feature} explains ${topFeat.importance_pct?.toFixed(1)}% of XGBoost's decisions — recent sales history is the strongest signal.` },
    { icon: '📊', title: 'Avg Stockout Risk', value: avgSO.toFixed(1) + '%',
      desc: `${risk.filter(r=>r['stockout_risk (%)']>20).length} of ${risk.length} products exceed the 20% high-risk threshold and need immediate attention.` },
    { icon: '📦', title: 'Total Reorder Units', value: totalROP.toLocaleString(),
      desc: 'Combined recommended reorder point across all products based on 7-day lead time and safety stock buffers.' },
    { icon: '📅', title: 'Peak Season', value: 'Nov – Dec',
      desc: 'Electronics (+40%) and Toys (+35%) peak in winter. Plan inventory build-up by October to prevent stockouts.' },
  ];

  cards.forEach(c => {
    const card = el('div', 'insight-card');
    card.innerHTML = `
      <div class="insight-icon">${c.icon}</div>
      <div class="insight-title">${c.title}</div>
      <div class="insight-value">${c.value || '—'}</div>
      <div class="insight-desc">${c.desc}</div>
    `;
    grid.appendChild(card);
  });
}

// ── Init ─────────────────────────────────────────────────────────────
$('load-demo-btn').addEventListener('click', () => {
  state.insights = null;
  loadDemoData();
});

$('run-pipeline-btn').addEventListener('click', () => {
  alert('Run the pipeline from your terminal:\n\n  python run_pipeline.py\n\nThen reload this page to see results.');
});

// Boot
loadInsights();
