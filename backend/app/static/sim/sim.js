/* STORYVERSE desktop simulator: a thin client over the authoritative API.
   Each tab keeps its own session (sessionStorage), so four tabs = four rulers. */
"use strict";

const RES = ["gold", "food", "wood", "stone", "iron"];
const BORDER_RADIUS = 0.22;
const S = {
  token: sessionStorage.getItem("sv_token"),
  worldId: sessionStorage.getItem("sv_world"),
  kingdomId: sessionStorage.getItem("sv_kingdom"),
  dash: null, map: null, catalog: [], selected: null, ws: null, refreshTimer: null, tab: "diplomacy",
  cat: "all", pane: "available", negotiating: null,
  mkt: { res: "wood", amt: 100 },   // Royal Market form: chosen resource and amount
};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => Number(n).toLocaleString();
const nameOf = (id) => (S.map?.kingdoms.find((k) => k.id === id) || {}).name || "?";

// ---------------------------------------------------------------- original art (tools/art/make_art.py)
const KINGDOMS = [
  { name: "Aurelia", title: "The Golden Kingdom", ruler: "King Aldric Solmane", color: "#C6A15B" },
  { name: "Drakoria", title: "The Iron Kingdom", ruler: "Queen Varka Embermane", color: "#813C43" },
  { name: "Sylvara", title: "The Emerald Kingdom", ruler: "Queen Isolde Fernhallow", color: "#3E7C5A" },
  { name: "Valoria", title: "The Maritime Kingdom", ruler: "High King Cassian Valor", color: "#5B6FA8" },
];
const artKey = (name) => String(name || "").toLowerCase();
const medal = (name) => `art/medallions/${artKey(name)}.svg`;
const crest = (name) => `art/crests/${artKey(name)}.svg`;
const icon = (name) => `art/icons/${name}.svg`;
const ico = (name, cls = "") => `<img src="${icon(name)}" alt="${esc(name)}" class="${cls}">`;
const BAND_COLOR = { HOSTILE: "var(--hostile)", COLD: "var(--cold)", PEACEFUL: "var(--peaceful)", FRIENDLY: "var(--friendly)", TRUSTED: "var(--trusted)" };
const IMG = {};   // preloaded images for the map canvas
function img(src) {
  if (!IMG[src]) { IMG[src] = new Image(); IMG[src].onload = () => S.map && drawMap(); IMG[src].src = src; }
  return IMG[src];
}

// ---------------------------------------------------------------- API
async function api(method, path, body, idempotent = false) {
  const headers = { "Content-Type": "application/json" };
  if (S.token) headers.Authorization = `Bearer ${S.token}`;
  if (idempotent) headers["Idempotency-Key"] = crypto.randomUUID();
  const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.status === 401 && S.token) { logout(); throw new Error("Session expired: please log in again"); }
  if (!res.ok) throw new Error(data?.error?.message || `${res.status} ${res.statusText}`);
  return data;
}

function toast(msg, isErr = false, ms = 5000) {
  const box = $("toasts");
  if ([...box.children].some((t) => t.dataset.msg === msg)) return;   // de-duplicate
  while (box.children.length >= 4) box.firstChild.remove();           // never bury the UI
  const el = document.createElement("div");
  el.dataset.msg = msg;
  el.className = "toast" + (isErr ? " err" : "");
  el.innerHTML = msg;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}
const fail = (e) => toast(esc(e.message), true);

function show(view) {
  for (const v of ["authView", "worldsView", "gameView"]) $(v).classList.toggle("hidden", v !== view);
  $("logoutBtn").classList.toggle("hidden", view === "authView");
  $("helpBtn").classList.toggle("hidden", view !== "gameView");
  $("advanceBtn").classList.toggle("hidden", view !== "gameView");
  $("turnMedal").classList.toggle("hidden", view !== "gameView");
  if (view !== "gameView") $("resbar").innerHTML = "";
  if (view === "authView") $("authThrones").innerHTML = KINGDOMS.map((k) => `<div class="throne parchment" style="cursor:default">
    <img class="med" src="${medal(k.name)}" alt=""><div class="t">${k.name}</div><div class="small muted">${k.ruler}</div></div>`).join("");
}

// ---------------------------------------------------------------- auth & worlds
function authMsg(text) { $("authMsg").textContent = text || ""; }

async function auth(kind) {
  const username = $("authUser").value.trim(), password = $("authPass").value;
  // Explain problems before asking the server, in plain words.
  if (!/^[A-Za-z0-9_-]{3,40}$/.test(username)) return authMsg("Username: 3 to 40 letters, numbers, - or _ (no spaces).");
  if (password.length < 8) return authMsg(`Password: at least 8 characters (you typed ${password.length}).`);
  authMsg("");
  try {
    const out = await api("POST", `/auth/${kind}`, { username, password });
    startSession(out.token);
  } catch (e) {
    if (kind === "login" && /Wrong username or password/.test(e.message))
      authMsg("No ruler with that name and password. New here? Press Register (new ruler).");
    else if (kind === "register" && /taken/.test(e.message))
      authMsg("That name is taken. If it is yours, press Log in; otherwise pick another name.");
    else authMsg(e.message);
  }
}

/** One click, no password: a private guest ruler remembered by this browser. */
async function guest() {
  authMsg("");
  try {
    let user = localStorage.getItem("sv_guest_user"), pass = localStorage.getItem("sv_guest_pass"), out = null;
    if (user && pass) { try { out = await api("POST", "/auth/login", { username: user, password: pass }); } catch { out = null; } }
    if (!out) {
      user = "guest_" + crypto.randomUUID().replace(/-/g, "").slice(0, 10);
      pass = crypto.randomUUID();
      out = await api("POST", "/auth/register", { username: user, password: pass });
      localStorage.setItem("sv_guest_user", user); localStorage.setItem("sv_guest_pass", pass);
    }
    startSession(out.token);
  } catch (e) { authMsg(e.message); }
}

async function startSession(token) {
  S.token = token;
  sessionStorage.setItem("sv_token", token);
  try { await loadWorlds(true); } catch (e) { fail(e); }
}

/** One click: a fresh Solo Court (you and three NPC rulers); then pick your throne. */
async function quickStart() {
  try {
    const stamp = new Date().toLocaleDateString(undefined, { day: "numeric", month: "short" });
    await api("POST", "/worlds", { name: `The Continent (${stamp})`, preset: "solo_court" });
    await loadWorlds(false);
    toast("A new realm awaits. Choose your throne: each kingdom plays differently.");
  } catch (e) { fail(e); }
}

function logout() {
  sessionStorage.clear();
  Object.assign(S, { token: null, worldId: null, kingdomId: null });
  if (S.ws) S.ws.close();
  S.dash = null; S.catalog = [];
  show("authView");
}

async function loadWorlds(autoEnter = false) {
  const worlds = await api("GET", "/worlds");
  // Returning ruler with exactly one living reign: skip the menus and walk straight into the court.
  const mine = worlds.filter((w) => w.my_kingdom_id && w.status !== "ENDED");
  if (autoEnter && mine.length === 1) return enterGame(mine[0].id, mine[0].my_kingdom_id);
  show("worldsView");
  $("worldList").innerHTML = worlds.length ? worlds.map((w) => `
    <div class="item"><div class="title">${esc(w.name)} <span class="muted small">· ${esc(w.preset.replace("_", " "))} · turn ${w.turn} of ${w.turn_limit}${w.status === "ENDED" ? " · <b>reign ended</b>" : ""}</span></div>
      ${w.my_kingdom_id
        ? `<div class="actions"><button class="gold" data-enter="${w.id}" data-k="${w.my_kingdom_id}">Return to your court</button></div>`
        : `<div class="throne-grid">${KINGDOMS.map((k) => {
            const open = w.open_seats.includes(k.name);
            return `<button class="throne parchment ${open ? "" : "taken"}" ${open ? `data-join="${w.id}" data-name="${k.name}"` : "disabled"}
              title="${open ? `Rule ${k.name}` : "A human ruler holds this throne"}">
              <img class="med" src="${medal(k.name)}" alt=""><div class="t">${k.name}</div>
              <div class="small muted">${open ? k.ruler : "Throne taken"}</div></button>`;
          }).join("")}</div>`}
    </div>`).join("") : '<p class="muted">No worlds yet. Found one above.</p>';
}

async function createWorld() {
  try {
    await api("POST", "/worlds", { name: $("newWorldName").value.trim() || "The Continent", preset: $("newWorldPreset").value });
    await loadWorlds();
  } catch (e) { fail(e); }
}

async function joinWorld(worldId, name) {
  try {
    const k = await api("POST", "/worlds/join", { world_id: worldId, kingdom_name: name });
    enterGame(worldId, k.id);
  } catch (e) { fail(e); }
}

function enterGame(worldId, kingdomId) {
  const switching = S.kingdomId && S.kingdomId !== kingdomId;
  S.worldId = worldId; S.kingdomId = kingdomId;
  if (switching) S.catalog = [];          // discounts differ per kingdom
  sessionStorage.setItem("sv_world", worldId); sessionStorage.setItem("sv_kingdom", kingdomId);
  show("gameView");
  refresh().then(() => {
    // Once per kingdom: say what winning means before anything else.
    if (!S.dash || S.dash.world.status === "ENDED") return;
    let seen = null;
    try { seen = localStorage.getItem(`sv_intro_${kingdomId}`); } catch { /* storage blocked: show it */ }
    if (!seen) { showHowToWin(); try { localStorage.setItem(`sv_intro_${kingdomId}`, "1"); } catch { /* private mode */ } }
  });
  connectWS();
}

