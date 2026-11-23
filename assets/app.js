/* Client-side interactions only; all data is prepared by Python at build time. */
'use strict';
const $ = id => document.getElementById(id);
const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = n => n >= 1000 ? `£${(n / 1000).toFixed(2)}bn` : `£${n.toLocaleString('en-GB')}m`;
const pct = n => n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
const direction = n => n == null ? '' : n >= 0 ? 'up' : 'down';
const pretty = date => new Date(date.length === 10 ? `${date}T12:00:00Z` : date).toLocaleDateString('en-GB', {day:'numeric', month:'short',year:'numeric',timeZone:'UTC'});
const config = {responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d'],scrollZoom:false};
let dataset, selected, briefing = null, quotedOnly = false, coveredOnly = true, chartPeriod = '1M', highlighted = null;
function topCompanies(companies) {return [...companies].sort((a,b)=>b.spend_m-a.spend_m || a.name.localeCompare(b.name)).slice(0,50);}

function startDate(last, period) {
  const d = new Date(`${last}T00:00:00Z`);
  const months = {'1M':1,'3M':3,'6M':6};
  if (period === '1W') d.setUTCDate(d.getUTCDate()-7);
  else if (period === 'YTD') { d.setUTCMonth(0,1); d.setUTCDate(0); }
  else if (months[period]) {
    const day = d.getUTCDate();
    d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth()-months[period]);
    const max = new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,0)).getUTCDate();
    d.setUTCDate(Math.min(day,max));
  } else { const month = d.getUTCMonth(); d.setUTCFullYear(d.getUTCFullYear()-(period==='5Y'?5:1)); if(d.getUTCMonth()!==month)d.setUTCDate(0); }
  return d.toISOString().slice(0,10);
}
function windowBars(company, period) {
  const bars = company.market.bars || [];
  if (!bars.length) return [];
  const target = startDate(bars.at(-1).date,period);
  let i = bars.findLastIndex(b => b.date <= target);
  if (i < 0) i = 0;
  return bars.slice(i);
}
function performance(company, period) {
  const b = windowBars(company,period);
  return b.length > 1 ? (b.at(-1).adjusted/b[0].adjusted-1)*100 : null;
}
function shortName(name) {return name.replace(/ (PLC|Inc\.?|Corporation|Holdings|Company|Group|SE|SpA|AG|AB|S\.A\.)/g,'').replace('The Boeing','Boeing');}
function selectCompany(name, scroll=false) {
  selected = dataset.companies.find(c => c.name === name);
  $('company-select').value = name; highlighted = null;
  renderCompany();
  renderMap();
  if(scroll)$('market').scrollIntoView({behavior:'smooth',block:'start'});
}
function renderMap() {
  const period = $('map-period').value;
  const top = topCompanies(dataset.companies);
  const companies = top.filter(c => !quotedOnly || c.ticker);
  $('map-count').textContent=`${companies.length} of ${top.length} largest suppliers · ranked by 2024/25 MOD payments`;
  const series = companies.map(c => performance(c,period));
  const extent = Math.max(5,...series.filter(n=>n!=null).map(Math.abs));
  const tone = n => {
    if(n==null)return '#70838d';
    const amount = .75+.25*Math.min(Math.abs(n)/Math.min(extent,40),1);
    const from=[232,239,241], to=n>=0?[8,126,117]:[189,78,80];
    return `rgb(${from.map((v,i)=>Math.round(v+(to[i]-v)*amount)).join(',')})`;
  };
  Plotly.react('treemap',[{type:'treemap',level:'',ids:companies.map(c=>c.name),labels:companies.map(c=>shortName(c.name)),parents:companies.map(()=>''),values:companies.map(c=>c.spend_m),sort:false,
    marker:{colors:series.map(tone),line:{color:companies.map(c=>c.name===selected?.name?'#122c3b':'white'),width:companies.map(c=>c.name===selected?.name?4:2)}},text:series.map((n,i)=>`${money(companies[i].spend_m)} · ${n==null?'No quote':pct(n)}`),textinfo:'label+text',textfont:{size:15,color:'white'},
    customdata:companies.map((c,i)=>[c.name,money(c.spend_m),pct(series[i]),c.ticker||'No direct listing mapped',c.market.bars.at(-1)?.date||'—']),
    hovertemplate:'<b>%{customdata[0]}</b><br>2024/25 MOD payments: %{customdata[1]}<br>'+period+' adjusted change: %{customdata[2]}<br>%{customdata[3]} · session %{customdata[4]}<extra></extra>',
    pathbar:{visible:false},tiling:{pad:2},root:{color:'white'}}],{margin:{l:0,r:0,t:0,b:0},paper_bgcolor:'white',font:{family:'system-ui'},uniformtext:{minsize:11,mode:'hide'}}, {...config,displayModeBar:false});
  const graph = $('treemap');
  graph.removeAllListeners?.('plotly_treemapclick');
  graph.on('plotly_treemapclick', e => {const name=e.points[0]?.id;if(name)selectCompany(name,true);return false;});
  renderTable();
}
function renderCompany() {
  const c=selected,bars=c.market.bars||[],latest=bars.at(-1),value=performance(c,chartPeriod);
  $('selected-name').textContent=c.name;
  $('selected-meta').textContent=`${money(c.spend_m)} MOD payments in 2024/25${c.ticker?` · ${c.ticker} · ${c.market.exchange||'exchange unavailable'}${latest?' · close '+pretty(latest.date):''}`:''}`;
  $('latest-price').textContent=latest?`${latest.close.toLocaleString('en-GB',{maximumFractionDigits:2,minimumFractionDigits:2})} ${c.market.currency}`:'No direct quote';
  $('selected-return').textContent=latest?`${pct(value)} · ${chartPeriod} adjusted`:'Private, state-owned or unmapped entity';
  $('selected-return').className=direction(value);
  const warnings=[];
  if(c.market.status==='stale')warnings.push('Price refresh failed. Showing the previous successful download.');
  if(latest){
    const age=(new Date(dataset.generated_at)-new Date(latest.date+'T23:59:59Z'))/86400000;
    if(age>7)warnings.push(`Latest session is over a week old (${pretty(latest.date)}).`);
  }
  if(c.ticker && !latest)warnings.push('Price data is unavailable for this listing.');
  if(c.news_status && c.news_status!=='ok')warnings.push(`News refresh ${c.news_status}. ${c.news.length?'Previous headlines are retained.':'No headlines available.'}`);
  $('company-notice').hidden=!warnings.length;
  $('company-notice').textContent=warnings.join(' ');
  renderChart();renderNews();renderWeeklyCompany();renderCompanyBriefing();
}
function renderChart() {
  const c=selected,visible=windowBars(c,chartPeriod),mode=$('chart-mode').value;
  const node=$('stock-chart');
  node.hidden=!visible.length;
  if(!visible.length)return;
  const indexed=mode==='indexed';
  const value = b => indexed ? b.adjusted/visible[0].adjusted*100 : b[mode==='close'?'close':'adjusted'];
  const groups=new Map();
  for(const story of c.news||[]){if(!story.session)continue;const b=visible.find(b=>b.date===story.session);if(!b)continue;if(!groups.has(b.date))groups.set(b.date,[]);groups.get(b.date).push(story);}
  const days=[...groups.keys()].sort();
  const traces=[{type:'scatter',mode:'lines',x:visible.map(b=>b.date),y:visible.map(value),line:{color:'#087e75',width:2.5},fill:'tozeroy',fillcolor:'rgba(8,126,117,.045)',name:mode==='close'?'Close':'Adjusted',hovertemplate:'%{x|%d %b %Y}<br>%{y:,.2f} '+(indexed?'index':esc(c.market.currency))+'<extra></extra>'},
    {type:'scatter',mode:'markers',x:days,y:days.map(d=>value(visible.find(b=>b.date===d))),name:'News',marker:{size:9,color:'white',line:{color:'#2968a5',width:2}},
    text:days.map(d=>groups.get(d).slice(0,3).map(s=>esc(s.title).match(/.{1,65}(?:\s|$)|.{1,65}/g)?.join('<br>')).join('<br><br>')),customdata:days.map(d=>pct(groups.get(d)[0].move_pct)),hovertemplate:'<b>%{x|%d %b %Y}</b> · daily move %{customdata}<br>%{text}<extra>News</extra>'}];
  const yValues=visible.map(value);
  const low=Math.min(...yValues),high=Math.max(...yValues),padding=Math.max((high-low)*.15,high*.01);
  const shapes=highlighted?[{type:'line',x0:highlighted,x1:highlighted,y0:0,y1:1,yref:'paper',line:{color:'#d39d31',dash:'dot',width:2}}]:[];
  const target=startDate(c.market.bars.at(-1).date,chartPeriod);
  const shortHistory=visible[0].date>target;
  Plotly.react(node,traces,{margin:{l:65,r:15,t:35,b:45},paper_bgcolor:'white',plot_bgcolor:'white',font:{family:'system-ui',color:'#5c6f79',size:12},showlegend:false,hovermode:'closest',dragmode:'zoom',shapes,
    xaxis:{showgrid:false,zeroline:false,type:'date'},yaxis:{title:{text:indexed?'Index · start = 100':`${mode==='close'?'Close':'Adjusted'} · ${c.market.currency}`,font:{size:12}},gridcolor:'#edf1f4',zeroline:false,fixedrange:false,range:[low-padding,high+padding]},
    annotations:[{xref:'paper',yref:'paper',x:0,y:1.12,xanchor:'left',showarrow:false,text:`${pretty(visible[0].date)} – ${pretty(visible.at(-1).date)}${shortHistory?' · available history':''}`,font:{size:11,color:'#5c6f79'}}]},config);
  node.removeAllListeners?.('plotly_click');
  node.on('plotly_click',event=>{const point=event.points[0];if(point.curveNumber===1){highlighted=point.x;renderNews();renderChart();$('news-list').querySelector('.highlighted')?.scrollIntoView({behavior:'smooth',block:'nearest'});}});
}
function renderNews() {
  const c=selected;
  $('news-updated').textContent='';
  if(!c.ticker && !(c.news||[]).length){$('news-list').innerHTML='<div class="empty">No direct stock listing is mapped for this holding company. Its MOD payments remain included in the treemap and directory.</div>';return;}
  const news=c.news||[];
  $('news-updated').textContent=c.news_fetched_at?'Fetched '+pretty(c.news_fetched_at):'';
  if(!news.length){$('news-list').innerHTML='<div class="empty">No recent matching headlines were returned. This does not imply that no news exists.</div>';return;}
  $('news-list').innerHTML=news.map((n,i)=>`<article class="news-row ${n.session===highlighted?'highlighted':''}"><div><div class="news-meta">${esc(n.source)} · ${pretty(n.published)} · ${new Date(n.published).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'UTC'})} UTC</div><a class="news-title" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a></div><div class="news-move"><strong class="${direction(n.move_pct)}">${!c.ticker?'No quote':n.move_pct==null?'Pending':pct(n.move_pct)}</strong><span>${!c.ticker?'No direct public listing':n.session?pretty(n.session)+' session':'Next completed session'}</span>${n.session?`<button data-news="${i}">Show on chart</button>`:''}</div></article>`).join('');
  $('news-list').querySelectorAll('[data-news]').forEach(b=>b.addEventListener('click',()=>{
    const n=news[Number(b.dataset.news)];highlighted=n.session;
    const visible=windowBars(c,chartPeriod);
    if(n.session<visible[0]?.date){chartPeriod='1Y';updateHorizons();}
    renderCompany();$('stock-chart').scrollIntoView({behavior:'smooth',block:'center'});
  }));
}
function weeklyBody(c) {
  const w=c.weekly_summary;
  if(!w)return '<p>Weekly summary unavailable. Refresh the snapshot to generate it.</p>';
  const prices=w.price_start?`${pretty(w.price_start)} – ${pretty(w.price_end)}`:`${pretty(w.week_start)} – ${pretty(w.week_end)}`;
  const largest=w.largest_session?`Largest daily move: <strong class="${direction(w.largest_session.change_pct)}">${pct(w.largest_session.change_pct)}</strong> on ${pretty(w.largest_session.date)}.`:'';
  const sources=(w.sources||[]).map((n,i)=>`<li><a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">[${i+1}] ${esc(n.headline)}</a><span> · ${esc(n.source)} · ${pretty(n.published)}${n.session?' · session '+pretty(n.session):''}</span></li>`).join('');
  return `<div class="weekly-meta"><span class="weekly-status ${esc(w.status)}">${esc(w.label)}</span><span>${prices}</span></div><p class="weekly-text">${esc(w.text)}</p>${largest?`<p class="weekly-largest">${largest}</p>`:''}${sources?`<details class="weekly-sources"><summary>Read the supporting reports (${w.sources.length})</summary><ol>${sources}</ol></details>`:''}`;
}
function briefingSources(entry) {
  return (entry.sources||[]).map((n,i)=>`<a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer" title="${esc(n.title)}">${esc(n.source)} · ${pretty(n.published)} ↗<span class="sr-only">: ${esc(n.title)}</span></a>`).join('');
}
function renderCompanyBriefing() {
  const entry=briefing?.companies.find(c=>c.name===selected.name);
  $('company-briefing').innerHTML=entry?`<div class="eyebrow">LATEST NEWS · CODEX BRIEFING</div><p>${esc(entry.summary)}</p><div class="briefing-sources">${briefingSources(entry)}</div>`:'<p class="muted">'+(topCompanies(dataset.companies).some(c=>c.name===selected.name)?'A current Codex news briefing is awaiting the next update.':'This supplier is outside the top-50 news briefing. Recent headlines are available below.')+'</p>';
}
function renderBriefing() {
  $('briefing-date').textContent=briefing?`${pretty(briefing.window_start)} – ${pretty(briefing.source_generated_at)} · prepared ${pretty(briefing.generated_at)}`:'Latest seven days · briefing awaiting a Codex update';
  $('briefing-overview').textContent=briefing?.overview||'The next Codex update will prepare a source-linked news briefing for the 50 largest suppliers.';
  if(!briefing){$('briefing-grid').innerHTML='<div class="empty">No briefing is available for this snapshot.</div>';$('briefing-count').textContent='';return;}
  const term=$('briefing-search').value.trim().toLowerCase();
  const companies=topCompanies(dataset.companies);
  const entries=companies.map((c,i)=>({...briefing.companies.find(e=>e.name===c.name),company:c,rank:i+1})).filter(e=>(!coveredOnly||e.status==='covered')&&(e.name+' '+(e.company.ticker||'')).toLowerCase().includes(term));
  $('briefing-grid').innerHTML=entries.length?entries.map(e=>`<article class="briefing-card ${e.status==='no_news'?'no-news':''}"><div class="briefing-card-meta"><span>#${String(e.rank).padStart(2,'0')} · ${money(e.company.spend_m)} MOD payments</span><span class="${direction(e.company.weekly_summary?.change_pct)}">${pct(e.company.weekly_summary?.change_pct)}<span class="sr-only"> weekly adjusted change</span></span></div><button class="briefing-company" data-briefing-company="${esc(e.name)}">${esc(shortName(e.name))}<span aria-hidden="true"> ↗</span></button><p>${esc(e.summary)}</p><div class="briefing-sources">${briefingSources(e)}</div>${e.status==='no_news'?'<span class="muted">No qualifying recent coverage</span>':''}</article>`).join(''):'<div class="empty">No suppliers match this search. Try All 50 for firms without recent coverage.</div>';
  $('briefing-count').textContent=`${entries.length} of 50 suppliers shown · ranked by annual MOD payments · percentage = latest weekly adjusted return`;
  $('briefing-grid').querySelectorAll('[data-briefing-company]').forEach(b=>b.addEventListener('click',()=>selectCompany(b.dataset.briefingCompany,true)));
}
function renderWeeklyCompany(){
  $('company-weekly').innerHTML=`<div class="eyebrow">LATEST WEEK · FIXED WINDOW</div><h3>Weekly movement summary <span class="${direction(selected.weekly_summary?.change_pct)}">${pct(selected.weekly_summary?.change_pct)}</span></h3>${weeklyBody(selected)}`;
}
function renderWeeklyOverview(){
 const period=dataset.weekly_period;
 $('weekly-period').textContent=period?`${pretty(period.start)} – ${pretty(period.end)} · updated weekly · adjusted close-to-close returns`:'Weekly summaries awaiting refresh';
 const term=$('weekly-search').value.toLowerCase();
 const companies=topCompanies(dataset.companies).filter(c=>(c.name+' '+(c.ticker||'')).toLowerCase().includes(term));
 $('weekly-overview').innerHTML=companies.map(c=>`<details class="weekly-company"><summary><span>${esc(c.name)}<small>${esc(c.ticker||'No direct quote')} · ${esc(c.weekly_summary?.label||'Unavailable')}</small></span><strong class="${direction(c.weekly_summary?.change_pct)}">${pct(c.weekly_summary?.change_pct)}</strong></summary><div class="weekly-content">${weeklyBody(c)}<button class="weekly-explore" data-weekly-company="${esc(c.name)}">Explore company chart and news</button></div></details>`).join('');
 $('weekly-count').textContent=`${companies.length} of ${topCompanies(dataset.companies).length} company summaries shown. Open a row for the explanation and supporting sources.`;
 $('weekly-overview').querySelectorAll('[data-weekly-company]').forEach(b=>b.addEventListener('click',()=>selectCompany(b.dataset.weeklyCompany,true)));
}

