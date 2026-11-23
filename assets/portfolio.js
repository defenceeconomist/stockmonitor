/* Auditable buy-and-hold basket arithmetic; usable in the browser and Node checks. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Portfolio = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const DAY = 86400000;
  const age = (a, b) => (Date.parse(a) - Date.parse(b)) / DAY;

  function periodStart(last, period) {
    const date = new Date(last + 'T00:00:00Z');
    const months = {'1M': 1, '3M': 3, '6M': 6, '1Y': 12, '5Y': 60};
    if (period === 'ALL') return '0000-01-01';
    if (period === '1W') date.setUTCDate(date.getUTCDate() - 7);
    else if (period === 'YTD') {date.setUTCMonth(0, 1); date.setUTCDate(0);}
    else if (months[period]) {
      const day = date.getUTCDate();
      date.setUTCDate(1); date.setUTCMonth(date.getUTCMonth() - months[period]);
      const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
      date.setUTCDate(Math.min(day, lastDay));
    } else throw new Error('Unsupported portfolio period');
    return date.toISOString().slice(0, 10);
  }

  function checkedBars(market, label) {
    const bars = market?.bars;
    if (!Array.isArray(bars) || bars.length < 2) throw new Error(label + ': price history unavailable. No company has been dropped from the basket.');
    let previous = '';
    for (const bar of bars) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(bar.date) || bar.date <= previous || !Number.isFinite(bar.adjusted) || bar.adjusted <= 0) {
        throw new Error(label + ': invalid or unordered price history.');
      }
      previous = bar.date;
    }
    return bars;
  }

  function observation(bars, date, label) {
    let low = 0, high = bars.length - 1, index = -1;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (bars[mid].date <= date) {index = mid; low = mid + 1;} else high = mid - 1;
    }
    if (index < 0 || age(date, bars[index].date) > 7) {
      throw new Error(label + ': no observation within seven calendar days of ' + date + '.');
    }
    return bars[index];
  }

  function calculate(snapshot, options = {}) {
    const period = options.period || '1M';
    const weighting = options.weighting || 'spend';
    const benchmarkKey = options.benchmark || 'global';
    if (!['spend', 'equal'].includes(weighting)) throw new Error('Unsupported portfolio weighting');
    const top = [...snapshot.companies].sort((a, b) => b.spend_m - a.spend_m || a.name.localeCompare(b.name)).slice(0, 50);
    const companies = top.filter(c => c.ticker);
    if (!companies.length) throw new Error('No quoted suppliers in the top 50.');
    const market = snapshot.portfolio_market;
    const benchmark = market?.benchmarks?.[benchmarkKey];
    if (!benchmark) throw new Error('Benchmark data is unavailable. Refresh the portfolio market data.');
    if (!['GBP', 'GBp'].includes(benchmark.market?.currency)) throw new Error('Benchmark must be quoted in GBP or GBp.');
    const benchmarkBars = checkedBars(benchmark.market, benchmark.label);
    const allSeries = [{bars: benchmarkBars, market: benchmark.market, label: benchmark.label}];
    const currencySeries = new Map();
    const inputs = companies.map(company => {
      const bars = checkedBars(company.market, company.name);
      if (!Number.isFinite(company.spend_m) || company.spend_m <= 0) throw new Error('Invalid supplier spending weight.');
      allSeries.push({bars, market: company.market, label: company.name});
      const currency = company.market.currency;
      if (!currency) throw new Error(company.name + ': quote currency unavailable.');
      if (!['GBP', 'GBp'].includes(currency) && !currencySeries.has(currency)) {
        const fxMarket = market.fx?.[currency]?.market;
        if (fxMarket?.currency !== 'GBP') throw new Error(currency + ': GBP-per-unit exchange rate unavailable.');
        const fxBars = checkedBars(fxMarket, currency + '/GBP');
        currencySeries.set(currency, fxBars);
        allSeries.push({bars: fxBars, market: fxMarket, label: currency + '/GBP'});
      }
      return {company, bars, currency};
    });
    // A single common end and fixed membership prevents changing coverage between curves.
    const end = allSeries.reduce((day, s) => s.bars.at(-1).date < day ? s.bars.at(-1).date : day, snapshot.generated_at.slice(0, 10));
    const first = allSeries.reduce((day, s) => s.bars[0].date > day ? s.bars[0].date : day, '0000-01-01');
    const available = benchmarkBars.filter(b => b.date >= first && b.date <= end).map(b => b.date);
    if (available.length < 2) throw new Error('Insufficient overlapping company, currency and benchmark history.');
    const target = periodStart(end, period);
    const baseline = available.findLast(day => day <= target) || available[0];
    const dates = available.filter(day => day >= baseline);
    if (dates.length < 2) throw new Error('This window has fewer than two common valuation dates.');
    const clipped = period !== 'ALL' && target < available[0];
    const spend = companies.reduce((sum, c) => sum + c.spend_m, 0);
    const topSpend = top.reduce((sum, c) => sum + c.spend_m, 0);
    const rate = (currency, day) => currency === 'GBP' ? 1 : currency === 'GBp' ? .01 : observation(currencySeries.get(currency), day, currency + '/GBP').adjusted;
    const initial = inputs.map(input => ({...input,
      base: observation(input.bars, baseline, input.company.name),
      baseFx: rate(input.currency, baseline),
      spendWeight: input.company.spend_m / spend,
      equalWeight: 1 / companies.length}));
    const benchmarkBase = observation(benchmarkBars, baseline, benchmark.label).adjusted;
    const series = dates.map(date => {
      let spendIndex = 0, equalIndex = 0;
      for (const item of initial) {
        const local = observation(item.bars, date, item.company.name).adjusted / item.base.adjusted;
        const value = local * rate(item.currency, date) / item.baseFx;
        spendIndex += item.spendWeight * value;
        equalIndex += item.equalWeight * value;
      }
      return {date, spend: 100 * spendIndex, equal: 100 * equalIndex,
        benchmark: 100 * observation(benchmarkBars, date, benchmark.label).adjusted / benchmarkBase};
    });
    const rows = initial.map(item => {
      const last = observation(item.bars, dates.at(-1), item.company.name);
      const local = last.adjusted / item.base.adjusted;
      const fx = rate(item.currency, dates.at(-1)) / item.baseFx;
      const weight = weighting === 'equal' ? item.equalWeight : item.spendWeight;
      // Exact identity: (L*F - 1) = (L - 1) + L*(F - 1). Interaction belongs to FX.
      return {name: item.company.name, ticker: item.company.ticker, currency: item.currency,
        weight, start_date: item.base.date, end_date: last.date,
        local_return_pct: (local - 1) * 100, fx_return_pct: (fx - 1) * 100,
        gbp_return_pct: (local * fx - 1) * 100,
        contribution_pp: weight * (local * fx - 1) * 100,
        local_contribution_pp: weight * (local - 1) * 100,
        fx_contribution_pp: weight * local * (fx - 1) * 100};
    });
    rows.sort((a, b) => Math.abs(b.contribution_pp) - Math.abs(a.contribution_pp) || a.name.localeCompare(b.name));
    const total = rows.reduce((sum, row) => sum + row.contribution_pp, 0);
    const localTotal = rows.reduce((sum, row) => sum + row.local_contribution_pp, 0);
    const fxTotal = rows.reduce((sum, row) => sum + row.fx_contribution_pp, 0);
    const absolute = rows.reduce((sum, row) => sum + Math.abs(row.contribution_pp), 0);
    const benchmarkReturn = series.at(-1).benchmark - 100;
    const warnings = allSeries.filter(s => s.market.status !== 'ok').map(s => s.label + ': ' + (s.market.status || 'unknown data status'));
    if (age(snapshot.generated_at.slice(0, 10), end) > 7) warnings.push('The common valuation date is more than a week behind the snapshot.');
    if (clipped) warnings.push('Requested history is unavailable for the full basket; showing the common history from ' + baseline + '.');
    return {period, weighting, benchmark, start: baseline, end: dates.at(-1), series, rows,
      return_pct: total, benchmark_return_pct: benchmarkReturn, excess_pp: total - benchmarkReturn,
      local_return_pct: localTotal, fx_contribution_pp: fxTotal,
      alternative_return_pct: series.at(-1)[weighting === 'equal' ? 'spend' : 'equal'] - 100,
      coverage: {quoted: companies.length, total: top.length, spend_pct: 100 * spend / topSpend},
      breadth: {up: rows.filter(r => r.gbp_return_pct > 1e-10).length, down: rows.filter(r => r.gbp_return_pct < -1e-10).length,
        flat: rows.filter(r => Math.abs(r.gbp_return_pct) <= 1e-10).length},
      top_five_gross_share_pct: absolute ? 100 * rows.slice(0, 5).reduce((sum, r) => sum + Math.abs(r.contribution_pp), 0) / absolute : 0,
      largest_two_weight_pct: 100 * [...rows].sort((a, b) => b.weight - a.weight).slice(0, 2).reduce((sum, r) => sum + r.weight, 0),
      warnings};
  }
  return {calculate, periodStart, observation};
});