// ---------------------------------------------------------------- data refresh
async function refresh() {
  try {
    const [dash, map] = await Promise.all([
      api("GET", `/kingdoms/${S.kingdomId}/dashboard`),
      api("GET", `/worlds/${S.worldId}/map`),
    ]);
    S.dash = dash; S.map = map;
    if (!S.catalog.length) S.catalog = await api("GET", `/buildings/catalog?kingdom_id=${S.kingdomId}`);
    renderAll();
  } catch (e) { fail(e); }
}
function scheduleRefresh() { clearTimeout(S.refreshTimer); S.refreshTimer = setTimeout(refresh, 250); }

function renderAll() {
  const { world } = S.dash;
  const left = world.turn_limit - world.turn;
  $("turnMedal").classList.toggle("final", world.status !== "ENDED" && left <= 3);
  $("turnMedal").innerHTML = `<span>${world.status === "ENDED" ? "REIGN ENDED" : left <= 3 ? `${left} TURN${left === 1 ? "" : "S"} LEFT` : "TURN"}</span>
    <b>${world.turn}<small> / ${world.turn_limit}</small></b>
    <div class="reign"><i style="width:${Math.min(100, Math.round(100 * world.turn / world.turn_limit))}%"></i></div><span>${esc(world.name)}</span>`;
  $("advanceBtn").disabled = world.status === "ENDED";
  if (world.status === "ENDED") showCoronation();
  renderKingdom(S.dash.kingdom); renderGoal(); renderCatalog(); drawMap(); renderDecrees();
  renderMarket(); renderThreat(); renderArmyNote();
  renderTab(S.tab);
  if (S.negotiating) renderNegotiation();
  const pending = Object.values(S.dash.inbox).reduce((n, a) => n + a.length, 0);
  $("inboxBadge").textContent = pending; $("inboxBadge").classList.toggle("hidden", !pending);
  renderGuide();                       // last: it highlights elements the renders above just rebuilt
}

function renderKingdom(k) {
  $("resbar").innerHTML = RES.map((r) => {
    const d = k.yield_per_turn[r] || 0;
    return `<div class="chip" title="${r}: ${d >= 0 ? "+" : ""}${d} per turn">${ico(r)}<div><b>${fmt(k.resources[r])}</b>
      <span class="d ${d >= 0 ? "pos" : "neg"}">${d >= 0 ? "+" : ""}${d}/turn</span></div></div>`;
  }).join("");
  $("kingdomCard").innerHTML = `<div class="ruler-card"><img class="med" src="${medal(k.name)}" alt="${esc(k.ruler_name)}">
    <div><div class="name"><img class="crest" src="${crest(k.name)}" alt="">${esc(k.name)}</div>
    <div class="sub">${esc(k.ruler_name)}</div><div class="sub">${esc(k.title)}</div></div></div>
    <div class="stats"><div title="Prestige">${ico("prestige")}${k.prestige}</div><div title="Population">${ico("people")}${fmt(k.population)}</div>
    <div title="Soldiers">${ico("soldiers")}${fmt(k.soldiers)}</div></div>`;
}

function costText(cost) { return Object.entries(cost).map(([r, a]) => `${a} ${r}`).join(", "); }
function costHTML(cost) { return Object.entries(cost).map(([r, a]) => `<span class="cost-line">${ico(r)}${fmt(a)}</span>`).join(""); }
function canAfford(cost) { return Object.entries(cost).every(([r, a]) => S.dash.kingdom.resources[r] >= a); }

const CATS = [["all", "All"], ["economy", "Economy"], ["military", "Military"], ["civic", "Civic"], ["housing", "Housing"]];

function renderCatalog() {
  for (const b of document.querySelectorAll("[data-pane]")) b.classList.toggle("gold", b.dataset.pane === S.pane);
  $("catbar").innerHTML = S.pane === "available"
    ? CATS.map(([k, l]) => `<button data-cat="${k}" class="${S.cat === k ? "active" : ""}">${l}</button>`).join("") : "";
  if (S.pane === "current") {
    $("catalog").innerHTML = S.dash.buildings.map((b) => `<div class="tile parchment" data-detail="${b.building_type}" data-bid="${b.id}">
      ${ico(b.building_type)}<div class="nm">${esc(b.label)}</div><div class="lvl">Rank ${b.level}</div></div>`).join("")
      || '<p class="muted" style="grid-column:1/-1;text-align:center">No holdings yet.</p>';
    return refreshGuide();
  }
  $("catalog").innerHTML = S.catalog.filter((b) => S.cat === "all" || b.category === S.cat).map((b) =>
    `<div class="tile parchment ${S.selected === b.building_type ? "sel" : ""} ${canAfford(b.cost) ? "" : "poor"}"
     data-detail="${b.building_type}" title="${esc(b.function)}">${ico(b.building_type)}<div class="nm">${esc(b.label)}</div>
     <div class="c">${esc(costText(b.cost))}</div></div>`).join("");
  refreshGuide();
}

/** Re-apply the guide's highlight after a partial re-render (only once the game is loaded). */
function refreshGuide() { if (S.dash && !$("gameView").classList.contains("hidden")) renderGuide(); }

function renderBuildings() { renderCatalog(); }

function openBuildDetail(type, ownedId) {
  const b = S.catalog.find((c) => c.building_type === type);
  const owned = ownedId && S.dash.buildings.find((x) => x.id === ownedId);
  const next = owned && b.upgrade_costs[owned.level + 1];
  const fx = (obj, sign) => Object.entries(obj).map(([r, a]) => `<span class="cost-line">${ico(r)}<b class="${sign > 0 ? "pos" : "neg"}">${sign > 0 ? "+" : "-"}${a}</b></span>`).join("");
  const ok = canAfford(b.cost);
  $("buildDetail").innerHTML = `<div class="ornate bdetail"><button class="close-x" data-close="buildDetail">✕</button>
    <div class="art parchment">${ico(b.building_type)}</div>
    <div><h2>${esc(b.label)}${owned ? ` <span class="muted" style="font-size:16px">Rank ${owned.level}</span>` : ""}</h2>
      <p class="lore">${esc(b.lore || "")}</p><p>${esc(b.function)}.</p>
      <div class="effects">${fx(b.production, 1) || '<span class="muted">No production</span>'}</div>
      <div class="muted small">Upkeep per turn</div><div class="effects">${fx(b.maintenance, -1) || '<span class="muted">None</span>'}</div>
      ${owned ? (next
        ? `<div class="muted small">Upgrade to rank ${owned.level + 1}</div><div class="effects">${costHTML(next)}</div>
           <button class="gold" data-upgrade="${owned.id}" ${canAfford(next) ? "" : "disabled"} style="width:100%;padding:12px;font-size:16px">
           ${canAfford(next) ? "Upgrade" : "Not enough resources"}</button>`
        : '<p class="muted">At the highest rank.</p>')
      : `<div class="muted small">Cost</div><div class="effects">${costHTML(b.cost)}</div>
      <button class="gold" data-build="${b.building_type}" ${ok ? "" : "disabled"} style="width:100%;padding:12px;font-size:16px">
        ${ok ? "Build: then click inside your borders" : "Not enough resources"}</button>`}</div></div>`;
  $("buildDetail").classList.remove("hidden");
}

function renderBuildings() {
  $("myBuildings").innerHTML = S.dash.buildings.map((b) => {
    const cat = S.catalog.find((c) => c.building_type === b.building_type);
    const next = cat && cat.upgrade_costs[b.level + 1];
    return `<div class="row" style="justify-content:space-between"><span>${esc(b.label)} <span class="muted">L${b.level}</span></span>
      ${next ? `<button class="small" data-upgrade="${b.id}" ${canAfford(next) ? "" : "disabled"} title="${esc(costText(next))}">Upgrade</button>` : '<span class="muted small">max</span>'}</div>`;
  }).join("");
}