function renderTable(){
 const term=$('supplier-search').value.toLowerCase();
 const companies=dataset.companies.filter(c=>(c.name+' '+(c.ticker||'')).toLowerCase().includes(term));
 const period=$('map-period').value;$('return-heading').textContent=period+' change';
 $('supplier-table').innerHTML=companies.map(c=>{const p=performance(c,period);return `<tr><td><button class="supplier-button" data-company="${esc(c.name)}">${esc(c.name)}</button></td><td>${money(c.spend_m)}</td><td>${esc(c.ticker||'No direct quote')}</td><td class="${direction(p)}">${pct(p)}${c.market.status==='stale'?' *':''}</td></tr>`;}).join('');
 $('table-count').textContent=`${companies.length} ${companies.length===1?'company':'companies'} shown · sorted by 2024/25 MOD payments · * cached after a failed refresh`;
 $('supplier-table').querySelectorAll('[data-company]').forEach(b=>b.addEventListener('click',()=>selectCompany(b.dataset.company,true)));
}
function updateHorizons(){document.querySelectorAll('[data-period]').forEach(b=>{const active=b.dataset.period===chartPeriod;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});}
async function init(){
 try{
   const response=await fetch('assets/dashboard.json');if(!response.ok)throw new Error(`Data request failed (${response.status})`);
   dataset=await response.json();const cs=topCompanies(dataset.companies);
   try {const r=await fetch('assets/news-briefing.json');if(r.ok)briefing=await r.json();}catch{briefing=null;}
   if(briefing?.source_generated_at!==dataset.generated_at)briefing=null;
   if(dataset.warnings.length){$('data-warning').hidden=false;$('data-warning').textContent=`${dataset.warnings.length} data request(s) failed in this snapshot. Affected companies show cached or unavailable data. Select a company for details.`;}
   $('total-spend').textContent=money(cs.reduce((s,c)=>s+c.spend_m,0));
   $('company-count').textContent=cs.length;$('listed-count').textContent=cs.filter(c=>c.ticker).length;
   $('coverage').textContent=`${cs.filter(c=>c.market.bars.length).length} price histories available`;
   $('headline-count').textContent=cs.reduce((s,c)=>s+(c.news||[]).filter(n=>new Date(n.published)>=new Date(new Date(dataset.generated_at)-7*86400000)&&new Date(n.published)<=new Date(dataset.generated_at)).length,0).toLocaleString('en-GB');
   $('updated').textContent=pretty(dataset.generated_at)+' · '+new Date(dataset.generated_at).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'UTC'})+' UTC';
   const dates=cs.flatMap(c=>c.market.bars.length?[c.market.bars.at(-1).date]:[]).sort();
   $('price-date').textContent=`Latest quote session: ${pretty(dates.at(-1))}`;
   $('company-select').innerHTML=dataset.companies.map(c=>`<option value="${esc(c.name)}">${esc(c.name)}${c.ticker?' · '+esc(c.ticker):' · no quote'}</option>`).join('');
   $('source-notes').innerHTML=dataset.notes.map(n=>`<p><strong>${esc(n.id)}.</strong> ${esc(n.text)}</p>`).join('');
   $('company-select').addEventListener('change',e=>selectCompany(e.target.value));
   $('map-period').addEventListener('change',renderMap);
   for(const [id,only] of [['all-companies',false],['quoted-only',true]])$(id).addEventListener('click',()=>{quotedOnly=only;$('all-companies').classList.toggle('active',!only);$('quoted-only').classList.toggle('active',only);$('all-companies').setAttribute('aria-pressed',String(!only));$('quoted-only').setAttribute('aria-pressed',String(only));renderMap();});
   document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>{chartPeriod=b.dataset.period;highlighted=null;updateHorizons();renderCompany();}));
   $('briefing-search').addEventListener('input',renderBriefing);
   for(const [id,covered] of [['covered-news',true],['all-news',false]])$(id).addEventListener('click',()=>{coveredOnly=covered;for(const key of ['covered-news','all-news']){const active=key===(covered?'covered-news':'all-news');$(key).classList.toggle('active',active);$(key).setAttribute('aria-pressed',String(active));}renderBriefing();});
   initPortfolio();
   renderBriefing();
   $('weekly-search').addEventListener('input',renderWeeklyOverview);renderWeeklyOverview();
   $('chart-mode').addEventListener('change',renderChart);$('supplier-search').addEventListener('input',renderTable);
   updateHorizons();renderMap();selectCompany(cs[0].name);
 }catch(error){$('load-error').hidden=false;$('load-error').textContent='The dashboard could not load. Please reload the page. '+error.message;console.error(error);}
}
init();
