import json
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# HTML template — all CSS/JS inline, only Leaflet loaded lazily from CDN
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Forensic Report</title>
<style>
:root {
  --bg:#0d1117;--surf:#161b22;--surf2:#21262d;--border:#30363d;
  --text:#e6edf3;--muted:#7d8590;--accent:#f78166;--link:#58a6ff;
  --hover:rgba(177,186,196,.1);--accent-dim:rgba(247,129,102,.12);
  --del:#da3633;--ok:#3fb950;--warn:#d29922;
}
[data-theme=light] {
  --bg:#f6f8fa;--surf:#ffffff;--surf2:#f6f8fa;--border:#d0d7de;
  --text:#1f2328;--muted:#636c76;--accent:#cf222e;--link:#0969da;
  --hover:rgba(31,35,40,.08);--accent-dim:rgba(207,34,46,.08);
  --del:#cf222e;--ok:#1a7f37;--warn:#9a6700;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;line-height:1.5}
a{color:var(--link)}
/* ── Topbar ── */
.topbar{background:var(--surf);border-bottom:1px solid var(--border);padding:0 20px;height:52px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:200}
.topbar-left h1{font-size:1rem;font-weight:700;color:var(--accent)}
.topbar-left .meta{font-size:.75rem;color:var(--muted);margin-top:1px}
.topbar-right{display:flex;align-items:center;gap:8px}
/* ── Tabs ── */
.tab-bar{display:flex;gap:2px}
.tab-btn{padding:5px 13px;border:none;background:none;color:var(--muted);border-radius:6px;cursor:pointer;font-size:.8rem;font-weight:500;transition:background .15s,color .15s}
.tab-btn:hover{background:var(--hover);color:var(--text)}
.tab-btn.active{background:var(--accent-dim);color:var(--accent)}
/* ── Theme toggle ── */
.theme-btn{background:none;border:1px solid var(--border);color:var(--text);border-radius:6px;padding:4px 9px;cursor:pointer;font-size:.8rem}
.theme-btn:hover{background:var(--hover)}
/* ── Tab panels ── */
.tab-panel{display:none}
.tab-panel.active{display:block}
/* ── Overview ── */
.overview{padding:20px;max-width:1400px;margin:0 auto}
.stats-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.stat-card{background:var(--surf);border:1px solid var(--border);border-top:3px solid var(--accent);border-radius:8px;padding:16px;text-align:center}
.stat-val{font-size:2rem;font-weight:700;color:var(--accent);line-height:1}
.stat-lbl{font-size:.75rem;color:var(--muted);margin-top:4px}
.card{background:var(--surf);border:1px solid var(--border);border-radius:8px;margin-bottom:20px;overflow:hidden}
.card-hdr{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:.875rem}
.card-body{padding:16px}
#map{height:380px}
/* ── Table ── */
.filter-row{display:flex;gap:10px;align-items:center;margin-bottom:12px}
.filter-input{background:var(--surf2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:6px 11px;font-size:.8rem;width:260px;outline:none}
.filter-input:focus{border-color:var(--accent)}
.filter-input::placeholder{color:var(--muted)}
.tbl-wrap{overflow-x:auto}
table.etbl{width:100%;border-collapse:collapse;font-size:.8rem}
table.etbl th{padding:7px 10px;text-align:left;color:var(--muted);font-weight:600;border-bottom:2px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap}
table.etbl th:hover{color:var(--text)}
table.etbl th .sort-arrow{margin-left:4px;opacity:.4}
table.etbl th.sort-asc .sort-arrow::after{content:'▲'}
table.etbl th.sort-desc .sort-arrow::after{content:'▼'}
table.etbl td{padding:7px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
table.etbl tbody tr:hover td{background:var(--hover)}
.mono{font-family:monospace;font-size:.75rem}
.badge{padding:2px 7px;border-radius:10px;font-size:.7rem;font-weight:600;white-space:nowrap}
.badge-img{background:rgba(88,166,255,.15);color:var(--link)}
.badge-vid{background:rgba(210,153,34,.15);color:var(--warn)}
.badge-del{background:rgba(218,54,51,.15);color:var(--del)}
.badge-saved{background:rgba(63,185,80,.15);color:var(--ok)}
.badge-chat{background:rgba(177,186,196,.1);color:var(--muted)}
.gps-link{color:var(--link);cursor:pointer;text-decoration:underline dotted;font-family:monospace;font-size:.75rem}
.gps-link:hover{color:var(--text)}
.view-btn{background:none;border:1px solid var(--border);color:var(--text);padding:2px 8px;border-radius:4px;cursor:pointer;font-size:.75rem}
.view-btn:hover{background:var(--accent);border-color:var(--accent);color:#fff}
.export-btn{background:none;border:1px solid var(--border);color:var(--text);padding:4px 12px;border-radius:5px;cursor:pointer;font-size:.75rem}
.export-btn:hover{background:var(--accent);border-color:var(--accent);color:#fff}
.tbl-footer{display:flex;justify-content:space-between;align-items:center;margin-top:10px;color:var(--muted);font-size:.75rem}
.pagination{display:flex;gap:4px}
.pg-btn{background:none;border:1px solid var(--border);color:var(--text);padding:3px 8px;border-radius:4px;cursor:pointer;font-size:.75rem}
.pg-btn:hover,.pg-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
/* ── Snap Browser ── */
.browser{display:flex;height:calc(100vh - 52px)}
.tree-sidebar{width:230px;background:var(--surf);border-right:1px solid var(--border);overflow-y:auto;padding:8px 4px;flex-shrink:0}
.tree-sidebar h3{padding:8px 10px;font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600}
.tree-list{list-style:none}
.tn-label{display:flex;align-items:center;gap:5px;padding:5px 8px;border-radius:5px;cursor:pointer;transition:background .1s}
.tn-label:hover{background:var(--hover)}
.tn-label.active{background:var(--accent-dim);color:var(--accent)}
.tn-arrow,.tn-dot{font-size:.6rem;color:var(--muted);width:10px;flex-shrink:0;text-align:center}
.tn-icon{flex-shrink:0}
.tn-text{flex:1;font-size:.8rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tn-count{background:var(--surf2);color:var(--muted);font-size:.65rem;padding:1px 5px;border-radius:8px;flex-shrink:0}
.tn-children{list-style:none;padding-left:14px}
.snap-grid-area{flex:1;overflow-y:auto;padding:16px}
.grid-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.grid-header h3{font-size:.85rem;font-weight:600;color:var(--muted)}
.snap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.snap-card{background:var(--surf);border:1px solid var(--border);border-radius:8px;overflow:hidden;cursor:pointer;transition:border-color .15s,box-shadow .15s}
.snap-card:hover{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.snap-thumb{width:100%;height:130px;background:var(--surf2);display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}
.snap-thumb img,.snap-thumb video{width:100%;height:100%;object-fit:cover}
.snap-thumb-placeholder{font-size:2rem;color:var(--muted)}
.snap-type-badge{position:absolute;top:6px;right:6px}
.snap-meta{padding:8px 10px}
.snap-date{font-size:.72rem;color:var(--muted)}
.snap-loc{font-size:.7rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px}
.snap-id{font-family:monospace;font-size:.65rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px}
/* ── Conversations ── */
.conv-layout{display:flex;height:calc(100vh - 52px)}
.conv-list-panel{width:280px;background:var(--surf);border-right:1px solid var(--border);overflow-y:auto;flex-shrink:0}
.conv-list-panel h3{padding:12px 14px;font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600;border-bottom:1px solid var(--border)}
.conv-item{padding:11px 14px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s}
.conv-item:hover{background:var(--hover)}
.conv-item.active{background:var(--accent-dim)}
.conv-name{font-size:.85rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.conv-sub{font-size:.72rem;color:var(--muted);margin-top:2px;display:flex;gap:8px;flex-wrap:wrap}
.conv-streak{color:var(--warn)}
.conv-unread{background:var(--accent);color:#fff;font-size:.65rem;padding:1px 5px;border-radius:8px}
.conv-deleted{text-decoration:line-through;opacity:.6}
.msg-panel{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:6px}
.msg-panel-empty{flex:1;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:.875rem}
.msg-row{display:flex;gap:8px;align-items:flex-start;max-width:600px}
.msg-row.me{flex-direction:row-reverse;align-self:flex-end}
.msg-bubble{background:var(--surf2);border:1px solid var(--border);border-radius:12px;padding:8px 12px;max-width:380px;font-size:.8rem}
.msg-row.me .msg-bubble{background:var(--accent-dim);border-color:var(--accent)}
.msg-meta{font-size:.65rem;color:var(--muted);margin-top:3px}
.msg-row.me .msg-meta{text-align:right}
.msg-sender{font-size:.65rem;color:var(--muted);margin-bottom:2px;font-weight:600}
/* ── Address Book ── */
.ab-panel{padding:20px;max-width:1200px;margin:0 auto}
/* ── Modal ── */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:999;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal-box{background:var(--surf);border:1px solid var(--border);border-radius:10px;max-width:90vw;max-height:90vh;overflow:auto;padding:20px;position:relative;min-width:300px}
.modal-close{position:absolute;top:10px;right:14px;background:none;border:none;color:var(--muted);font-size:1.4rem;cursor:pointer;line-height:1}
.modal-close:hover{color:var(--text)}
.modal-media{max-width:78vw;max-height:65vh;display:block;margin:0 auto;border-radius:6px}
.modal-meta{margin-top:12px;font-size:.75rem;color:var(--muted);font-family:monospace;border-top:1px solid var(--border);padding-top:10px;line-height:1.9}
/* ── Utility ── */
.platform-badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.72rem;font-weight:700}
.b-android{background:#4caf50;color:#000}
.b-ios{background:#888;color:#fff}
.empty-state{text-align:center;color:var(--muted);padding:40px;font-size:.875rem}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-left">
    <h1>Snapchat Forensic Report</h1>
    <div class="meta" id="hdr-meta"></div>
  </div>
  <div class="topbar-right">
    <nav class="tab-bar" id="tab-bar"></nav>
    <button class="theme-btn" id="theme-btn" title="Toggle theme">☀</button>
  </div>
</header>

<!-- Overview -->
<div class="tab-panel" id="panel-overview">
  <div class="overview">
    <div class="stats-row" id="stats-row"></div>
    <div class="card" id="map-card" style="display:none">
      <div class="card-hdr"><span id="map-title">GPS Locations</span></div>
      <div id="map"></div>
    </div>
    <div class="card">
      <div class="card-hdr">
        <span>Evidence Table</span>
        <button class="export-btn" onclick="exportCSV()">Export CSV</button>
      </div>
      <div class="card-body">
        <div class="filter-row">
          <input class="filter-input" id="tbl-filter" placeholder="Filter snaps…" oninput="filterTable()">
          <span id="tbl-count" style="color:var(--muted);font-size:.75rem"></span>
        </div>
        <div class="tbl-wrap">
          <table class="etbl" id="etbl">
            <thead>
              <tr>
                <th onclick="sortTable(0)">Snap ID<span class="sort-arrow"></span></th>
                <th onclick="sortTable(1)">Type<span class="sort-arrow"></span></th>
                <th onclick="sortTable(2)">Region<span class="sort-arrow"></span></th>
                <th onclick="sortTable(3)">GPS<span class="sort-arrow"></span></th>
                <th onclick="sortTable(4)">Capture Time<span class="sort-arrow"></span></th>
                <th>Media</th>
              </tr>
            </thead>
            <tbody id="etbl-body"></tbody>
          </table>
        </div>
        <div class="tbl-footer">
          <span id="tbl-info" style="color:var(--muted);font-size:.75rem"></span>
          <div class="pagination" id="tbl-pg"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Snap Browser -->
<div class="tab-panel" id="panel-browser">
  <div class="browser">
    <aside class="tree-sidebar">
      <h3>Browse Snaps</h3>
      <ul class="tree-list" id="snap-tree"></ul>
    </aside>
    <div class="snap-grid-area">
      <div class="grid-header">
        <h3 id="grid-title">All Snaps</h3>
        <span id="grid-count" style="color:var(--muted);font-size:.75rem"></span>
      </div>
      <div class="snap-grid" id="snap-grid"></div>
    </div>
  </div>
</div>

<!-- Conversations -->
<div class="tab-panel" id="panel-conv">
  <div class="conv-layout">
    <div class="conv-list-panel">
      <h3>Conversations</h3>
      <div id="conv-list"></div>
    </div>
    <div class="msg-panel" id="msg-panel">
      <div class="msg-panel-empty">Select a conversation to view messages</div>
    </div>
  </div>
</div>

<!-- Address Book -->
<div class="tab-panel" id="panel-ab">
  <div class="ab-panel">
    <div class="card">
      <div class="card-hdr">
        <span>Address Book — Friends</span>
        <button class="export-btn" onclick="exportFriendsCSV()">Export CSV</button>
      </div>
      <div class="card-body">
        <div class="filter-row">
          <input class="filter-input" id="ab-filter" placeholder="Filter friends…" oninput="filterFriends()">
          <span id="ab-count" style="color:var(--muted);font-size:.75rem"></span>
        </div>
        <div class="tbl-wrap">
          <table class="etbl" id="ab-tbl">
            <thead>
              <tr>
                <th>Username</th><th>Display Name</th><th>User ID</th>
                <th>Snap Score</th><th>Streak</th><th>Streak Expiry</th>
                <th>Snaps Received</th><th>Snaps Sent</th>
                <th>Added Date</th><th>Added Me</th><th>Relationship</th>
              </tr>
            </thead>
            <tbody id="ab-body"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Snap modal -->
<div class="modal-overlay" id="snap-modal" onclick="closeModal(event)">
  <div class="modal-box">
    <button class="modal-close" onclick="document.getElementById('snap-modal').classList.remove('open')">&times;</button>
    <div id="modal-content"></div>
    <div class="modal-meta" id="modal-meta"></div>
  </div>
</div>

<script>
const DATA = __REPORT_DATA__;

/* ─── Utilities ─── */
function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fp(s){ return (s||'').replace(/\\/g,'/'); }
function ms(n){ return n!=null?n.toFixed(6):'—'; }
function debounce(fn,d){ let t; return function(){ clearTimeout(t); t=setTimeout(fn,d); }; }

/* ─── Theme ─── */
(function(){
  const saved = localStorage.getItem('rpt-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
})();
document.getElementById('theme-btn').onclick = function(){
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('rpt-theme', next);
  this.textContent = next === 'dark' ? '☀' : '🌙';
};

/* ─── Tabs ─── */
const TABS = [];
function addTab(id, label, condition){
  if (!condition) return;
  TABS.push({id, label});
}
addTab('overview', 'Overview', true);
addTab('browser', 'Snap Browser', DATA.snaps.length > 0);
addTab('conv', 'Conversations', (DATA.conversations||[]).length > 0);
addTab('ab', 'Address Book', (DATA.friends||[]).length > 0);

function renderTabs(){
  const bar = document.getElementById('tab-bar');
  bar.innerHTML = TABS.map((t,i) =>
    `<button class="tab-btn${i===0?' active':''}" onclick="showTab('${t.id}')">${esc(t.label)}</button>`
  ).join('');
}
function showTab(id){
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('panel-' + id);
  if (panel) panel.classList.add('active');
  TABS.forEach((t,i) => {
    if (t.id === id) document.querySelectorAll('.tab-btn')[i].classList.add('active');
  });
  if (id === 'overview' && DATA.stats.gps_count > 0) initMap();
  if (id === 'browser' && !browserBuilt) buildBrowser();
  if (id === 'conv' && !convBuilt) buildConversations();
  if (id === 'ab' && !abBuilt) buildAddressBook();
}

/* ─── Header ─── */
function initHeader(){
  document.title = 'Report — ' + DATA.case_name;
  const pb = DATA.platform === 'ANDROID'
    ? '<span class="platform-badge b-android">Android</span>'
    : '<span class="platform-badge b-ios">iOS</span>';
  document.getElementById('hdr-meta').innerHTML =
    `<strong>${esc(DATA.case_name)}</strong> &bull; ${pb} &bull; ${esc(DATA.generated_at)}`;
}

/* ─── Stats ─── */
function initStats(){
  const s = DATA.stats;
  const defs = [
    ['Total Snaps',   s.total_snaps],
    ['Images',        s.images],
    ['Videos',        s.videos],
    ['GPS Locations', s.gps_count],
    ['Downloaded',    s.media_downloaded],
    ['Conversations', s.conversations],
    ['Messages',      s.messages],
    ['Friends',       s.friends],
  ].filter(d => d[1] > 0 || d[0]==='Total Snaps');
  document.getElementById('stats-row').innerHTML = defs.map(([l,v]) =>
    `<div class="stat-card"><div class="stat-val">${v}</div><div class="stat-lbl">${l}</div></div>`
  ).join('');
}

/* ─── Map (lazy Leaflet) ─── */
let mapReady=false, leafletLoading=false, mapInstance=null, mapMarkers=[];
function initMap(){
  if (!DATA.stats.gps_count) return;
  document.getElementById('map-card').style.display='';
  document.getElementById('map-title').textContent='GPS Locations ('+DATA.stats.gps_count+' snaps)';
  if (mapReady){ renderMap(); return; }
  if (leafletLoading) return;
  leafletLoading=true;
  const lc=document.createElement('link');
  lc.rel='stylesheet'; lc.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  document.head.appendChild(lc);
  const sc=document.createElement('script');
  sc.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  sc.onload=function(){ mapReady=true; renderMap(); };
  document.head.appendChild(sc);
}
function renderMap(){
  if (mapInstance) return;
  const c = DATA.map_center || [0,0];
  mapInstance = L.map('map').setView(c, DATA.stats.gps_count===1?13:5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    attribution:'© OpenStreetMap contributors', maxZoom:19
  }).addTo(mapInstance);
  DATA.snaps.forEach(function(snap,idx){
    if (snap.latitude==null||snap.longitude==null) return;
    const label = snap.region || snap.snap_id.slice(0,14)+'…';
    const popup = `<b>${esc(label)}</b><br>${esc(snap.capture_time||'Unknown time')}<br>`
                + `<small class="mono">${esc(snap.snap_id.slice(0,20))}…</small>`;
    const m = L.marker([snap.latitude,snap.longitude]).addTo(mapInstance).bindPopup(popup);
    mapMarkers.push({m,idx});
  });
  if (DATA.stats.gps_count>1){
    const fg=L.featureGroup(mapMarkers.map(x=>x.m));
    mapInstance.fitBounds(fg.getBounds().pad(.12));
  }
}
function focusMap(lat,lon,idx){
  showTab('overview');
  setTimeout(function(){
    if (!mapInstance) return;
    document.getElementById('map-card').scrollIntoView({behavior:'smooth',block:'start'});
    setTimeout(function(){
      mapInstance.setView([lat,lon],15);
      const e=mapMarkers.find(x=>x.idx===idx);
      if (e) e.m.openPopup();
    },300);
  },50);
}

/* ─── Evidence Table ─── */
let etblData=[], etblFiltered=[], etblSort={col:-1,asc:true}, etblPage=0;
const PAGE=30;
function initTable(){
  etblData=[...DATA.snaps];
  etblFiltered=[...etblData];
  renderTable();
}
function filterTable(){
  const q=(document.getElementById('tbl-filter').value||'').toLowerCase();
  etblFiltered = q ? etblData.filter(s =>
    (s.snap_id||'').toLowerCase().includes(q)||
    (s.region||'').toLowerCase().includes(q)||
    (s.capture_time||'').toLowerCase().includes(q)||
    (s.format||'').toLowerCase().includes(q)
  ) : [...etblData];
  etblPage=0;
  renderTable();
}
function sortTable(col){
  const ths=document.querySelectorAll('#etbl thead th');
  ths.forEach(t=>{t.classList.remove('sort-asc','sort-desc');});
  if (etblSort.col===col){ etblSort.asc=!etblSort.asc; } else { etblSort.col=col; etblSort.asc=true; }
  ths[col].classList.add(etblSort.asc?'sort-asc':'sort-desc');
  const keys=['snap_id','format','region','latitude','capture_time'];
  etblFiltered.sort((a,b)=>{
    let av=a[keys[col]]||'', bv=b[keys[col]]||'';
    if (col===3){ av=a.latitude||0; bv=b.latitude||0; }
    if (av<bv) return etblSort.asc?-1:1;
    if (av>bv) return etblSort.asc?1:-1;
    return 0;
  });
  etblPage=0; renderTable();
}
function renderTable(){
  const start=etblPage*PAGE, end=start+PAGE;
  const page=etblFiltered.slice(start,end);
  let html='';
  page.forEach(function(snap,i){
    const realIdx=DATA.snaps.indexOf(snap);
    const lat=snap.latitude!=null?snap.latitude.toFixed(6):null;
    const lon=snap.longitude!=null?snap.longitude.toFixed(6):null;
    const gps=lat&&lon
      ?`<span class="gps-link" onclick="focusMap(${snap.latitude},${snap.longitude},${realIdx})">${lat}, ${lon}</span>`
      :'—';
    let typeBadge='';
    if(snap.format==='image_jpeg') typeBadge='<span class="badge badge-img">Image</span>';
    else if(snap.format&&snap.format.includes('video')) typeBadge='<span class="badge badge-vid">Video</span>';
    else typeBadge='<span class="badge badge-chat">'+(snap.format||'Unknown')+'</span>';
    const mediaBt=snap.file_path?`<button class="view-btn" onclick="openSnapModal(${realIdx})">View</button>`:'—';
    const sid=snap.snap_id||'';
    html+=`<tr>
      <td><span class="mono" title="${esc(sid)}">${esc(sid.length>22?sid.slice(0,22)+'…':sid)}</span></td>
      <td>${typeBadge}</td>
      <td>${esc(snap.region||'—')}</td>
      <td>${gps}</td>
      <td>${esc(snap.capture_time||'—')}</td>
      <td>${mediaBt}</td>
    </tr>`;
  });
  document.getElementById('etbl-body').innerHTML=html||'<tr><td colspan="6" class="empty-state">No snaps match the filter.</td></tr>';
  const total=etblFiltered.length;
  document.getElementById('tbl-count').textContent=total+' snap'+(total!==1?'s':'');
  document.getElementById('tbl-info').textContent=
    `Showing ${Math.min(start+1,total)}–${Math.min(end,total)} of ${total}`;
  renderPagination();
}
function renderPagination(){
  const pages=Math.ceil(etblFiltered.length/PAGE);
  let html='';
  if(pages<=1){document.getElementById('tbl-pg').innerHTML='';return;}
  if(etblPage>0) html+=`<button class="pg-btn" onclick="goPage(${etblPage-1})">‹</button>`;
  const lo=Math.max(0,etblPage-2), hi=Math.min(pages,etblPage+3);
  for(let p=lo;p<hi;p++) html+=`<button class="pg-btn${p===etblPage?' active':''}" onclick="goPage(${p})">${p+1}</button>`;
  if(etblPage<pages-1) html+=`<button class="pg-btn" onclick="goPage(${etblPage+1})">›</button>`;
  document.getElementById('tbl-pg').innerHTML=html;
}
function goPage(p){ etblPage=p; renderTable(); document.getElementById('etbl').scrollIntoView({behavior:'smooth',block:'start'}); }

/* ─── Snap Browser ─── */
let browserBuilt=false;
const filterFnMap={};
function buildBrowser(){
  browserBuilt=true;
  const snaps=DATA.snaps;
  const dateMap={}, locMap={};
  snaps.forEach(s=>{
    const d=s.capture_time?s.capture_time.slice(0,7):'Unknown Date';
    (dateMap[d]=dateMap[d]||[]).push(s);
    const l=s.region||(s.latitude!=null?`${s.latitude.toFixed(2)}, ${s.longitude.toFixed(2)}`:'No Location');
    (locMap[l]=locMap[l]||[]).push(s);
  });
  filterFnMap['all']=null;
  filterFnMap['images']=s=>s.format==='image_jpeg';
  filterFnMap['videos']=s=>s.format&&s.format.includes('video');
  const dateNodes=Object.entries(dateMap).sort((a,b)=>b[0].localeCompare(a[0])).map(([k,v])=>{
    const id='dt-'+k.replace(/\W/g,'_');
    filterFnMap[id]=s=>(s.capture_time||'').startsWith(k);
    return {id,icon:'🗓',label:k,count:v.length};
  });
  const locNodes=Object.entries(locMap).sort((a,b)=>b[1].length-a[1].length).map(([k,v])=>{
    const id='lc-'+k.replace(/\W/g,'_');
    filterFnMap[id]=s=>(s.region||(s.latitude!=null?`${s.latitude.toFixed(2)}, ${s.longitude.toFixed(2)}`:'No Location'))===k;
    return {id,icon:'📍',label:k,count:v.length};
  });
  const tree=[
    {id:'all',icon:'📁',label:'All Snaps',count:snaps.length,leaf:true},
    {id:'images',icon:'🖼',label:'Images',count:snaps.filter(s=>s.format==='image_jpeg').length,leaf:true},
    {id:'videos',icon:'🎬',label:'Videos',count:snaps.filter(s=>s.format&&s.format.includes('video')).length,leaf:true},
    {id:'by-date',icon:'📅',label:'By Date',count:null,leaf:false,children:dateNodes},
    {id:'by-loc',icon:'📍',label:'By Location',count:null,leaf:false,children:locNodes},
  ];
  document.getElementById('snap-tree').innerHTML=tree.map(n=>renderTreeNode(n,0)).join('');
  selectTreeNode('all');
}
function renderTreeNode(n,depth){
  const isParent=n.children&&n.children.length>0;
  const countHtml=n.count!=null?`<span class="tn-count">${n.count}</span>`:'';
  const arrow=isParent?'<span class="tn-arrow">▸</span>':'<span class="tn-dot">·</span>';
  const childrenHtml=isParent
    ?`<ul class="tn-children" id="tc-${n.id}" style="display:none">${n.children.map(c=>renderTreeNode(c,depth+1)).join('')}</ul>`
    :'';
  return `<li><div class="tn-label" id="tn-${n.id}" onclick="tnClick('${n.id}',${isParent})">${arrow}<span class="tn-icon">${n.icon}</span><span class="tn-text">${esc(n.label)}</span>${countHtml}</div>${childrenHtml}</li>`;
}
function tnClick(id,isParent){
  if(isParent){
    const el=document.getElementById('tc-'+id);
    const arrow=document.getElementById('tn-'+id).querySelector('.tn-arrow');
    if(el.style.display==='none'){el.style.display='';arrow.textContent='▾';}
    else{el.style.display='none';arrow.textContent='▸';}
  }
  if(id in filterFnMap) selectTreeNode(id);
}
function selectTreeNode(id){
  document.querySelectorAll('.tn-label').forEach(el=>el.classList.remove('active'));
  const lbl=document.getElementById('tn-'+id);
  if(lbl) lbl.classList.add('active');
  const filterFn=filterFnMap[id];
  const filtered=filterFn?DATA.snaps.filter(filterFn):DATA.snaps;
  const labelEl=lbl?lbl.querySelector('.tn-text'):null;
  const label=labelEl?labelEl.textContent:'Snaps';
  document.getElementById('grid-title').textContent=label;
  document.getElementById('grid-count').textContent=filtered.length+' snap'+(filtered.length!==1?'s':'');
  renderSnapGrid(filtered);
}
function renderSnapGrid(snaps){
  if(!snaps.length){
    document.getElementById('snap-grid').innerHTML='<p class="empty-state">No snaps in this category.</p>';
    return;
  }
  document.getElementById('snap-grid').innerHTML=snaps.map(s=>snapCard(s)).join('');
}
function snapCard(snap){
  const idx=DATA.snaps.indexOf(snap);
  const f=fp(snap.file_path||'');
  const isImg=snap.format==='image_jpeg'||(f&&f.endsWith('.jpeg'));
  const isVid=snap.format&&snap.format.includes('video');
  let thumb='';
  if(f){
    thumb=isImg
      ?`<img src="${esc(f)}" loading="lazy" alt="">`
      :`<video src="${esc(f)}"></video>`;
  } else {
    thumb=`<div class="snap-thumb-placeholder">${isVid?'🎬':'📷'}</div>`;
  }
  const typeBadge=isImg?'<span class="badge badge-img snap-type-badge">IMG</span>'
    :isVid?'<span class="badge badge-vid snap-type-badge">VID</span>':'';
  const date=snap.capture_time?snap.capture_time.slice(0,10):'—';
  const loc=snap.region||(snap.latitude!=null?`${snap.latitude.toFixed(2)}, ${snap.longitude.toFixed(2)}`:'');
  return `<div class="snap-card" onclick="openSnapModal(${idx})">
    <div class="snap-thumb">${thumb}${typeBadge}</div>
    <div class="snap-meta">
      <div class="snap-date">${date}</div>
      ${loc?`<div class="snap-loc">📍 ${esc(loc)}</div>`:''}
      <div class="snap-id">${esc((snap.snap_id||'').slice(0,18))}…</div>
    </div>
  </div>`;
}

/* ─── Snap Modal ─── */
function openSnapModal(idx){
  const snap=DATA.snaps[idx];
  const f=fp(snap.file_path||'');
  const isImg=snap.format==='image_jpeg'||(f&&f.endsWith('.jpeg'));
  let html='';
  if(f) html=isImg?`<img src="${esc(f)}" class="modal-media">`:`<video src="${esc(f)}" class="modal-media" controls></video>`;
  else html=`<p style="text-align:center;color:var(--muted);padding:30px">No downloaded media</p>`;
  document.getElementById('modal-content').innerHTML=html;
  document.getElementById('modal-meta').innerHTML=
    `ID: ${esc(snap.snap_id)}<br>Format: ${esc(snap.format||'—')} | Region: ${esc(snap.region||'—')}<br>`+
    `Capture: ${esc(snap.capture_time||'—')}`+(snap.duration?` | Duration: ${snap.duration}s`:'')+
    (snap.latitude!=null?`<br>GPS: ${snap.latitude.toFixed(6)}, ${snap.longitude.toFixed(6)}`:'');
  document.getElementById('snap-modal').classList.add('open');
}
function closeModal(e){ if(e.target===document.getElementById('snap-modal')) document.getElementById('snap-modal').classList.remove('open'); }

/* ─── Conversations ─── */
let convBuilt=false, activeConvId=null;
function buildConversations(){
  convBuilt=true;
  const convs=DATA.conversations||[];
  if(!convs.length){
    document.getElementById('conv-list').innerHTML='<div class="empty-state">No conversations found.</div>';
    return;
  }
  document.getElementById('conv-list').innerHTML=convs.map((c,i)=>{
    const name=c.title||'(Unknown)';
    const del=c.deleted?'conv-deleted':'';
    const unreadHtml=c.unread>0?`<span class="conv-unread">${c.unread}</span>`:'';
    const streakHtml=c.streak>0?`<span class="conv-streak">🔥 ${c.streak}</span>`:'';
    const typeHtml=`<span>${esc(c.conversation_type||'')}</span>`;
    return `<div class="conv-item ${del}" onclick="selectConv('${esc(c.conversation_id)}',${i})" id="ci-${i}">
      <div class="conv-name">${esc(name)} ${unreadHtml}</div>
      <div class="conv-sub">${typeHtml}${streakHtml}<span>${esc(c.last_activity||'')}</span>
        <span>${c.message_count} msg${c.message_count!==1?'s':''}</span></div>
    </div>`;
  }).join('');
}
function selectConv(convId, i){
  document.querySelectorAll('.conv-item').forEach(el=>el.classList.remove('active'));
  const el=document.getElementById('ci-'+i);
  if(el) el.classList.add('active');
  activeConvId=convId;
  const msgs=(DATA.messages||[]).filter(m=>m.conversation_id===convId);
  const panel=document.getElementById('msg-panel');
  if(!msgs.length){
    panel.innerHTML='<div class="msg-panel-empty">No messages recorded for this conversation.</div>';
    return;
  }
  panel.innerHTML=msgs.map(m=>{
    const isMe=!m.sender_id||(DATA.user_id&&m.sender_id===DATA.user_id);
    const dir=isMe?'me':'';
    let badges='';
    if(m.deleted) badges+='<span class="badge badge-del">Deleted</span> ';
    if(m.is_saved) badges+='<span class="badge badge-saved">Saved</span> ';
    const ctype=`<span class="badge badge-chat">${esc(m.content_type_label)}</span>`;
    const meta=`${esc(m.timestamp)}${m.read_timestamp?' · Read: '+esc(m.read_timestamp):''}`;
    return `<div class="msg-row ${dir}">
      <div>
        ${!isMe?`<div class="msg-sender">${esc(m.sender_id||'Unknown')}</div>`:''}
        <div class="msg-bubble">${ctype} ${badges}<span class="mono" style="font-size:.7rem">#${m.message_id}</span></div>
        <div class="msg-meta">${meta}</div>
      </div>
    </div>`;
  }).join('');
  panel.scrollTop=0;
}

/* ─── Address Book ─── */
let abBuilt=false, abData=[];
function buildAddressBook(){
  abBuilt=true;
  abData=DATA.friends||[];
  renderFriends(abData);
  document.getElementById('ab-count').textContent=abData.length+' contact'+(abData.length!==1?'s':'');
}
function filterFriends(){
  const q=(document.getElementById('ab-filter').value||'').toLowerCase();
  const filtered=q?abData.filter(f=>
    (f.username||'').toLowerCase().includes(q)||
    (f.display_name||'').toLowerCase().includes(q)
  ):abData;
  renderFriends(filtered);
  document.getElementById('ab-count').textContent=filtered.length+' contact'+(filtered.length!==1?'s':'');
}
function renderFriends(friends){
  document.getElementById('ab-body').innerHTML=friends.map(f=>`<tr>
    <td class="mono">${esc(f.username)}</td>
    <td>${esc(f.display_name)}</td>
    <td class="mono" style="font-size:.7rem">${esc(f.user_id)}</td>
    <td>${f.snap_score.toLocaleString()}</td>
    <td>${f.streak>0?'🔥 '+f.streak:'—'}</td>
    <td class="mono" style="font-size:.7rem">${esc(f.streak_expiry)||'—'}</td>
    <td>${f.snaps_received.toLocaleString()}</td>
    <td>${f.snaps_sent.toLocaleString()}</td>
    <td class="mono" style="font-size:.7rem">${esc(f.added_date)}</td>
    <td class="mono" style="font-size:.7rem">${esc(f.added_me_date)||'—'}</td>
    <td>${esc(f.relationship)}</td>
  </tr>`).join('')||'<tr><td colspan="11" class="empty-state">No contacts match.</td></tr>';
}

/* ─── CSV Exports ─── */
function exportCSV(){
  const h=['snap_id','format','region','latitude','longitude','capture_time','duration','download_url'];
  const rows=DATA.snaps.map(s=>h.map(k=>{const v=s[k]!=null?String(s[k]):'';return v.includes(',')?'"'+v.replace(/"/g,'""')+'"':v;}).join(','));
  dl([h.join(',')].concat(rows).join('\n'), DATA.case_name+'_snaps.csv');
}
function exportFriendsCSV(){
  const h=['username','display_name','user_id','snap_score','streak','added_date','added_me_date','snaps_received','snaps_sent','relationship'];
  const rows=(DATA.friends||[]).map(f=>h.map(k=>{const v=f[k]!=null?String(f[k]):'';return v.includes(',')?'"'+v.replace(/"/g,'""')+'"':v;}).join(','));
  dl([h.join(',')].concat(rows).join('\n'), DATA.case_name+'_friends.csv');
}
function dl(csv, name){
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
  a.download=name;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
}

/* ─── Boot ─── */
document.addEventListener('DOMContentLoaded', function(){
  initHeader();
  renderTabs();
  showTab('overview');
  initStats();
  initTable();
  if (DATA.stats.gps_count > 0) initMap();
});
</script>
</body>
</html>"""


def generate_report(
    case_name: str,
    platform: str,
    output_path: str,
    snaps: list,
    conversations: list = None,
    messages: list = None,
    friends: list = None,
) -> str:
    """
    Generate a standalone HTML forensic report.

    Returns the path to the written report.html.
    """
    conversations = conversations or []
    messages = messages or []
    friends = friends or []

    gps_snaps = [s for s in snaps if s.get('latitude') is not None and s.get('longitude') is not None]
    map_center = (
        [sum(s['latitude'] for s in gps_snaps) / len(gps_snaps),
         sum(s['longitude'] for s in gps_snaps) / len(gps_snaps)]
        if gps_snaps else None
    )

    report_data = {
        'case_name': case_name,
        'platform': platform,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stats': {
            'total_snaps':      len(snaps),
            'images':           sum(1 for s in snaps if s.get('format') == 'image_jpeg'),
            'videos':           sum(1 for s in snaps if s.get('format') in ('video_hevc', 'video_avc')),
            'gps_count':        len(gps_snaps),
            'media_downloaded': sum(1 for s in snaps if s.get('file_path')),
            'conversations':    len(conversations),
            'messages':         len(messages),
            'friends':          len(friends),
        },
        'map_center': map_center,
        'snaps': [
            {
                'snap_id':      s.get('snap_id', ''),
                'format':       s.get('format', ''),
                'region':       s.get('region', '') or '',
                'latitude':     s.get('latitude'),
                'longitude':    s.get('longitude'),
                'capture_time': s.get('capture_time', '') or '',
                'duration':     s.get('duration'),
                'download_url': s.get('download_url', '') or '',
                'file_path':    s.get('file_path', '') or '',
            }
            for s in snaps
        ],
        'conversations': [
            {
                'conversation_id':   c.get('conversation_id', ''),
                'title':             c.get('title', ''),
                'last_activity':     c.get('last_activity', ''),
                'last_activity_ts':  c.get('last_activity_ts', 0),
                'streak':            c.get('streak', 0),
                'streak_expiry':     c.get('streak_expiry', ''),
                'unread':            c.get('unread', 0),
                'conversation_type': c.get('conversation_type', ''),
                'last_sender':       c.get('last_sender', ''),
                'message_count':     c.get('message_count', 0),
                'deleted':           c.get('deleted', False),
            }
            for c in conversations
        ],
        'messages': [
            {
                'conversation_id':   m.get('conversation_id', ''),
                'message_id':        m.get('message_id', 0),
                'server_message_id': m.get('server_message_id', 0),
                'timestamp':         m.get('timestamp', ''),
                'timestamp_ts':      m.get('timestamp_ts', 0),
                'read_timestamp':    m.get('read_timestamp', ''),
                'sender_id':         m.get('sender_id', ''),
                'content_type':      m.get('content_type', 0),
                'content_type_label':m.get('content_type_label', ''),
                'is_saved':          m.get('is_saved', False),
                'is_viewed':         m.get('is_viewed', False),
                'deleted':           m.get('deleted', False),
            }
            for m in messages
        ],
        'friends': [
            {
                'username':      f.get('username', ''),
                'display_name':  f.get('display_name', ''),
                'user_id':       f.get('user_id', ''),
                'snap_score':    f.get('snap_score', 0),
                'birthday':      f.get('birthday', ''),
                'snaps_received':f.get('snaps_received', 0),
                'snaps_sent':    f.get('snaps_sent', 0),
                'added_date':    f.get('added_date', ''),
                'added_me_date': f.get('added_me_date', ''),
                'streak':        f.get('streak', 0),
                'streak_expiry': f.get('streak_expiry', ''),
                'relationship':  f.get('relationship', ''),
            }
            for f in friends
        ],
    }

    html = HTML_TEMPLATE.replace('__REPORT_DATA__', json.dumps(report_data, indent=2, default=str))
    report_path = os.path.join(output_path, 'report.html')
    with open(report_path, 'w', encoding='utf-8') as fh:
        fh.write(html)

    return report_path