// ---------------------------------------------------------------- map
function drawMap() {
  const cv = $("map"), g = cv.getContext("2d"), W = cv.width;
  const P = (v) => v * W;
  g.clearRect(0, 0, W, W);
  const bg = g.createRadialGradient(W * 0.45, W * 0.4, W * 0.05, W / 2, W / 2, W * 0.78);
  bg.addColorStop(0, "#4f6b45"); bg.addColorStop(0.6, "#2f4a36"); bg.addColorStop(1, "#14231c");
  g.fillStyle = bg; g.fillRect(0, 0, W, W);
  // the sea around the continent and a few hills: a hand-drawn campaign map feel
  g.save(); g.strokeStyle = "#8fb3c766"; g.lineWidth = 2;
  for (let i = 0; i < 4; i++) { g.beginPath(); g.ellipse(W / 2, W / 2, W * (0.47 + i * 0.012), W * (0.46 + i * 0.012), 0, 0, Math.PI * 2); g.stroke(); }
  g.fillStyle = "#00000022";
  for (const [x, y, r] of [[0.5, 0.5, 0.07], [0.42, 0.18, 0.05], [0.58, 0.82, 0.05], [0.12, 0.5, 0.04], [0.88, 0.5, 0.04]]) {
    g.beginPath(); g.moveTo(P(x - r), P(y + r / 2)); g.lineTo(P(x), P(y - r / 2)); g.lineTo(P(x + r), P(y + r / 2)); g.fill();
  }
  g.restore();
  const byId = Object.fromEntries(S.map.kingdoms.map((k) => [k.id, k]));
  // territories
  for (const k of S.map.kingdoms) {
    g.beginPath(); g.arc(P(k.map_x), P(k.map_y), P(BORDER_RADIUS), 0, Math.PI * 2);
    g.fillStyle = k.color + (k.id === S.kingdomId ? "55" : "30"); g.fill();
    g.lineWidth = k.id === S.kingdomId && S.selected ? 4 : 2;
    g.strokeStyle = k.id === S.kingdomId && S.selected ? "#C6A15B" : k.color; g.stroke();
  }
  // treaty ribbons
  const ribbon = (a, b, color, dash) => {
    g.save(); g.setLineDash(dash); g.lineWidth = 5; g.strokeStyle = color;
    g.beginPath(); g.moveTo(P(a.map_x), P(a.map_y)); g.lineTo(P(b.map_x), P(b.map_y)); g.stroke(); g.restore();
  };
  for (const a of S.map.treaties.alliances) ribbon(byId[a.a], byId[a.b], "#5b8fc9cc", []);
  for (const w of S.map.treaties.wars) ribbon(byId[w.attacker], byId[w.defender], "#d0434dcc", [14, 10]);
  for (const p of S.map.treaties.passages || []) ribbon(byId[p.grantor], byId[p.grantee], "#e9cf8aaa", [3, 9]);
  // buildings
  for (const b of S.map.buildings) {
    const k = byId[b.kingdom_id];
    const s = 26 + b.level * 5;
    g.beginPath(); g.arc(P(b.x), P(b.z), s * 0.52, 0, Math.PI * 2);
    g.fillStyle = "#1a140dcc"; g.fill(); g.lineWidth = 2; g.strokeStyle = k.color; g.stroke();
    const pic = img(icon(b.building_type));
    if (pic.complete && pic.naturalWidth) g.drawImage(pic, P(b.x) - s * 0.4, P(b.z) - s * 0.4, s * 0.8, s * 0.8);
  }
  // capitals: the kingdom's crest and banner name
  for (const k of S.map.kingdoms) {
    const c = img(crest(k.name)), w = 52, h = 62;
    g.save(); g.shadowColor = "#000"; g.shadowBlur = 12;
    if (c.complete && c.naturalWidth) g.drawImage(c, P(k.map_x) - w / 2, P(k.map_y) - h / 2, w, h);
    g.restore();
    const label = k.name + (k.is_npc ? "" : " ♔");
    g.font = "bold 22px Cinzel"; g.textAlign = "center"; g.textBaseline = "middle";
    const tw = g.measureText(label).width + 26;
    g.fillStyle = "#1a140de6"; g.strokeStyle = "#d6b066"; g.lineWidth = 2;
    g.beginPath(); g.roundRect(P(k.map_x) - tw / 2, P(k.map_y) - 66, tw, 30, 6); g.fill(); g.stroke();
    g.fillStyle = k.id === S.kingdomId ? "#fbe9ad" : "#ece2cc"; g.fillText(label, P(k.map_x), P(k.map_y) - 50);
  }
  $("placeHint").classList.toggle("hidden", !S.selected);
  if (S.selected) $("placeHint").textContent = `Placing: ${S.catalog.find((c) => c.building_type === S.selected).label} (Esc to cancel)`;
}

async function onMapClick(ev) {
  const cv = $("map"), r = cv.getBoundingClientRect();
  const x = +((ev.clientX - r.left) / r.width).toFixed(4), z = +((ev.clientY - r.top) / r.height).toFixed(4);
  if (!S.selected) return;
  try {
    const b = await api("POST", "/buildings", { kingdom_id: S.kingdomId, building_type: S.selected, x, z }, true);
    toast(`${esc(b.label)} built.`);
    S.selected = null;
    await refresh();
  } catch (e) { fail(e); }
}

// ---------------------------------------------------------------- tabs
function renderTab(tab) {
  S.tab = tab;
  for (const b of $("tabs").querySelectorAll("button")) b.classList.toggle("active", b.dataset.tab === tab);
  for (const t of ["diplomacy", "inbox", "council", "treasury", "letters", "chronicle", "leaders"]) $(`tab-${t}`).classList.toggle("hidden", t !== tab);
  ({ diplomacy: renderDiplomacy, inbox: renderInbox, council: renderCouncil, treasury: renderTreasury, letters: renderLetters,
     chronicle: renderChronicle, leaders: renderLeaders })[tab]();
  refreshGuide();
}

function decisionHTML(d) {
  if (!d) return "";
  return `<div class="decision"><b>${esc(d.summary)}</b><ul>${d.reasons.map((r) =>
    `<li class="${r.value >= 0 ? "pos" : "neg"}">${r.value >= 0 ? "+" : ""}${r.value} ${esc(r.label)}</li>`).join("")}</ul></div>`;
}

const trendHTML = (r) => r.trend > 0 ? '<span class="pos">▲</span>' : r.trend < 0 ? '<span class="neg">▼</span>' : "";

function renderDiplomacy() {
  $("tab-diplomacy").innerHTML = councilWhisper() + S.dash.relations.map((r) => `<div class="item">
      <div class="court"><img class="med" src="${medal(r.name)}" alt="">
        <div><div class="row" style="justify-content:space-between"><span class="nm" style="color:${esc(r.color)}">${esc(r.name)}</span>
          <span><span class="band ${r.band}">${r.band}</span> <b>${r.standing}</b> ${trendHTML(r)}</span></div>
        <div class="muted small">${esc(r.ruler_name)}${r.is_npc ? " · NPC ruler" : " · human ruler"}${r.alliance ? " · <b class='pos'>Allied</b>" : ""}${r.war_id ? " · <b class='neg'>AT WAR</b>" : ""}</div>
        <div class="gauge"><div class="needle" style="left:${(r.standing + 100) / 2}%"></div></div></div></div>
      <div class="actions"><button class="gold" data-negotiate="${r.kingdom_id}" style="flex:1">Open negotiations</button>
        <button data-act="letter" data-k="${r.kingdom_id}"><img src="${icon("letter")}" alt="" style="width:18px;vertical-align:-4px"> Letter</button></div></div>`).join("");
}

// ---------------------------------------------------------------- royal decrees (objectives)
const DECREE_ICON = { buildings: null, level: "watchtower", resource: "gold", population: "people", trades: "trade",
  band: "ally", battles_won: "war", alliances: "ally" };

function renderDecrees() {
  const list = S.dash.decrees || [];
  $("decrees").classList.toggle("hidden", !list.length);
  $("decrees").innerHTML = `<h4>${ico("decree", "")} Royal Decrees</h4>`.replace('class=""', 'style="width:20px;vertical-align:-4px"') +
    list.map((d) => {
      const iconName = d.kind === "buildings" ? d.target : d.kind === "resource" ? d.target : DECREE_ICON[d.kind] || "decree";
      const reward = Object.entries(d.reward).map(([r, v]) => `+${fmt(v)} ${r}`).join(", ");
      return `<div class="decree">${ico(iconName)}<div class="g"><b>${esc(d.title)}</b>${esc(d.goal)}
        <div class="bar"><i style="width:${Math.round(100 * d.progress / d.need)}%"></i></div>
        <span class="muted small">Reward: ${esc(reward)}</span></div>
        ${d.complete ? `<button class="gold" data-claim="${d.key}">Claim</button>` : `<span class="n">${fmt(d.progress)}/${fmt(d.need)}</span>`}</div>`;
    }).join("");
}

async function claimDecree(key) {
  try {
    const r = await api("POST", `/decrees/${key}/claim`, { kingdom_id: S.kingdomId });
    guideMark("answer");
    toast(`<b>Decree fulfilled: ${esc(r.title)}</b><br>The crown receives ${Object.entries(r.reward).map(([k, v]) => `${fmt(v)} ${k}`).join(", ")}.`);
    await refresh();
  } catch (e) { fail(e); }
}

// ---------------------------------------------------------------- royal council (advisers)
function renderCouncil() {
  const c = S.dash.council || [];
  $("tab-council").innerHTML = `<h3>The Royal Council</h3>` + (c.map((a) => `<div class="item adviser u${a.urgency}">
      <img class="med" src="${medal(a.portrait)}" alt=""><div><div class="nm">${esc(a.name)}</div><div class="role">${esc(a.role)}</div>
      <div class="say parchment">"${esc(a.advice)}"</div></div></div>`).join("") || '<p class="muted">Your council has nothing to say.</p>');
}

function councilWhisper() {
  const a = (S.dash.council || [])[0];
  return a ? `<div class="council-whisper item"><img src="${medal(a.portrait)}" alt=""><div><b>${esc(a.name)}:</b> "${esc(a.advice)}"</div></div>` : "";
}

// ---------------------------------------------------------------- map hover info
function onMapHover(ev) {
  if (!S.map) return;
  const r = $("map").getBoundingClientRect();
  const x = (ev.clientX - r.left) / r.width, z = (ev.clientY - r.top) / r.height;
  const near = (a, b) => Math.hypot(a - x, b - z);
  const k = S.map.kingdoms.find((k) => near(k.map_x, k.map_y) < 0.045);
  const b = S.map.buildings.find((b) => near(b.x, b.z) < 0.022);
  const land = S.map.kingdoms.find((k) => near(k.map_x, k.map_y) < BORDER_RADIUS);
  let html;
  if (b) {
    const owner = S.map.kingdoms.find((k) => k.id === b.kingdom_id);
    const c = S.catalog.find((c) => c.building_type === b.building_type);
    html = `${ico(b.building_type)}<div class="h">${esc(b.label)}</div><div class="k">Rank ${b.level} · ${esc(owner?.name)}</div><div class="k">${esc(c?.function || "")}</div>`;
  } else if (k) {
    html = `<img src="${crest(k.name)}" alt=""><div class="h">${esc(k.name)}</div><div class="k">${k.is_npc ? "NPC ruler" : "Human ruler"}</div>`;
  } else if (land) {
    html = `${ico("farm")}<div class="h">Lands of ${esc(land.name)}</div><div class="k">${land.id === S.kingdomId ? "Your borders: you may build here" : "Foreign soil"}</div>`;
  } else {
    html = `${ico("passage")}<div class="h">Wild country</div><div class="k">Unclaimed forest and hills</div>`;
  }
  $("hoverInfo").innerHTML = html; $("hoverInfo").classList.remove("hidden");
}

