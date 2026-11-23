/* Verify accounting identities independently of chart rendering. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {calculate, periodStart} = require('../assets/portfolio.js');
const near = (actual, expected, label) => assert.ok(Math.abs(actual - expected) < 1e-8, `${label || ''}: ${actual} != ${expected}`);
const bars = (a, b) => [{date: '2026-11-13', adjusted: a}, {date: '2026-11-20', adjusted: b}];
const market = (currency, a, b) => ({currency, status: 'ok', bars: bars(a, b)});
const fixture = () => ({generated_at: '2026-11-23T12:00:00+00:00', companies: [
  {name: 'Euro PLC', ticker: 'EU', spend_m: 100, market: market('EUR', 100, 110)},
  {name: 'British PLC', ticker: 'GB', spend_m: 100, market: market('GBp', 10000, 9000)},
  {name: 'Private Ltd', ticker: null, spend_m: 100, market: {bars: []}}
], portfolio_market: {benchmarks: {
  global: {label: 'Global', market: market('GBP', 100, 103)},
  uk: {label: 'UK', market: market('GBp', 10000, 10200)}
}, fx: {EUR: {market: market('GBP', .8, .84)}}}});
let checks = 0;
function check(name, test) {test(); checks++;}
check('FX plus local equals GBP, without losing the interaction', () => {
  const r = calculate(fixture(), {period: '1W'});
  near(r.return_pct, 2.75); near(r.local_return_pct, 0); near(r.fx_contribution_pp, 2.75);
  near(r.benchmark_return_pct, 3); near(r.excess_pp, -.25);
  near(r.rows.find(c => c.ticker === 'EU').gbp_return_pct, 15.5);
  near(r.rows.find(c => c.ticker === 'GB').fx_contribution_pp, 0);
  near(r.series[0].spend, 100); near(r.series.at(-1).spend, 102.75);
  assert.equal(r.coverage.quoted, 2); assert.equal(r.coverage.total, 3); near(r.coverage.spend_pct, 200 / 3);
  assert.deepEqual(r.breadth, {up: 1, down: 1, flat: 0});
});
check('spending and equal weights reset at the same baseline', () => {
  const s = fixture(); s.companies[0].spend_m = 300;
  const weighted = calculate(s, {period: '1W'}), equal = calculate(s, {period: '1W', weighting: 'equal'});
  near(weighted.return_pct, 9.125); near(equal.return_pct, 2.75);
  near(weighted.alternative_return_pct, equal.return_pct); near(equal.alternative_return_pct, weighted.return_pct);
  assert.equal(weighted.start, equal.start); assert.equal(weighted.end, equal.end);
});
check('UK benchmark uses the same currency and period', () => {
  const r = calculate(fixture(), {period: '1W', benchmark: 'uk'});
  near(r.return_pct, 2.75); near(r.benchmark_return_pct, 2); near(r.excess_pp, .75);
});
check('last known holiday price is valued at the current FX rate', () => {
  const s = fixture();
  s.companies[0].market.bars[1].date = '2026-11-19';
  s.portfolio_market.benchmarks.global.market.bars.splice(1, 0, {date: '2026-11-19', adjusted: 102});
  const r = calculate(s, {period: '1W'});
  assert.equal(r.end, '2026-11-19');
  near(r.rows.find(c => c.ticker === 'EU').fx_return_pct, 0);
  assert.ok(!r.series.some(day => day.date > r.end));
});
check('an unavailable company blocks the basket instead of disappearing', () => {
  const s = fixture(); s.companies[0].market.bars = [];
  assert.throws(() => calculate(s), /Euro PLC.*unavailable/);
});
check('unknown currencies and missing FX are never assumed to be sterling', () => {
  const s = fixture(); delete s.portfolio_market.fx.EUR;
  assert.throws(() => calculate(s), /EUR.*unavailable/);
  delete s.companies[0].market.currency;
  assert.throws(() => calculate(s), /currency unavailable/);
});
check('wrong FX direction and benchmark currency are rejected', () => {
  const s = fixture(); s.portfolio_market.fx.EUR.market.currency = 'EUR';
  assert.throws(() => calculate(s), /GBP-per-unit/);
  s.portfolio_market.benchmarks.global.market.currency = 'USD';
  assert.throws(() => calculate(s), /Benchmark must/);
});
check('future values never enter an earlier snapshot', () => {
  const s = fixture();
  for (const m of [s.companies[0].market, s.companies[1].market, s.portfolio_market.fx.EUR.market, s.portfolio_market.benchmarks.global.market]) m.bars.push({date: '2026-11-24', adjusted: 999999});
  const r = calculate(s, {period: '1W'}); near(r.return_pct, 2.75); assert.equal(r.end, '2026-11-20');
});
check('zero moves remain exactly flat', () => {
  const s = fixture(); s.companies[0].market.bars = bars(100, 100); s.companies[1].market.bars = bars(10000, 10000); s.portfolio_market.fx.EUR.market.bars = bars(.8, .8);
  const r = calculate(s); near(r.return_pct, 0); near(r.top_five_gross_share_pct, 0); assert.equal(r.breadth.flat, 2);
});
check('corrupt, duplicate and reversed prices are rejected', () => {
  for (const changed of [0, -1, NaN, Infinity]) {const s = fixture(); s.companies[0].market.bars[1].adjusted = changed; assert.throws(() => calculate(s), /invalid/);}
  const s = fixture(); s.companies[0].market.bars.reverse(); assert.throws(() => calculate(s), /unordered/);
});
check('gaps beyond a week cannot be silently carried across', () => {
  const s = fixture();
  s.portfolio_market.benchmarks.global.market.bars = [{date: '2026-10-01', adjusted: 100}, {date: '2026-11-03', adjusted: 101}, {date: '2026-11-20', adjusted: 103}];
  s.companies[0].market.bars = [{date: '2026-10-01', adjusted: 100}, {date: '2026-11-20', adjusted: 110}];
  s.companies[1].market.bars = [{date: '2026-10-01', adjusted: 100}, {date: '2026-11-20', adjusted: 90}];
  s.portfolio_market.fx.EUR.market.bars = [{date: '2026-10-01', adjusted: .8}, {date: '2026-11-20', adjusted: .84}];
  assert.throws(() => calculate(s, {period: 'ALL'}), /seven calendar days/);
});
check('calendar windows clamp month ends and flag limited history', () => {
  assert.equal(periodStart('2026-03-31', '1M'), '2026-02-28');
  assert.equal(periodStart('2024-02-29', '1Y'), '2023-02-28');
  assert.equal(periodStart('2026-11-20', 'YTD'), '2025-12-31');
  assert.ok(calculate(fixture(), {period: '1Y'}).warnings.some(w => w.includes('common history')));
});
check('only the top 50 enter; unquoted firms never receive a zero-return holding', () => {
  const s = fixture();
  s.companies = Array.from({length: 51}, (_, i) => ({...s.companies[1], name: 'Company ' + i, spend_m: 100 + i}));
  const r = calculate(s); assert.equal(r.rows.length, 50); assert.ok(!r.rows.some(c => c.name === 'Company 0'));
});
check('snapshot periods reconcile for both weighting and benchmark choices', () => {
  const s = JSON.parse(fs.readFileSync(process.env.STOCKMONITOR_SNAPSHOT || 'data/snapshot.json', 'utf8'));
  assert.ok(s.portfolio_market, 'Saved snapshot must include benchmark and FX data');
  for (const period of ['1W', '1M', '3M', '6M', 'YTD', '1Y', 'ALL']) {
    for (const weighting of ['spend', 'equal']) for (const benchmark of ['global', 'uk']) {
      const r = calculate(s, {period, weighting, benchmark});
      near(r.rows.reduce((sum, c) => sum + c.weight, 0), 1);
      near(r.return_pct, r.local_return_pct + r.fx_contribution_pp);
      near(r.return_pct, r.series.at(-1)[weighting] - 100);
      near(r.excess_pp, r.return_pct - r.benchmark_return_pct);
      assert.equal(r.rows.length, 34); near(r.series[0].benchmark, 100);
      assert.ok(r.series.every(day => day.date <= r.end && day.date >= r.start));
      assert.equal(r.breadth.up + r.breadth.down + r.breadth.flat, r.rows.length);
    }
  }
});
console.log(`${checks} portfolio accounting, coverage, calendar and saved-data checks passed.`);
