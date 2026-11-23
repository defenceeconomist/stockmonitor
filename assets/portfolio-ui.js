/* Portfolio views consume only the saved snapshot and the current Codex briefing. */
'use strict';
let portfolioWeight = 'spend';
const pp = value => `${value >= 0 ? '+' : ''}${value.toFixed(2)} pp`;
function initPortfolio() {
  for (const [id, weight] of [['weight-spend', 'spend'], ['weight-equal', 'equal']]) {
    $(id).addEventListener('click', () => {
      portfolioWeight = weight;
      for (const [button, key] of [['weight-spend', 'spend'], ['weight-equal', 'equal']]) {
        $(button).classList.toggle('active', weight === key);
        $(button).setAttribute('aria-pressed', String(weight === key));
      }
      renderPortfolio();
    });
  }
  $('portfolio-benchmark').addEventListener('change', renderPortfolio);
  $('portfolio-period').addEventListener('change', renderPortfolio);
  renderPortfolio();
}
function renderPortfolio() {
  try {
    const result = Portfolio.calculate(dataset, {weighting: portfolioWeight,
      benchmark: $('portfolio-benchmark').value, period: $('portfolio-period').value});
    const weightLabel = portfolioWeight === 'spend' ? 'MOD spending weights' : 'Equal weights';
    $('portfolio-content').hidden = false;
    $('portfolio-error').hidden = !result.warnings.length;
    $('portfolio-error').textContent = result.warnings.join(' · ');
    $('portfolio-return-label').textContent = 'Supplier basket · ' + (portfolioWeight === 'spend' ? 'spending' : 'equal');
    for (const [id, value, format] of [
      ['portfolio-return', result.return_pct, pct], ['portfolio-benchmark-return', result.benchmark_return_pct, pct],
      ['portfolio-excess', result.excess_pp, pp], ['portfolio-fx', result.fx_contribution_pp, pp]
    ]) {$(id).textContent = format(value); $(id).className = direction(value);}
    $('portfolio-benchmark-label').textContent = result.benchmark.label + ' tracker';
    $('portfolio-proxy').textContent = result.benchmark.ticker + ' · accumulating ETF proxy';
    $('portfolio-alternative').textContent = `${portfolioWeight === 'spend' ? 'Equal' : 'Spending'} weights: ${pct(result.alternative_return_pct)}`;
    $('portfolio-local').textContent = 'Local share contribution: ' + pp(result.local_return_pct);
    $('portfolio-dates').textContent = `${pretty(result.start)} – ${pretty(result.end)} · same window for every curve · buy and hold from starting weights`;
    $('portfolio-chart-note').textContent = `Start = 100 · ${weightLabel} in green · alternate weighting dashed · ${result.benchmark.index} tracker in blue`;
    $('portfolio-coverage').textContent = `${result.coverage.quoted} of ${result.coverage.total} suppliers included, representing ${result.coverage.spend_pct.toFixed(1)}% of top-50 MOD payments. ${result.coverage.total - result.coverage.quoted} firms without a direct quote are excluded; quoted weights are normalised to 100%. The full 50 remain in the treemap.`;
    $('portfolio-benchmark-source').innerHTML = `Benchmark proxy: <a href="${esc(result.benchmark.source_url)}" target="_blank" rel="noopener noreferrer">${esc(result.benchmark.fund)}</a> (${esc(result.benchmark.ticker)}). Fund fees and tracking differences are included. FX and prices: Yahoo Finance · portfolio feeds fetched ${pretty(dataset.portfolio_market.fetched_at)}.`;
    $('portfolio-breadth').innerHTML = `<span><strong class="up">${result.breadth.up} rising</strong> / <strong class="down">${result.breadth.down} falling</strong>${result.breadth.flat ? ` / ${result.breadth.flat} unchanged` : ''} in GBP</span><span>Largest two starting weights: <strong>${result.largest_two_weight_pct.toFixed(1)}%</strong></span><span>Top five: ${result.top_five_gross_share_pct.toFixed(1)}% of absolute company contributions</span>`;
    renderPortfolioCharts(result, weightLabel);
    renderPortfolioTable(result);
    renderPortfolioDrivers(result);
  } catch (error) {
    $('portfolio-content').hidden = true;
    $('portfolio-error').hidden = false;
    $('portfolio-error').textContent = 'Portfolio comparison unavailable. ' + error.message;
  }
}
function renderPortfolioCharts(result, weightLabel) {
  const alternate = portfolioWeight === 'spend' ? 'equal' : 'spend';
  const traces = [
    {key: portfolioWeight, name: weightLabel, color: '#087e75', width: 2.7},
    {key: alternate, name: alternate === 'equal' ? 'Equal weights' : 'MOD spending weights', color: '#87958e', width: 1.6, dash: 'dot'},
    {key: 'benchmark', name: result.benchmark.label + ' tracker', color: '#2968a5', width: 2}
  ].map(trace => ({type: 'scatter', mode: 'lines', name: trace.name,
    x: result.series.map(d => d.date), y: result.series.map(d => d[trace.key]),
    line: {color: trace.color, width: trace.width, dash: trace.dash || 'solid'},
    hovertemplate: '%{x|%d %b %Y}<br>Index %{y:.2f}<extra>' + esc(trace.name) + '</extra>'}));
  Plotly.react('portfolio-chart', traces, {
    margin: {l: 45, r: 10, t: 15, b: 65}, paper_bgcolor: 'white', plot_bgcolor: 'white',
    font: {family: 'system-ui', color: '#6a7b83', size: 10}, hovermode: 'x unified',
    legend: {orientation: 'h', y: -.2, x: 0, font: {size: 9}},
    xaxis: {type: 'date', showgrid: false, zeroline: false},
    yaxis: {gridcolor: '#edf1ef', zeroline: false, tickformat: '.1f'},
    shapes: [{type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 100, y1: 100, line: {color: '#cbd6d0', width: 1, dash: 'dot'}}]
  }, {...config, displayModeBar: false});
  const positive = result.rows.filter(r => r.contribution_pp > 1e-10).sort((a, b) => b.contribution_pp - a.contribution_pp).slice(0, 5);
  const negative = result.rows.filter(r => r.contribution_pp < -1e-10).sort((a, b) => a.contribution_pp - b.contribution_pp).slice(0, 5);
  const featured = [...positive, ...negative];
  const remaining = result.rows.filter(row => !featured.includes(row));
  const bars = [...featured];
  if (remaining.length) bars.push({name: `Other ${remaining.length} suppliers`, contribution_pp: remaining.reduce((s, r) => s + r.contribution_pp, 0), aggregate: true});
  bars.sort((a, b) => a.contribution_pp - b.contribution_pp);
  const label = name => {const short = shortName(name); return short.length > 24 ? short.slice(0, 23) + '…' : short;};
  Plotly.react('contribution-chart', [{type: 'bar', orientation: 'h',
    y: bars.map(r => label(r.name)), x: bars.map(r => r.contribution_pp),
    marker: {color: bars.map(r => r.aggregate ? '#87958e' : r.contribution_pp >= 0 ? '#087e75' : '#b84952')},
    customdata: bars.map(r => [r.aggregate ? '' : r.name, r.name]),
    hovertemplate: '<b>%{customdata[1]}</b><br>%{x:+.3f} percentage points<extra></extra>'
  }], {margin: {l: 145, r: 15, t: 12, b: 35}, paper_bgcolor: 'white', plot_bgcolor: 'white',
    font: {family: 'system-ui', color: '#6a7b83', size: 10}, showlegend: false,
    xaxis: {title: {text: 'Contribution · pp', font: {size: 10}}, gridcolor: '#edf1ef', zeroline: true, zerolinecolor: '#bac9c1'},
    yaxis: {type: 'category', showgrid: false, fixedrange: true}
  }, {...config, displayModeBar: false});
  $('contribution-chart').removeAllListeners?.('plotly_click');
  $('contribution-chart').on('plotly_click', e => {const name = e.points[0]?.customdata?.[0]; if (name) selectCompany(name, true);});
  $('contribution-caption').textContent = 'Up to five positive and five negative contributors; all remaining firms are grouped. Bars sum to ' + pp(result.return_pct) + '. Select a company bar to explore it.';
}
function renderPortfolioTable(result) {
  $('portfolio-contributions').innerHTML = result.rows.map(row => `<tr><td><button class="supplier-button" data-portfolio-company="${esc(row.name)}">${esc(row.name)}</button></td><td>${(row.weight * 100).toFixed(2)}%</td><td class="${direction(row.gbp_return_pct)}">${pct(row.gbp_return_pct)}</td><td class="${direction(row.contribution_pp)}">${pp(row.contribution_pp)}</td><td class="${direction(row.local_contribution_pp)}">${pp(row.local_contribution_pp)}</td><td class="${direction(row.fx_contribution_pp)}">${pp(row.fx_contribution_pp)}</td></tr>`).join('');
  for (const [id, value, format] of [
    ['portfolio-table-return', result.return_pct, pct], ['portfolio-table-contribution', result.return_pct, pp],
    ['portfolio-table-local', result.local_return_pct, pp], ['portfolio-table-fx', result.fx_contribution_pp, pp]
  ]) $(id).textContent = format(value);
  $('portfolio-contributions').querySelectorAll('[data-portfolio-company]').forEach(button => button.addEventListener('click', () => selectCompany(button.dataset.portfolioCompany, true)));
}
function renderPortfolioDrivers(result) {
  $('portfolio-news-date').textContent = briefing ? `News: ${pretty(briefing.window_start)} – ${pretty(briefing.source_generated_at)}` : 'Current Codex briefing awaiting update';
  const positive = result.rows.filter(r => r.contribution_pp > 1e-10).sort((a, b) => b.contribution_pp - a.contribution_pp).slice(0, 2);
  const negative = result.rows.filter(r => r.contribution_pp < -1e-10).sort((a, b) => a.contribution_pp - b.contribution_pp).slice(0, 2);
  const drivers = [...positive, ...negative];
  $('portfolio-drivers').innerHTML = drivers.length ? drivers.map(row => {
    const entry = briefing?.companies.find(c => c.name === row.name);
    return `<article class="portfolio-driver"><small>${row.contribution_pp >= 0 ? 'POSITIVE CONTRIBUTOR' : 'NEGATIVE CONTRIBUTOR'} · ${(row.weight * 100).toFixed(1)}% starting weight</small><strong class="${direction(row.contribution_pp)}">${pp(row.contribution_pp)}</strong><button data-driver-company="${esc(row.name)}">${esc(shortName(row.name))} ↗</button><p>${esc(entry?.summary || 'A current Codex news summary is unavailable for this company. The contribution above is calculated from prices and currency data.')}</p><div class="briefing-sources">${entry ? briefingSources(entry) : ''}</div></article>`;
  }).join('') : '<p class="portfolio-unavailable">The basket is unchanged over this window; no positive or negative contributors to highlight.</p>';
  $('portfolio-drivers').querySelectorAll('[data-driver-company]').forEach(button => button.addEventListener('click', () => selectCompany(button.dataset.driverCompany, true)));
}