// ---------------------------------------------------------------- turn report ("Dawn of turn N")
function snapshot() {
  const k = S.dash.kingdom, row = S.dash.leaderboard.find((r) => r.kingdom_id === S.kingdomId);
  return { turn: S.dash.world.turn, res: { ...k.resources }, pop: k.population, prestige: k.prestige, rank: row?.rank };
}

async function showTurnReport(before) {
  const k = S.dash.kingdom, w = S.dash.world, now = snapshot();
  let events = [];
  try { events = (await api("GET", `/kingdoms/${S.kingdomId}/since?turn=${before.turn}`)).chronicle || []; } catch { /* report without news */ }
  const delta = (a, b) => { const d = b - a; return `<b class="${d >= 0 ? "pos" : "neg"}">${d >= 0 ? "+" : ""}${fmt(d)}</b>`; };
  const envoys = Object.values(S.dash.inbox).reduce((n, a) => n + a.length, 0);
  const ready = (S.dash.decrees || []).filter((d) => d.complete).length;
  const left = w.turn_limit - w.turn;
  $("turnReport").innerHTML = `<div class="ornate report"><button class="close-x" data-close="turnReport">✕</button>
    <div class="muted small" style="text-align:center">THE HERALD REPORTS</div>
    <h2>Dawn of Turn ${w.turn}${left <= 3 ? ` <span class="warn">${left} turn${left === 1 ? "" : "s"} to the coronation</span>` : ""}</h2>
    <div class="ledger">${RES.map((r) => `<div>${ico(r)}${fmt(now.res[r])}<span>${delta(before.res[r], now.res[r])}</span></div>`).join("")}
      <div>${ico("people")}${fmt(now.pop)}<span>${delta(before.pop, now.pop)}</span></div>
      <div>${ico("prestige")}${now.prestige}<span>${delta(before.prestige, now.prestige)}</span></div></div>
    ${now.rank ? `<p style="text-align:center">You stand <b>#${now.rank}</b> of 4 in prestige${before.rank && before.rank !== now.rank ? ` (was #${before.rank})` : ""}.</p>` : ""}
    <h3>In the realm</h3>
    ${events.length ? `<div class="news">${events.slice(-5).reverse().map((e) => `<div class="chron parchment imp${e.importance}"><div class="t">${esc(e.title)}</div><div class="small">${esc(e.description)}</div></div>`).join("")}</div>`
      : '<p class="muted" style="text-align:center">A quiet season across the realm.</p>'}
    <div class="report-actions">
      ${envoys ? `<button class="gold" data-goto="inbox">${envoys} envoy${envoys > 1 ? "s" : ""} await your answer</button>` : ""}
      ${ready ? `<button class="gold" data-close="turnReport">${ready} decree${ready > 1 ? "s" : ""} ready to claim</button>` : ""}
      <button data-close="turnReport">Continue your reign</button></div></div>`;
  $("toasts").innerHTML = "";                 // the report replaces this turn's pile of toasts
  $("turnReport").classList.remove("hidden");
}

// ---------------------------------------------------------------- the coronation (end of the reign)
function showCoronation() {
  const c = S.dash.world.coronation;
  if (!c || S.coronationShown === S.worldId) return;
  S.coronationShown = S.worldId;
  const board = S.dash.leaderboard, me = board.find((r) => r.kingdom_id === S.kingdomId), won = me?.rank === 1;
  $("turnReport").innerHTML = `<div class="ornate report coronation"><button class="close-x" data-close="turnReport">✕</button>
    <div class="muted small" style="text-align:center">THE REIGN IS OVER</div>
    <h2>${esc(c.title)}</h2>
    <img class="med big" src="${medal(board[0].name)}" alt="">
    <p class="verdict">${won ? "Long live the High Monarch: <b>you</b> have won the realm!" : `You finished <b>#${me?.rank}</b> of ${board.length}. ${esc(board[0].ruler_name)} wears the High Crown.`}</p>
    <p class="small muted" style="text-align:center">${esc(c.description)}</p>
    <div class="final">${board.map((r) => `<div class="${r.kingdom_id === S.kingdomId ? "me" : ""}"><span class="rank">${r.rank}</span>
      <img src="${medal(r.name)}" alt=""><b>${esc(r.name)}</b><span>${r.prestige}</span></div>`).join("")}</div>
    <div class="report-actions"><button class="gold" data-newreign>Begin a new reign</button><button data-close="turnReport">Stay and look around</button></div></div>`;
  $("turnReport").classList.remove("hidden");
}

// ---------------------------------------------------------------- the goal: the race for the High Crown
// What each prestige category is made of (server: prestige_service.compute) and how to raise it.
const PRESTIGE_HELP = [
  ["economic", "Economic", "the value of your stockpile (iron and stone count most), minus debts, plus interest earned", "Hoard, lend at interest, avoid debt"],
  ["military", "Military", "soldiers, plus 60 for every battle won", "Barracks and recruits; win battles (defending counts)"],
  ["diplomatic", "Diplomatic", "50 per alliance, 12 per trade, 20 per loan honoured, plus your average standing", "Trade often, make allies, keep your word"],
  ["development", "Development", "20 per building rank, plus 40 per Academy rank", "Build and upgrade; Academies count double"],
  ["welfare", "Welfare", "your people, Hospitals, Mansions and a full granary", "Houses, Taverns, Hospitals; never let food run out"],
];

function myRow() { return (S.dash.leaderboard || []).find((r) => r.kingdom_id === S.kingdomId); }

function renderGoal() {
  const board = S.dash.leaderboard || [], me = myRow(), w = S.dash.world;
  if (!me || !board.length) { $("goalCard").innerHTML = ""; return; }
  const left = Math.max(0, w.turn_limit - w.turn), top = board[0], next = board[me.rank - 2];
  const line = w.status === "ENDED" ? (me.rank === 1 ? "You were crowned High Monarch." : `The reign is over: you finished #${me.rank}.`)
    : me.rank === 1 ? `You lead ${esc(board[1]?.name || "")} by <b>${me.prestige - (board[1]?.prestige || 0)}</b> prestige.`
    : `<b>${next.prestige - me.prestige}</b> prestige behind ${esc(next.name)} (#${next.rank})${me.rank > 2 ? `, ${top.prestige - me.prestige} behind the leader` : ""}.`;
  // Your weakest category is usually the cheapest place to gain (diminishing returns at the top).
  const weak = PRESTIGE_HELP.map((p) => [p, me.breakdown[p[0]] || 0]).sort((a, b) => a[1] - b[1])[0];
  $("goalCard").innerHTML = `<div class="rank">Rank #${me.rank} of ${board.length} · ${me.prestige} prestige</div>
    <div>${line}</div>
    <div class="bar" title="Your prestige against the leader's"><i style="width:${Math.round(100 * me.prestige / Math.max(1, top.prestige))}%"></i></div>
    ${w.status === "ENDED" ? "" : `<div class="muted small">${left} turn${left === 1 ? "" : "s"} left. Most prestige at turn ${w.turn_limit} wins the crown.
      Weakest: <b>${weak[0][1]}</b> (${weak[1]}): ${esc(weak[0][3].toLowerCase())}.</div>`}`;
}

function showHowToWin() {
  const w = S.dash.world, k = S.dash.kingdom;
  $("infoOverlay").innerHTML = `<div class="ornate info"><button class="close-x" data-close="infoOverlay">✕</button>
    <h2>How to Win the High Crown</h2>
    <p class="lead">You rule ${esc(k.name)}, ${esc(k.title)}. The other three courts are run by the computer, each with its own temper.</p>
    <p><b>The goal:</b> after <b>${w.turn_limit} turns</b>, the ruler with the most <b>prestige</b> is crowned High Monarch. You are on turn ${w.turn}.</p>
    <b>Each turn</b>
    <ol>
      <li><b>Build</b> (left panel): pick a building, press Build, then click your land near your capital. Buildings produce every turn and can be upgraded.</li>
      <li><b>Short of wood or stone?</b> Buy it at the <b>Royal Market</b> (left panel, needs a Market). Gold is for spending.</li>
      <li><b>Deal with the courts</b> (Courts tab): trade, gift, lend, ally. NPCs show their reasons when they say yes or no.</li>
      <li><b>Claim Royal Decrees</b> (bottom right of the map) for free resources.</li>
      <li><b>End Turn</b> (red seal, or press E): everything produces, the rival courts move, and the herald reports.</li>
    </ol>
    <p><b class="neg">Beware Drakoria.</b> When it outguns you, Queen Varka demands tribute with a deadline. Pay it, or raise your defence (soldiers, Watchtowers, an ally with mutual defence) until she backs down. Ignore her and her army comes for your gold.</p>
    <b>Prestige comes from five things</b> (each has diminishing returns, so balance wins):
    <div class="cats">${PRESTIGE_HELP.map(([, label, what]) => `<div><b>${label}</b>: ${esc(what)}</div>`).join("")}</div>
    <div class="go"><button class="gold" data-close="infoOverlay">Begin my reign</button></div></div>`;
  $("infoOverlay").classList.remove("hidden");
}

