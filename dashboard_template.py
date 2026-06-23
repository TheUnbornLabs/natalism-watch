# -*- coding: utf-8 -*-
"""Self-contained dashboard HTML. collect.py injects JSON where /*__DATA__*/ sits."""

DASHBOARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Natalism Watch — daily dashboard</title>
<style>
  :root{
    --bg:#0f1117; --panel:#171a23; --panel2:#1f2430; --line:#2a3040;
    --text:#e6e9ef; --muted:#9aa3b2; --accent:#7c5cff;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
  header{padding:20px 24px;border-bottom:1px solid var(--line);
    display:flex;flex-wrap:wrap;align-items:center;gap:14px;
    background:linear-gradient(180deg,#161925,#0f1117);position:sticky;top:0;z-index:5}
  h1{font-size:18px;margin:0;letter-spacing:.3px}
  .meta{color:var(--muted);font-size:12px}
  #refresh{margin-left:auto;background:var(--accent);color:#fff;border:none;cursor:pointer;
    padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600}
  #refresh:hover{filter:brightness(1.1)}
  #refresh:disabled{opacity:.6;cursor:default}
  #refresh.spin{pointer-events:none}
  #toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
    background:var(--panel2);border:1px solid var(--line);color:var(--text);
    padding:10px 18px;border-radius:10px;font-size:13px;opacity:0;transition:opacity .25s;
    pointer-events:none;z-index:20;max-width:80vw}
  #toast.show{opacity:1}
  .controls{display:flex;flex-wrap:wrap;gap:8px;padding:14px 24px;border-bottom:1px solid var(--line);
    align-items:center;background:var(--panel)}
  .tab{padding:7px 14px;border-radius:999px;border:1px solid var(--line);
    background:var(--panel2);color:var(--text);cursor:pointer;font-size:13px;white-space:nowrap}
  .tab.active{border-color:transparent;color:#fff;font-weight:600}
  select,input{background:var(--panel2);border:1px solid var(--line);color:var(--text);
    padding:7px 10px;border-radius:8px;font-size:13px}
  input#search{min-width:200px;flex:1}
  .counts{color:var(--muted);font-size:12px;margin-left:auto}
  main{padding:18px 24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 15px;
    display:flex;flex-direction:column;gap:8px;transition:border-color .15s}
  .card:hover{border-color:#3a445c}
  .badges{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .badge{font-size:11px;padding:2px 8px;border-radius:6px;font-weight:600}
  .stype{font-size:11px;color:var(--muted);border:1px solid var(--line);padding:2px 7px;border-radius:6px}
  .lang{font-size:10px;font-weight:700;letter-spacing:.5px;color:#0f1117;background:var(--muted);
    padding:2px 6px;border-radius:6px}
  .title{font-size:14px;font-weight:600;line-height:1.35;text-decoration:none;color:var(--text)}
  .title:hover{color:#fff;text-decoration:underline}
  .snippet{font-size:12.5px;color:var(--muted);line-height:1.5}
  .foot{display:flex;justify-content:space-between;gap:8px;font-size:11px;color:var(--muted);margin-top:2px}
  .empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:60px 0}
  a.src{color:var(--muted);text-decoration:none}
  a.src:hover{color:var(--text)}
</style>
</head>
<body>
<header>
  <h1>👶 Natalism Watch</h1>
  <span class="meta" id="genmeta"></span>
  <button id="refresh" title="Fetch the latest items from the web">↻ Refresh</button>
</header>

<div class="controls">
  <div id="tabs"></div>
  <select id="lang"><option value="all">All languages</option></select>
  <select id="stype">
    <option value="all">All sources</option>
    <option value="reddit">Reddit</option>
    <option value="news">News</option>
    <option value="academic">Academic / Philosophy</option>
    <option value="twitter">X / Twitter</option>
    <option value="youtube">YouTube</option>
  </select>
  <select id="sort">
    <option value="published">Newest first</option>
    <option value="collected">Recently collected</option>
  </select>
  <input id="search" type="text" placeholder="Search title & text…">
  <span class="counts" id="counts"></span>
</div>

<main id="grid"></main>
<div id="toast"></div>

<script>
let DATA = /*__DATA__*/;
const state = { topic: "all", lang: "all", stype: "all", q: "", sort: "published" };

function buildLangOptions(){
  const sel = document.getElementById("lang");
  const cur = state.lang;
  const langs = DATA.languages || {};
  sel.innerHTML = '<option value="all">All languages</option>' +
    Object.entries(langs).map(([code,m]) =>
      `<option value="${code}">${m.label} (${code})</option>`).join("");
  sel.value = (cur in langs || cur === "all") ? cur : "all";
}

function fmt(iso){
  if(!iso) return "—";
  const d = new Date(iso);
  if(isNaN(d)) return "—";
  const diff = (Date.now()-d.getTime())/86400000;
  const date = d.toLocaleDateString(undefined,{month:"short",day:"numeric"});
  if(diff < 1) return date + " · today";
  if(diff < 2) return date + " · 1d ago";
  if(diff < 30) return date + " · " + Math.floor(diff) + "d ago";
  return date;
}

function buildTabs(){
  const tabs = document.getElementById("tabs");
  const entries = [["all",{label:"All topics",color:"#7c5cff"}]].concat(Object.entries(DATA.topics));
  tabs.innerHTML = "";
  for(const [key,meta] of entries){
    const el = document.createElement("span");
    el.className = "tab" + (state.topic===key?" active":"");
    el.textContent = meta.label;
    if(state.topic===key) el.style.background = meta.color;
    el.onclick = () => { state.topic = key; render(); };
    tabs.appendChild(el);
  }
}

function render(){
  buildTabs();
  buildLangOptions();
  document.getElementById("genmeta").textContent =
    DATA.total + " items · updated " + fmt(DATA.generated_at) + " · last " + DATA.history_days + " days";

  const q = state.q.toLowerCase();
  let items = DATA.items.filter(it=>{
    if(state.topic!=="all" && it.topic!==state.topic) return false;
    if(state.lang!=="all" && it.language!==state.lang) return false;
    if(state.stype!=="all" && it.source_type!==state.stype) return false;
    if(q && !((it.title||"").toLowerCase().includes(q) || (it.snippet||"").toLowerCase().includes(q))) return false;
    return true;
  });

  items.sort((a,b)=>{
    const ka = state.sort==="collected" ? a.collected_at : (a.published_at||a.collected_at);
    const kb = state.sort==="collected" ? b.collected_at : (b.published_at||b.collected_at);
    return (kb||"").localeCompare(ka||"");
  });

  document.getElementById("counts").textContent = items.length + " shown";

  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  if(!items.length){
    grid.innerHTML = '<div class="empty">No items match. Run <code>python collect.py</code> to pull fresh data, or loosen the filters.</div>';
    return;
  }
  for(const it of items){
    const meta = DATA.topics[it.topic] || {label:it.topic,color:"#888"};
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="badges">
        <span class="badge" style="background:${meta.color}22;color:${meta.color}">${meta.label}</span>
        <span class="stype">${it.source_type}</span>
        ${it.language && it.language!=="en" ? `<span class="lang">${(it.language||"").toUpperCase()}</span>` : ""}
      </div>
      <a class="title" href="${it.url}" target="_blank" rel="noopener">${escapeHtml(it.title)||"(untitled)"}</a>
      ${it.snippet?`<div class="snippet">${escapeHtml(it.snippet)}</div>`:""}
      <div class="foot">
        <a class="src" href="${it.url}" target="_blank" rel="noopener">${escapeHtml(it.source_name||it.source_type)}</a>
        <span>${fmt(it.published_at)}</span>
      </div>`;
    grid.appendChild(card);
  }
}

function escapeHtml(s){
  return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
}

document.getElementById("lang").onchange = e => { state.lang = e.target.value; render(); };
document.getElementById("stype").onchange = e => { state.stype = e.target.value; render(); };
document.getElementById("sort").onchange = e => { state.sort = e.target.value; render(); };
document.getElementById("search").oninput = e => { state.q = e.target.value; render(); };

// ---- Refresh button ----
let toastTimer;
function toast(msg, ms){
  const t = document.getElementById("toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toastTimer);
  if(ms) toastTimer = setTimeout(()=>t.classList.remove("show"), ms);
}

// Three modes:
//  - local server (localhost)  -> live collect via /api/refresh
//  - hosted site (github.io..) -> reload to get the latest daily batch
//  - plain file (file://)      -> explain it needs the server
const isLocalServer = ["localhost", "127.0.0.1"].includes(location.hostname);
const isHosted = (location.protocol === "http:" || location.protocol === "https:") && !isLocalServer;
const btn = document.getElementById("refresh");

async function liveRefresh(){
  const before = DATA.total;
  btn.disabled = true; btn.classList.add("spin"); btn.textContent = "⟳ Collecting…";
  toast("Fetching the latest items from the web… this can take ~30–90s.", 0);
  try{
    const res = await fetch("/api/refresh", {method:"POST"});
    if(res.status === 429){ toast("A refresh is already running — give it a moment.", 5000); return; }
    if(!res.ok) throw new Error("server returned " + res.status);
    const fresh = await res.json();
    DATA = fresh;
    render();
    const added = (fresh.new_this_refresh != null) ? fresh.new_this_refresh : (fresh.total - before);
    toast(added > 0 ? `Done — ${added} new item${added===1?"":"s"} added.` : "Done — no new items since last collection.", 5000);
  }catch(err){
    toast("Refresh failed: " + err.message, 6000);
  }finally{
    btn.disabled = false; btn.classList.remove("spin"); btn.textContent = "↻ Refresh";
  }
}

if(isLocalServer){
  btn.onclick = liveRefresh;
} else if(isHosted){
  // Static hosting updates automatically once a day; reload pulls the newest copy.
  btn.textContent = "↻ Reload";
  btn.title = "This page refreshes automatically every day. Click to load the newest copy.";
  btn.onclick = () => { toast("Loading the latest daily collection…", 0); location.reload(); };
} else {
  btn.title = "Live refresh works when served via serve.bat / python serve.py";
  btn.onclick = () => toast("Refresh needs the local server. Close this and run serve.bat (or: python serve.py).", 6000);
}

render();
</script>
</body>
</html>
"""