// ---------------------------------------------------------------- Royal Market (gold buys materials)
function renderMarket() {
  const m = S.dash.market, box = $("market");
  if (!m) { box.innerHTML = ""; return; }
  if (box.contains(document.activeElement)) return;     // never rebuild the form under the ruler's cursor
  if (!m.open) {
    box.innerHTML = `<div class="market"><p class="muted small closed">Build a <b>Market</b> to buy wood, stone, iron and food with gold.</p></div>`;
    return;
  }
  const sel = S.mkt.res, price = m.prices[sel], amt = Math.max(1, Math.min(S.mkt.amt || 1, m.units_left || 1));
  const have = S.dash.kingdom.resources;
  box.innerHTML = `<div class="market">
    <div class="prices">${Object.entries(m.prices).map(([r, p]) => `<div title="${r}: buy ${p.buy} gold, sell ${p.sell} gold">${ico(r)}${p.buy}<span class="muted">/${p.sell}</span></div>`).join("")}</div>
    <div class="row"><select id="mktRes">${Object.keys(m.prices).map((r) => `<option ${r === sel ? "selected" : ""}>${r}</option>`).join("")}</select>
      <input id="mktAmt" type="number" min="1" max="${m.units_left}" value="${amt}"></div>
    <div class="row" style="margin-top:6px">
      <button class="gold" data-mkt="buy" ${m.units_left && have.gold >= price.buy * amt ? "" : "disabled"}>Buy for ${fmt(price.buy * amt)} gold</button>
      <button data-mkt="sell" ${m.units_left && have[sel] >= amt ? "" : "disabled"}>Sell for ${fmt(price.sell * amt)}</button></div>
    <div class="muted small" style="margin-top:4px">Gold per unit: buy / sell. ${m.units_left} of ${m.units_per_turn} units left this turn (upgrade the Market for more).</div></div>`;
  $("mktRes").onchange = (e) => { S.mkt.res = e.target.value; e.target.blur(); renderMarket(); };
  $("mktAmt").oninput = (e) => { S.mkt.amt = +e.target.value; };
  $("mktAmt").onchange = (e) => { S.mkt.amt = +e.target.value; e.target.blur(); renderMarket(); };
}

async function marketTrade(side) {
  const amount = Math.floor(+($("mktAmt")?.value || S.mkt.amt));
  if (!(amount > 0)) return toast("Enter how many units to trade.", true);
  try {
    const r = await api("POST", "/market", { kingdom_id: S.kingdomId, resource: S.mkt.res, amount, side }, true);
    toast(`${side === "buy" ? "Bought" : "Sold"} ${fmt(r.amount)} ${r.resource} for ${fmt(r.gold)} gold.`);
    document.activeElement?.blur();
    await refresh();
  } catch (e) { fail(e); }
}

// ---------------------------------------------------------------- ultimatums (Drakoria's demands)
function renderThreat() {
  const list = S.dash.ultimatums || [], box = $("threat");
  if (!list.length || S.dash.world.status === "ENDED") { box.classList.add("hidden"); return; }
  const u = list[0];
  const when = u.turns_left <= 0 ? "now" : `in ${u.turns_left} End Turn${u.turns_left === 1 ? "" : "s"}`;
  box.innerHTML = `<h4>${ico("war")} Ultimatum from ${esc(u.from)}</h4>
    <div class="small">${esc(u.ruler)} demands <b>${fmt(u.amount)} gold</b> by turn ${u.deadline_turn}. Her army marches ${when} if it is not paid.</div>
    ${u.paid ? `<div class="small pos">Paid so far: ${fmt(u.paid)} of ${fmt(u.amount)}.</div>` : ""}
    <div class="meter"><span>Your defence: <b class="${u.safe ? "pos" : "neg"}">${fmt(u.your_defense)}</b></span>
      <span>Needed to deter: <b>${fmt(u.defense_needed)}</b></span><span>Their army: ~${fmt(u.their_army)}</span></div>
    <div class="small ${u.safe ? "pos" : "muted"}">${u.safe ? "Your defences are strong enough: she will not dare attack." :
      "Defence = (soldiers + allies' help) × watchtower bonus + 50 for your walls."}</div>
    <div class="actions">
      ${u.owed ? `<button class="gold" data-tribute="${u.from_id}" data-amt="${u.owed}" ${S.dash.kingdom.resources.gold >= u.owed ? "" : "disabled"}>Pay ${fmt(u.owed)} gold</button>` : ""}
      <button data-defend>How to defend</button></div>`;
  box.classList.remove("hidden");
}

async function payTribute(toId, amount) {
  try {
    await api("POST", "/gifts", { kingdom_id: S.kingdomId, target_id: toId, gold: amount }, true);
    toast(`Tribute of ${fmt(amount)} gold sent. Drakoria's banners stay furled.`);
    await refresh();
  } catch (e) { fail(e); }
}

function renderArmyNote() {
  const has = (t) => S.dash.buildings.some((b) => b.building_type === t);
  const barracks = S.dash.buildings.filter((b) => b.building_type === "barracks").reduce((n, b) => n + b.level, 0);
  $("recruitBtn").disabled = !barracks;
  $("armyNote").innerHTML = barracks
    ? `Up to ${barracks * 20} recruits a turn (10 gold, 2 iron, 1 food each).${has("watchtower") ? "" : " A Watchtower adds +25% to your defence."}`
    : "Build Barracks to train soldiers. A Watchtower adds +25% defence even without them.";
}

// ---------------------------------------------------------------- first-steps guide
const GUIDE = [
  { key: "build", text: "Build something inside your borders: pick a Farm or Houses on the left, press Build, then click your land.",
    target: () => document.querySelector('#catalog .tile[data-detail="farm"], #catalog .tile') },
  { key: "turn", text: "End your turn (the red seal, or press E). Your fields produce and the other courts make their moves.",
    target: () => $("advanceBtn") },
  { key: "court", text: "Open negotiations with a neighbouring court: trade, gifts, passage, alliances.",
    target: () => document.querySelector("[data-negotiate]") },
  { key: "answer", text: "Answer an envoy (Envoys tab) or claim a Royal Decree reward on the map.",
    target: () => document.querySelector('[data-claim], [data-tab="inbox"]') },
];
function guideState() {
  try { return JSON.parse(localStorage.getItem(`sv_guide_${S.kingdomId}`) || "{}"); } catch { return {}; }
}
function guideMark(key) {
  const g = guideState(); if (g[key]) return;
  g[key] = true;
  try { localStorage.setItem(`sv_guide_${S.kingdomId}`, JSON.stringify(g)); } catch { /* private mode */ }
  renderGuide();
}
function renderGuide() {
  for (const el of document.querySelectorAll(".pulse")) el.classList.remove("pulse");
  const g = guideState();
  if (!g.start) { g.start = { buildings: S.dash.buildings.length, turn: S.dash.world.turn }; try { localStorage.setItem(`sv_guide_${S.kingdomId}`, JSON.stringify(g)); } catch {} }
  if (S.dash.buildings.length > g.start.buildings) g.build = true;
  if (S.dash.world.turn > g.start.turn) g.turn = true;
  const step = GUIDE.findIndex((s) => !g[s.key]);
  const box = $("guide");
  if (g.hidden || step < 0 || S.dash.world.status === "ENDED") { box.classList.add("hidden"); return; }
  box.innerHTML = `${ico("decree")}<div><b>First steps · ${step + 1} of ${GUIDE.length}</b><br>${esc(GUIDE[step].text)}</div>
    <button class="ghost" data-hideguide title="Hide the guide">✕</button>`;
  box.classList.remove("hidden");
  GUIDE[step].target()?.classList.add("pulse");
}

// ---------------------------------------------------------------- negotiation screen
async function openNegotiation(kingdomId) {
  guideMark("court");
  S.negotiating = { kingdomId, tiers: null, chosen: null };
  $("negotiation").classList.remove("hidden");
  renderNegotiation();
  const [tiers, pub] = await Promise.allSettled([
    api("GET", `/gifts/tiers?kingdom_id=${S.kingdomId}&target_id=${kingdomId}`),
    api("GET", `/kingdoms/${kingdomId}`),
  ]);
  if (S.negotiating?.kingdomId !== kingdomId) return;
  S.negotiating.tiers = tiers.status === "fulfilled" ? tiers.value : { tiers: [], error: tiers.reason.message };
  S.negotiating.army = pub.status === "fulfilled" ? pub.value.army_estimate : null;
  if (S.negotiating?.kingdomId === kingdomId) renderNegotiation();
}

function closeOverlay(id) {
  $(id).classList.add("hidden");
  if (id === "negotiation") S.negotiating = null;
}

const CROWN_ICON = { "Golden Crown": "gold", "Iron Crown": "soldiers", "Diplomat's Crown": "ally", "Builder's Crown": "mansions", "People's Crown": "people" };

function medalWithBadges(kingdomName, kingdomId) {
  const row = (S.dash.leaderboard || []).find((r) => r.kingdom_id === kingdomId);
  const pips = (row?.crowns || []).map((c) => `<img src="${icon(CROWN_ICON[c] || "prestige")}" title="${esc(c)}" alt="">`).join("");
  return `<div class="medal-wrap"><img class="med" src="${medal(kingdomName)}" alt="">
    ${row ? `<div class="rank-badge" title="Prestige rank">${row.rank}</div>` : ""}<div class="crown-pips">${pips}</div></div>`;
}

function webHTML(kingdomId) {
  const t = S.map.treaties, nm = (id) => S.map.kingdoms.find((k) => k.id === id)?.name;
  const crests = (ids) => ids.length ? ids.map((id) => `<img src="${crest(nm(id))}" title="${esc(nm(id))}" alt="">`).join("") : '<span class="none">none</span>';
  const allies = t.alliances.filter((a) => a.a === kingdomId || a.b === kingdomId).map((a) => a.a === kingdomId ? a.b : a.a);
  const wars = t.wars.filter((w) => w.attacker === kingdomId || w.defender === kingdomId).map((w) => w.attacker === kingdomId ? w.defender : w.attacker);
  const roads = (t.passages || []).filter((p) => p.grantor === kingdomId).map((p) => p.grantee);
  return `<div class="web">
    <div class="row2" title="Allied with">${ico("ally")}<div class="crests">${crests(allies)}</div></div>
    <div class="row2" title="At war with">${ico("war")}<div class="crests">${crests(wars)}</div></div>
    <div class="row2" title="Roads open to (military passage)">${ico("passage")}<div class="crests">${crests(roads)}</div></div></div>`;
}

function renderNegotiation() {
  const n = S.negotiating;
  const r = S.dash.relations.find((x) => x.kingdom_id === n.kingdomId);
  if (!r) return closeOverlay("negotiation");
  const me = S.dash.kingdom;
  const a = r.actions;
  const pct = (r.standing + 100) / 2;
  const tiers = n.tiers?.tiers || [];
  const banner = (key, act, label, iconName, cls, extra = "") => {
    const gate = key ? a[key] : { allowed: true };
    return `<button class="banner-btn ${cls}" data-act="${act}" data-k="${r.kingdom_id}" ${extra} ${gate.allowed ? "" : "disabled"}
      title="${esc(gate.reason || gate.warning || "")}">${ico(iconName)}${label}</button>`;
  };
  const agreements = [r.alliance ? `${ico("ally")}<span>Allied until turn ${r.alliance.expires_turn}</span>` : "",
    r.war_id ? `${ico("war")}<span class="neg">At war</span>` : "",
    r.passage_granted ? `${ico("passage")}<span>Your roads are open to them</span>` : "",
    r.passage_received ? `${ico("passage")}<span>Their roads are open to you</span>` : "",
    !r.alliance && !r.war_id && !r.passage_granted && !r.passage_received ? `${ico("peace")}<span>No treaty</span>` : ""].join(" ");
  $("negotiation").innerHTML = `<div class="ornate nego"><button class="close-x" data-close="negotiation">✕</button>
    <div class="nego-grid">
      <div class="side">${medalWithBadges(me.name, me.id)}<div class="who">${esc(me.ruler_name)}</div>
        <div class="banner" style="background:${esc(me.color)}">${esc(me.name)}</div>
        <div class="wealth"><span>${ico("gold")} ${fmt(me.resources.gold)}</span><span>${ico("iron")} ${fmt(me.resources.iron)}</span></div>
        <div class="wealth"><span>${ico("soldiers")} ${fmt(me.soldiers)}</span><span>${ico("prestige")} ${me.prestige}</span></div>
        ${webHTML(me.id)}</div>

      <div class="attitude"><div class="muted small">ATTITUDE TOWARDS YOU</div>
        <div class="band-name" style="color:${BAND_COLOR[r.band]}">${r.band.charAt(0) + r.band.slice(1).toLowerCase()} ${trendHTML(r)}</div>
        <div class="scale"><div class="ticks">${[-100, -60, -20, 20, 60, 100].map((t) => `<span>${t}</span>`).join("")}</div>
          <div class="val" style="left:${pct}%">${r.standing}</div><div class="marker" style="left:${pct}%"></div></div>
        <div class="thresholds">${[[-100, "war", "War: always possible (beware betrayal)"], [-49, "loan", "Loans: better than Hostile"],
            [0, "passage", "Military passage: Peaceful or better"], [40, "ally", "Alliance: Friendly (40) or better"]].map(([v, ic, tip]) =>
            `<div class="th ${r.standing >= v ? "on" : "off"}" style="left:${(v + 100) / 2}%" title="${tip}">${ico(ic)}${v}</div>`).join("")}</div>
        <div class="agreements">${agreements}</div>
        ${r.recent_reasons.length ? `<div class="reasons-box parchment"><b>Why they feel this way</b><ul>${r.recent_reasons.slice(0, 4).map((x) =>
          `<li><b class="${x.delta >= 0 ? "pos" : "neg"}" style="color:${x.delta >= 0 ? "#2f7a52" : "#8c2a33"}">${x.delta > 0 ? "+" : ""}${x.delta}</b> ${esc(x.reason)} <span class="muted">(turn ${x.turn})</span></li>`).join("")}</ul></div>` : ""}
        <div class="gift-title">Send a gift to improve relations</div>
        <div class="gifts">${tiers.length ? tiers.map((t, i) => `<div class="gift parchment ${n.chosen === i ? "chosen" : ""} ${t.standing_gain > 0 ? "" : "none"}" data-gift="${i}">
            <div class="gain">+${t.standing_gain} Standing</div>
            <div class="amt two"><span class="pair">${ico("gold")}${fmt(t.gold)}</span>${t.iron ? `<span class="pair">${ico("iron")}${fmt(t.iron)}</span>` : ""}</div>
            <div class="muted small">becomes ${t.new_standing} · ${t.new_band.toLowerCase()}</div></div>`).join("")
          : `<div class="muted" style="grid-column:1/-1;text-align:center">${n.tiers?.error ? esc(n.tiers.error) : "Weighing the treasury…"}</div>`}</div>
        <div style="text-align:center;margin-top:10px"><button class="gold" data-sendgift ${n.chosen == null ? "disabled" : ""} style="padding:10px 38px;font-size:15px">Confirm gift</button></div>
      </div>

      <div class="side">${medalWithBadges(r.name, r.kingdom_id)}<div class="who">${esc(r.ruler_name)}</div>
        <div class="banner" style="background:${esc(r.color)}">${esc(r.name)}</div>
        <div class="muted small">${r.is_npc ? "NPC ruler" : "Human ruler"}</div>
        <div class="wealth"><span title="Estimated army (rounded)">${ico("soldiers")} ${n.army == null ? "?" : "~" + fmt(n.army)}</span></div>
        ${webHTML(r.kingdom_id)}</div>
    </div>
    <div class="nego-actions">
      ${r.alliance ? `<button class="banner-btn war" data-act="break" data-alliance="${r.alliance.id}">${ico("ally")}Break pact</button>` : banner("alliance", "alliance", "Ally", "ally", "ally")}
      ${banner("trade", "trade", "Trade", "trade", "gold")}
      ${banner("loan", "loan", "Loan", "loan", "green")}
      ${r.war_id ? `<button class="banner-btn peace" data-act="peace" data-war="${r.war_id}">${ico("peace")}Offer peace</button>` : ""}
      ${r.war_id ? `<button class="banner-btn war" data-act="battle" data-k="${r.kingdom_id}">${ico("war")}Attack</button>` : banner("declare_war", "battle", "Declare war", "war", "war")}
      ${r.passage_granted ? `<button class="banner-btn war" data-act="closepassage" data-passage="${r.passage_granted.id}">${ico("passage")}Terminate passage</button>`
        : banner("passage", "passage", "Grant passage", "passage", "green")}
      ${banner(null, "letter", "Send letter", "letter", "")}
    </div></div>`;
}

async function sendGift() {
  const n = S.negotiating, t = n?.tiers?.tiers?.[n.chosen];
  if (!t) return;
  try {
    const g = await api("POST", "/gifts", { kingdom_id: S.kingdomId, target_id: n.kingdomId, gold: t.gold, iron: t.iron || 0 }, true);
    toast(`Gift of ${fmt(g.gold)} gold${g.iron ? ` and ${fmt(g.iron)} iron` : ""} delivered: +${g.standing_gain} standing (now ${g.standing}).`);
    await refresh();
    if (S.negotiating) await openNegotiation(n.kingdomId);
  } catch (e) { fail(e); }
}

function renderInbox() {
  const ib = S.dash.inbox;
  const items = [];
  for (const t of ib.trades) items.push(`<div class="item"><div class="title">Trade from ${esc(nameOf(t.sender_id))}</div>
     Gives ${fmt(t.offered_amount)} ${t.offered_resource} for ${fmt(t.requested_amount)} ${t.requested_resource}
     <div class="actions"><button class="gold" data-inbox="trade-accept" data-id="${t.id}">Accept</button><button data-inbox="trade-reject" data-id="${t.id}">Reject</button></div></div>`);
  for (const l of ib.loans) items.push(`<div class="item"><div class="title">Loan ${esc(l.code)}: ${esc(nameOf(l.lender_id))} → ${esc(nameOf(l.borrower_id))}</div>
     ${fmt(l.principal)} gold at ${l.interest_rate}% over ${l.duration_turns} turns (repay ${fmt(l.total_repayment)})
     <div class="actions"><button class="gold" data-inbox="loan-accept" data-id="${l.id}">Accept</button><button data-inbox="loan-reject" data-id="${l.id}">Reject</button></div></div>`);
  for (const a of ib.alliances) items.push(`<div class="item"><div class="title">Alliance proposal from ${esc(nameOf(a.proposer_id))}</div>
     ${a.duration_turns} turns${a.mutual_defense ? ", mutual defence" : ""}
     <div class="actions"><button class="gold" data-inbox="ally-accept" data-id="${a.id}">Seal the pact</button><button data-inbox="ally-reject" data-id="${a.id}">Refuse</button></div></div>`);
  for (const w of ib.peace) items.push(`<div class="item"><div class="title">Peace offered by ${esc(nameOf(w.peace_proposed_by))}</div>
     <div class="actions"><button class="gold" data-act="peace" data-war="${w.id}">Accept peace</button></div></div>`);
  const notes = S.dash.notifications.map((n) => `<div class="item small"><span class="muted">t${n.turn}</span> ${esc(n.text)}</div>`).join("");
  $("tab-inbox").innerHTML = (items.join("") || '<p class="muted">No proposals waiting.</p>') +
    `<h3>Notifications</h3>${notes || '<p class="muted">Nothing new.</p>'}
     <button data-inbox="mark-read">Mark all read</button>`;
}

async function renderTreasury() {
  const loans = S.dash.loans.map((l) => `<tr><td>${esc(l.code)}</td><td>${esc(nameOf(l.lender_id))} → ${esc(nameOf(l.borrower_id))}</td>
    <td>${fmt(l.amount_repaid)}/${fmt(l.total_repayment)}</td><td>${l.status}${l.missed_payments ? ` <span class="neg">(${l.missed_payments} missed)</span>` : ""}</td>
    <td>${l.status === "ACTIVE" && l.borrower_id === S.kingdomId ? `<button data-act="repay" data-loan="${l.id}" data-rem="${l.remaining}">Repay</button>` : ""}</td></tr>`).join("");
  $("tab-treasury").innerHTML = `<h3>Loans</h3>${loans ? `<table><tr><th>Loan</th><th>Parties</th><th>Repaid</th><th>Status</th><th></th></tr>${loans}</table>` : '<p class="muted">No loans.</p>'}
    <h3>Transaction history</h3><div id="ledger" class="muted">Loading…</div>`;
  try {
    const rows = await api("GET", `/kingdoms/${S.kingdomId}/ledger?limit=40`);
    $("ledger").innerHTML = `<table><tr><th>Turn</th><th>Type</th><th>Change</th><th>Balance</th></tr>${rows.map((e) =>
      `<tr><td>${e.turn}</td><td>${esc(e.type)}</td><td class="${e.delta >= 0 ? "pos" : "neg"}">${e.delta > 0 ? "+" : ""}${fmt(e.delta)} ${e.resource}</td><td>${fmt(e.balance_after)}</td></tr>`).join("")}</table>`;
  } catch (e) { fail(e); }
}

async function renderLetters() {
  $("tab-letters").innerHTML = '<p class="muted">Loading…</p>';
  try {
    const letters = await api("GET", `/messages?kingdom_id=${S.kingdomId}`);
    $("tab-letters").innerHTML = letters.map((m) => `<div class="item"><div class="title">${m.read ? "" : "● "}${esc(m.subject)}
      <span class="muted small">from ${esc(nameOf(m.sender_kingdom_id))} · t${m.turn} · ${esc(m.tone)}</span></div>
      <div class="letter parchment">${esc(m.body)}</div>
      <div class="actions">${m.read ? "" : `<button data-read="${m.id}">Mark read</button>`}<button data-act="letter" data-k="${m.sender_kingdom_id}">Reply</button></div></div>`).join("")
      || '<p class="muted">No letters yet.</p>';
  } catch (e) { fail(e); }
}

async function renderChronicle() {
  try {
    const events = await api("GET", `/worlds/${S.worldId}/chronicle?limit=80`);
    $("tab-chronicle").innerHTML = events.map((e) => `<div class="chron parchment imp${e.importance}"><div class="t">${esc(e.title)}</div>
      <div>${esc(e.description)}</div><div class="muted small">Turn ${e.turn}${e.consequences.length ? " · " + e.consequences.map(esc).join(", ") : ""}</div></div>`).join("");
  } catch (e) { fail(e); }
}

function renderLeaders() {
  $("tab-leaders").innerHTML = `<h3>Hall of Crowns</h3>` + S.dash.leaderboard.map((r) => `<div class="item"><div class="leader">
    <div class="rank">${r.rank}</div><img class="med" src="${medal(r.name)}" alt="">
    <div><div class="title">${esc(r.name)}${r.is_npc ? ' <span class="muted small">NPC</span>' : ""}</div>
      <div class="muted small">${esc(r.ruler_name)}</div>
      ${r.crowns.length ? `<div class="crowns">${ico("prestige", "")} ${r.crowns.map(esc).join(", ")}</div>`.replace('class=""', 'style="width:16px;vertical-align:-3px"') : ""}</div>
    <div class="pts">${r.prestige}</div></div>
    <div class="muted small" style="margin-top:6px">${Object.entries(r.breakdown).map(([k, v]) => `${k} ${v}`).join(" · ")}${r.penalty ? ` · <span class="neg">betrayal −${r.penalty}</span>` : ""}</div></div>`).join("")
    + `<div class="item prestige-help"><b>How prestige is counted</b> (each category tops out at 200, and the first points come cheapest)
      <ul>${PRESTIGE_HELP.map(([, label, what, how]) => `<li><b>${label}</b>: ${esc(what)}. <span class="muted">${esc(how)}.</span></li>`).join("")}</ul>
      <span class="muted">Breaking an alliance or defaulting on a loan costs prestige outright. At turn ${S.dash.world.turn_limit} the highest total is crowned.</span></div>`;
}

// ---------------------------------------------------------------- dialogs & actions
function dialog(title, inner, onSubmit) {
  const form = $("actionForm");
  form.innerHTML = `<h2 style="margin-top:0;color:var(--gold)">${title}</h2>${inner}
    <div class="row" style="margin-top:14px"><button value="ok" class="gold">Confirm</button><button value="cancel" formnovalidate>Cancel</button></div>`;
  const dlg = $("actionDialog");
  dlg.onclose = async () => {
    if (dlg.returnValue !== "ok") return;
    try { await onSubmit(new FormData(form)); await refresh(); } catch (e) { fail(e); }
  };
  dlg.showModal();
}
const resSelect = (name, sel) => `<select name="${name}">${RES.map((r) => `<option ${r === sel ? "selected" : ""}>${r}</option>`).join("")}</select>`;

async function doAction(act, el) {
  const k = el.dataset.k, target = k && S.dash.relations.find((r) => r.kingdom_id === k);
  const me = S.kingdomId;
  if (act === "trade") return dialog(`Trade with ${esc(target.name)}`, `
    <label>You give <div class="row">${resSelect("ores", "food")}<input name="oamt" type="number" min="1" value="100" required></div></label>
    <label>You receive <div class="row">${resSelect("rres", "iron")}<input name="ramt" type="number" min="1" value="80" required></div></label>`,
    async (f) => {
      const t = await api("POST", "/trades", { kingdom_id: me, receiver_id: k, offered_resource: f.get("ores"), offered_amount: +f.get("oamt"),
        requested_resource: f.get("rres"), requested_amount: +f.get("ramt") }, true);
      toast(`Trade ${t.status.toLowerCase()}.${decisionHTML(t.decision)}`, false, 9000);
    });
  if (act === "gift") {
    const tiers = await api("GET", `/gifts/tiers?kingdom_id=${me}&target_id=${k}`);
    return dialog(`Gift to ${esc(target.name)}`, `<p class="muted">Standing ${tiers.current_standing} (${tiers.band}). Choose a chest:</p>
      ${tiers.tiers.map((t, i) => `<label><input type="radio" name="tier" value="${i}" ${i === 0 ? "checked" : ""} style="display:inline;width:auto">
        ${fmt(t.gold)} gold${t.iron ? ` + ${fmt(t.iron)} iron` : ""} → <b class="pos">+${t.standing_gain}</b> standing (${t.new_band})</label>`).join("")}`,
      async (f) => {
        const t = tiers.tiers[+f.get("tier")];
        const g = await api("POST", "/gifts", { kingdom_id: me, target_id: k, gold: t.gold, iron: t.iron || 0 }, true);
        toast(`Gift sent: +${g.standing_gain} standing (now ${g.standing}).`);
      });
  }
  if (act === "loan") return dialog(`Loan with ${esc(target.name)}`, `
    <label>I want to <select name="role"><option value="borrower">borrow from them</option><option value="lender">lend to them</option></select></label>
    <label>Principal (gold) <input name="p" type="number" min="100" value="2000"></label>
    <label>Interest % <input name="r" type="number" min="0" max="50" step="0.5" value="10"></label>
    <label>Duration (turns) <input name="d" type="number" min="1" max="20" value="5"></label>
    <p class="muted small">Credit they would extend you: ${fmt(target.credit_limit_from_them)} gold. Total = P × (1 + r/100).</p>`,
    async (f) => {
      const l = await api("POST", "/loans", { kingdom_id: me, counterparty_id: k, role: f.get("role"), principal: +f.get("p"),
        interest_rate: +f.get("r"), duration_turns: +f.get("d") }, true);
      toast(`Loan ${esc(l.code)} ${l.status.toLowerCase()} (repay ${fmt(l.total_repayment)}).${decisionHTML(l.decision)}`, false, 9000);
    });
  if (act === "alliance") return dialog(`Alliance with ${esc(target.name)}`, `
    <label>Duration (turns) <input name="d" type="number" min="1" max="20" value="10"></label>
    <label><input type="checkbox" name="md" checked style="display:inline;width:auto"> Mutual defence</label>`,
    async (f) => {
      const a = await api("POST", "/alliances", { kingdom_id: me, target_id: k, duration_turns: +f.get("d"), mutual_defense: f.get("md") === "on" });
      toast(`Alliance ${a.status.toLowerCase()}.${decisionHTML(a.decision)}`, false, 9000);
    });
  if (act === "letter") return dialog(`Letter to ${esc(nameOf(k))}`, `
    <label>Subject <input name="s" maxlength="120" required></label>
    <label>Letter <textarea name="b" rows="5" maxlength="2000" required style="width:100%"></textarea></label>
    <label>Tone <select name="t"><option>warm</option><option>proud</option><option>cold</option></select></label>`,
    async (f) => { await api("POST", "/messages", { kingdom_id: me, recipient_id: k, subject: f.get("s"), body: f.get("b"), tone: f.get("t") }); toast("Letter sealed and sent."); });
  if (act === "battle") {
    const warn = target.alliance ? '<p class="neg"><b>You are allied with them. Attacking is a BETRAYAL.</b></p>' : "";
    return dialog(`${target.war_id ? "Attack" : "Declare war on"} ${esc(target.name)}`, `${warn}
      <label>Soldiers to commit (you have ${S.dash.kingdom.soldiers}) <input name="n" type="number" min="1" max="${S.dash.kingdom.soldiers}" value="${Math.max(1, Math.floor(S.dash.kingdom.soldiers / 2))}"></label>`,
      async (f) => {
        const b = await api("POST", "/battles", { kingdom_id: me, target_id: k, soldiers: +f.get("n") }, true);
        toast(`<b>Battle of ${esc(b.place_name)}</b>: ${b.outcome === "ATTACKER_VICTORY" ? "victory" : "defeat"}. Losses ${b.attacker_losses}/${b.defender_losses}, plunder ${fmt(b.plunder_gold)}.`, false, 9000);
      });
  }
  if (act === "break") return dialog("Break the alliance?", '<p class="neg">This is a betrayal: prestige loss, and every kingdom will trust you less.</p>',
    async () => { await api("POST", `/alliances/${el.dataset.alliance}/terminate`, { kingdom_id: me }); });
  if (act === "peace") {
    try {
      const out = await api("POST", `/wars/${el.dataset.war}/peace`, { kingdom_id: me });
      toast(`War status: ${out.war.status.toLowerCase().replace("_", " ")}.${decisionHTML(out.decision)}`, false, 9000);
      await refresh();
    } catch (e) { fail(e); }
  }
  if (act === "passage") {
    try {
      await api("POST", "/passages", { kingdom_id: me, target_id: k });
      toast(`Your roads are open to ${esc(target.name)}. Both realms earn tolls each turn.`); await refresh();
    } catch (e) { fail(e); }
    return;
  }
  if (act === "closepassage") return dialog("Terminate passage?", '<p>Your border gates close to them. They will take it as a slight (standing falls), though it is no betrayal.</p>',
    async () => { await api("POST", `/passages/${el.dataset.passage}/close`, { kingdom_id: me }); toast("The roads are closed."); });
  if (act === "repay") {
    const amt = prompt(`Repay how much? (${el.dataset.rem} remaining)`, el.dataset.rem);
    if (!amt) return;
    try { await api("POST", `/loans/${el.dataset.loan}/repay`, { amount: +amt }, true); toast("Repayment sent."); await refresh(); } catch (e) { fail(e); }
  }
}

async function doInbox(kind, id) {
  const routes = {
    "trade-accept": ["POST", `/trades/${id}/accept`, null, true], "trade-reject": ["POST", `/trades/${id}/reject`],
    "loan-accept": ["POST", `/loans/${id}/accept`, null, true], "loan-reject": ["POST", `/loans/${id}/reject`],
    "ally-accept": ["POST", `/alliances/${id}/respond`, { accept: true }], "ally-reject": ["POST", `/alliances/${id}/respond`, { accept: false }],
    "mark-read": ["GET", `/kingdoms/${S.kingdomId}/notifications?mark_read=true`],
  };
  try { await api(...routes[kind]); if (kind !== "mark-read") guideMark("answer"); await refresh(); } catch (e) { fail(e); }
}

// ---------------------------------------------------------------- live updates
function connectWS() {
  if (S.ws) S.ws.close();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/worlds/${S.worldId}?token=${encodeURIComponent(S.token)}`);
  S.ws = ws;
  ws.onmessage = (m) => {
    const e = JSON.parse(m.data);
    if (e.type === "notification") toast(esc(e.notification.text));
    if (e.type === "turn_ready") toast(`Ready for the next turn: ${e.ready.map(esc).join(", ")}. Waiting for: ${e.waiting_for.map(esc).join(", ")}`);
    if (e.type === "chronicle" && e.event.importance >= 2) toast(`<b>${esc(e.event.title)}</b><br>${esc(e.event.description)}`, false, 8000);
    if (e.type !== "connected" && e.type !== "pong") scheduleRefresh();
  };
  ws.onclose = () => { if (S.ws === ws && S.token) setTimeout(() => S.ws === ws && connectWS(), 2000); };
}

// ---------------------------------------------------------------- wiring
$("loginBtn").onclick = () => auth("login");
$("registerBtn").onclick = () => auth("register");
$("guestBtn").onclick = guest;
$("quickBtn").onclick = quickStart;
$("authUser").onkeydown = (e) => { if (e.key === "Enter") $("authPass").focus(); };
$("authPass").onkeydown = (e) => { if (e.key === "Enter") auth("login"); };
$("pwToggle").onclick = () => {
  const p = $("authPass"), show = p.type === "password";
  p.type = show ? "text" : "password"; $("pwToggle").textContent = show ? "Hide" : "Show"; p.focus();
};
$("logoutBtn").onclick = logout;
$("helpBtn").onclick = () => S.dash && showHowToWin();
$("createWorldBtn").onclick = createWorld;
async function endTurn() {
  if ($("advanceBtn").disabled || S.endingTurn) return;
  S.endingTurn = true; $("advanceBtn").disabled = true;
  const before = snapshot();
  try {
    const r = await api("POST", `/worlds/${S.worldId}/turn`);
    if (!r.advanced) { toast(`You are ready. Waiting for: ${r.waiting_for.map(esc).join(", ")}`); await refresh(); return; }
    await refresh();
    if (!r.ended) await showTurnReport(before);
  } catch (e) { fail(e); }
  finally { S.endingTurn = false; $("advanceBtn").disabled = S.dash?.world.status === "ENDED"; }
}
$("advanceBtn").onclick = endTurn;
$("map").onclick = onMapClick;
$("map").onmousemove = onMapHover;
$("map").onmouseleave = () => $("hoverInfo").classList.add("hidden");
document.addEventListener("keydown", (e) => {
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "");
  const overlayOpen = ["infoOverlay", "turnReport", "buildDetail", "negotiation"].some((id) => !$(id).classList.contains("hidden")) || $("actionDialog").open;
  if ((e.key === "e" || e.key === "E") && !typing && !overlayOpen && !$("gameView").classList.contains("hidden")) return endTurn();
  if (e.key !== "Escape") return;
  for (const id of ["infoOverlay", "turnReport", "buildDetail", "negotiation"]) if (!$(id).classList.contains("hidden")) return closeOverlay(id);
  if (S.selected) { S.selected = null; renderCatalog(); drawMap(); }
});
document.addEventListener("click", (e) => {
  if (e.target.classList?.contains("overlay")) return closeOverlay(e.target.id);   // click outside the panel
  const el = e.target.closest("button, [data-detail], [data-gift]");
  if (!el || el.disabled) return;
  const d = el.dataset;
  if (d.close) closeOverlay(d.close);
  else if (d.goto) { closeOverlay("turnReport"); renderTab(d.goto); }
  else if (d.mkt) marketTrade(d.mkt);
  else if (d.tribute) payTribute(d.tribute, +d.amt);
  else if (d.defend != null) toast("<b>Raising your defence</b><br>Recruit soldiers (needs Barracks), build or upgrade a Watchtower (+25% per rank), or ally with a court and tick <i>mutual defence</i>: a quarter of their army stands with you.", false, 11000);
  else if (d.hideguide != null) { const g = guideState(); g.hidden = true; try { localStorage.setItem(`sv_guide_${S.kingdomId}`, JSON.stringify(g)); } catch {} renderGuide(); }
  else if (d.newreign != null) { closeOverlay("turnReport"); S.worldId = S.kingdomId = null; sessionStorage.removeItem("sv_world"); sessionStorage.removeItem("sv_kingdom"); if (S.ws) S.ws.close(); loadWorlds(false); }
  else if (d.detail) openBuildDetail(d.detail, d.bid);
  else if (d.pane) { S.pane = d.pane; renderCatalog(); }
  else if (d.cat) { S.cat = d.cat; renderCatalog(); }
  else if (d.claim) claimDecree(d.claim);
  else if (d.negotiate) openNegotiation(d.negotiate);
  else if (d.gift != null && S.negotiating) { if (!el.classList.contains("none")) { S.negotiating.chosen = +d.gift; renderNegotiation(); } }
  else if (d.sendgift != null) sendGift();
  else if (d.join) joinWorld(d.join, d.name);
  else if (d.enter) enterGame(d.enter, d.k);
  else if (d.build) { S.selected = S.selected === d.build ? null : d.build; closeOverlay("buildDetail"); renderCatalog(); drawMap(); }
  else if (d.upgrade) closeOverlay("buildDetail"), api("PATCH", `/buildings/${d.upgrade}/upgrade`, null, true).then(() => { toast("Upgraded."); refresh(); }, fail);
  else if (d.tab) renderTab(d.tab);
  else if (d.act) doAction(d.act, el);
  else if (d.inbox) doInbox(d.inbox, d.id);
  else if (d.read) api("POST", `/messages/${d.read}/read`).then(renderLetters, fail);
});
$("recruitBtn").onclick = async () => {
  try { await api("POST", "/soldiers/recruit", { kingdom_id: S.kingdomId, count: +$("recruitCount").value }, true); toast("Soldiers trained."); await refresh(); } catch (e) { fail(e); }
};

if (!S.token) show("authView");
else if (S.worldId && S.kingdomId) enterGame(S.worldId, S.kingdomId);
else loadWorlds(true).catch(() => logout());
