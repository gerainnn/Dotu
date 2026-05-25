/* Dotu Poker — Mini App client */

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  try { tg.setHeaderColor("#0a0b0e"); } catch (_) {}
  try { tg.setBackgroundColor("#0a0b0e"); } catch (_) {}
}

// ---- API client ------------------------------------------------------------

const initData = tg?.initData || "";
const devUser = new URLSearchParams(location.search).get("dev_user") || "";

async function api(path, body = null) {
  const headers = { "Content-Type": "application/json" };
  if (initData) headers["X-Init-Data"] = initData;
  if (!initData && devUser) headers["X-Dev-User"] = devUser;
  const res = await fetch(path, {
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : "{}",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

// ---- state -----------------------------------------------------------------

const state = {
  profile: null,
  equipped: { card_back: "back_classic", chip_style: "chip_gold", table_felt: "felt_emerald" },
  shopItems: [],
  shopCategory: "card_back",
  game: null,
};

// ---- helpers ---------------------------------------------------------------

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function toast(text, ms = 1800) {
  const el = $("#toast");
  el.textContent = text;
  el.hidden = false;
  el.style.animation = "none";
  // restart animation
  void el.offsetWidth;
  el.style.animation = "";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), ms);
}

function haptic(kind = "light") {
  try { tg?.HapticFeedback?.impactOccurred(kind); } catch (_) {}
}

function fmt(n) {
  return Number(n).toLocaleString("en-US");
}

// ---- views / nav -----------------------------------------------------------

function showView(name) {
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${name}`));
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  if (name === "shop") loadShop();
  if (name === "profile") loadProfile();
  if (name === "lobby") loadProfile();
}

$$(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => { haptic(); showView(btn.dataset.view); });
});

// ---- profile ---------------------------------------------------------------

async function loadProfile() {
  try {
    const data = await api("/api/profile");
    state.profile = data.user;
    state.equipped = data.equipped;
    renderProfile();
    renderTopBar();
  } catch (e) {
    console.error(e);
    toast("Auth failed. Open from Telegram.");
  }
}

function renderTopBar() {
  if (!state.profile) return;
  $("#balance").innerHTML = `${fmt(state.profile.balance)} <span class="balance-label">chips</span>`;
}

function renderProfile() {
  if (!state.profile) return;
  const u = state.profile;
  $("#stat-hands").textContent = u.hands_played;
  $("#stat-wins").textContent = u.hands_won;
  $("#stat-rate").textContent = `${Math.round(u.win_rate * 100)}%`;

  $("#profile-name").textContent = u.first_name || u.username || "Player";
  $("#profile-handle").textContent = u.username ? `@${u.username}` : "";
  $("#p-balance").textContent = fmt(u.balance);
  $("#p-level").textContent = u.level;
  $("#p-hands").textContent = u.hands_played;
  $("#p-wins").textContent = u.hands_won;
  $("#p-rate").textContent = `${Math.round(u.win_rate * 100)}%`;

  const av = $("#avatar");
  av.innerHTML = "";
  if (u.photo_url) {
    const img = document.createElement("img");
    img.src = u.photo_url;
    av.appendChild(img);
  } else {
    av.textContent = (u.first_name || u.username || "P").slice(0, 1).toUpperCase();
  }

  // equipped grid
  const grid = $("#equipped-grid");
  grid.innerHTML = "";
  const labels = { card_back: "Card back", chip_style: "Chips", table_felt: "Felt" };
  for (const cat of ["card_back", "chip_style", "table_felt"]) {
    const itemId = state.equipped[cat] || "";
    const item = (state.shopItems || []).find(i => i.id === itemId);
    const div = document.createElement("div");
    div.className = "equipped-card";
    div.innerHTML = `
      <div class="label">${labels[cat]}</div>
      <div class="preview-spot">${previewHTML(cat, item ? item.preview : itemId)}</div>
      <div class="name">${item ? item.name : itemId}</div>
    `;
    grid.appendChild(div);
  }
}

// ---- shop ------------------------------------------------------------------

async function loadShop() {
  try {
    const data = await api("/api/shop");
    state.shopItems = data.items;
    renderShop();
    renderProfile(); // equipped previews need shop items
  } catch (e) { console.error(e); }
}

function previewCardBackClass(preview) {
  // preview value: diag-gold (default classic) / noir / ruby / ocean / aurora
  if (!preview || preview === "diag-gold") return "";
  return `back_${preview}`;
}

function previewHTML(category, preview) {
  if (category === "card_back") {
    return `<div class="preview-card card back ${previewCardBackClass(preview)}"></div>`;
  }
  if (category === "chip_style") {
    return `<div class="preview-chip" style="--c: ${preview}"></div>`;
  }
  if (category === "table_felt") {
    return `<div class="preview-felt" style="--c: ${preview}"></div>`;
  }
  return "";
}
function renderShop() {
  $$("#shop-tabs .tab").forEach(t => t.classList.toggle("active", t.dataset.cat === state.shopCategory));
  const grid = $("#shop-grid");
  grid.innerHTML = "";
  const items = state.shopItems.filter(i => i.category === state.shopCategory);
  for (const it of items) {
    const div = document.createElement("div");
    div.className = "shop-item" + (it.equipped ? " equipped" : "");
    let preview;
    if (it.category === "card_back") {
      preview = `<div class="preview-card card back ${previewCardBackClass(it.preview)}"></div>`;
    } else if (it.category === "chip_style") {
      preview = `<div class="preview-chip" style="--c: ${it.preview}"></div>`;
    } else {
      preview = `<div class="preview-felt" style="--c: ${it.preview}"></div>`;
    }
    let btn;
    if (it.equipped) {
      btn = `<button class="shop-btn equipped" disabled>Equipped</button>`;
    } else if (it.owned) {
      btn = `<button class="shop-btn equip" data-equip="${it.id}">Equip</button>`;
    } else {
      btn = `<button class="shop-btn buy" data-buy="${it.id}">Buy · ${fmt(it.price)}</button>`;
    }
    div.innerHTML = `
      <div class="shop-preview">${preview}</div>
      <div class="shop-name">${it.name}</div>
      <div class="shop-price">${it.price === 0 ? "Free" : fmt(it.price) + " chips"}</div>
      ${btn}
    `;
    grid.appendChild(div);
  }
}

$$("#shop-tabs .tab").forEach(t => t.addEventListener("click", () => {
  state.shopCategory = t.dataset.cat;
  renderShop();
}));

document.addEventListener("click", async (e) => {
  const buy = e.target.closest("[data-buy]");
  const eq  = e.target.closest("[data-equip]");
  if (buy) {
    haptic("medium");
    try {
      const r = await api("/api/buy", { item_id: buy.dataset.buy });
      state.profile.balance = r.balance;
      renderTopBar();
      toast("Purchased");
      await loadShop();
    } catch (err) {
      let msg = "Not enough chips";
      try { msg = JSON.parse(err.message).detail || msg; } catch (_) {}
      toast(msg);
    }
  } else if (eq) {
    haptic("light");
    try {
      const r = await api("/api/equip", { item_id: eq.dataset.equip });
      state.equipped = r.equipped;
      toast("Equipped");
      await loadShop();
    } catch (err) {
      toast("Could not equip");
    }
  }
});

// ---- poker -----------------------------------------------------------------

const SUIT_GLYPH = { s: "♠", h: "♥", d: "♦", c: "♣" };

function renderCard(code, faceDown = false) {
  if (!code) return `<div class="card placeholder"></div>`;
  if (faceDown || code === "??") {
    const skin = previewCardBackClass(skinPreviewForBack(state.equipped.card_back));
    return `<div class="card back ${skin}"></div>`;
  }
  const r = code[0];
  const s = code[1];
  const red = (s === "h" || s === "d");
  const rankDisp = r === "T" ? "10" : r;
  return `
    <div class="card ${red ? "red" : "black"}">
      <div class="rank">${rankDisp}</div>
      <div class="suit">${SUIT_GLYPH[s]}</div>
    </div>`;
}

function skinPreviewForBack(itemId) {
  const m = (state.shopItems || []).find(i => i.id === itemId);
  return m ? m.preview : "diag-gold";
}

function chipColor() {
  const m = (state.shopItems || []).find(i => i.id === state.equipped.chip_style);
  return m ? m.preview : "#d4af37";
}

function feltColor() {
  const m = (state.shopItems || []).find(i => i.id === state.equipped.table_felt);
  return m ? m.preview : "#143b2a";
}

function applyTableTheme() {
  const felt = feltColor();
  const tableEl = $("#poker-table");
  if (tableEl) {
    tableEl.style.background = `radial-gradient(ellipse at 50% 50%, ${shade(felt, 14)} 0%, ${shade(felt, -8)} 80%)`;
  }
  document.documentElement.style.setProperty("--chip", chipColor());
}

// utility: lighten/darken hex
function shade(hex, amt) {
  const c = hex.replace("#", "");
  const n = parseInt(c, 16);
  let r = (n >> 16) + amt;
  let g = ((n >> 8) & 0xff) + amt;
  let b = (n & 0xff) + amt;
  r = Math.max(0, Math.min(255, r));
  g = Math.max(0, Math.min(255, g));
  b = Math.max(0, Math.min(255, b));
  return "#" + (r << 16 | g << 8 | b).toString(16).padStart(6, "0");
}

function renderGame(g) {
  state.game = g;
  $("#stage-label").textContent = g.stage;
  $("#pot").textContent = `Pot ${fmt(g.pot)}`;
  $("#board").innerHTML = (g.community.length
    ? g.community
    : Array(5).fill(null)).map(c => renderCard(c, false)).join("");

  for (const p of g.players) {
    const seat = $(`.seat-${p.seat}`);
    if (!seat) continue;
    const isTurn = g.turn_seat === p.seat && !["showdown", "finished"].includes(g.stage);
    const handHTML = p.hole.map(c => renderCard(c, !p.is_human && c === "??")).join("");
    seat.innerHTML = `
      <div class="player ${isTurn ? "is-turn" : ""} ${p.folded ? "is-folded" : ""}">
        <div>
          <div class="pname">${escapeHtml(p.name)}</div>
          <div class="pstack">${fmt(p.stack)} chips</div>
        </div>
      </div>
      <div class="hand">${handHTML}</div>
      <div class="player-bet">${p.bet ? `<span class="chip-dot"></span>${fmt(p.bet)}` : "&nbsp;"}</div>
      <div class="player-action">${p.last_action || ""}</div>
    `;
    if (g.dealer_seat === p.seat) {
      const dealer = document.createElement("div");
      dealer.className = "dealer-btn";
      dealer.textContent = "D";
      // place near the player block
      seat.appendChild(dealer);
      // crude positioning per seat
      if (p.seat === 0) Object.assign(dealer.style, { top: "-4px", right: "-6px" });
      if (p.seat === 1) Object.assign(dealer.style, { right: "-6px", bottom: "-4px" });
      if (p.seat === 2) Object.assign(dealer.style, { right: "-6px", bottom: "-4px" });
      if (p.seat === 3) Object.assign(dealer.style, { left: "-6px", bottom: "-4px" });
    }
  }

  updateActionButtons(g);

  if (g.stage === "finished") {
    showResult(g);
  } else {
    $("#result-overlay").hidden = true;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[c]));
}

function updateActionButtons(g) {
  const me = g.players.find(p => p.is_human);
  const myTurn = g.turn_seat === 0 && !["showdown", "finished"].includes(g.stage);
  const toCall = Math.max(0, g.current_bet - me.bet);

  const fold = $('button[data-act="fold"]');
  const check = $('button[data-act="check"]');
  const raise = $('button[data-act="raise"]');

  for (const b of [fold, check, raise]) b.disabled = !myTurn;

  if (toCall === 0) {
    check.textContent = "Check";
    check.dataset.act = "check";
  } else {
    check.textContent = `Call ${fmt(toCall)}`;
    check.dataset.act = "call";
  }

  // raise slider bounds
  const minTotalRaise = g.current_bet + g.min_raise;
  const maxTotalRaise = me.bet + me.stack; // all-in
  const slider = $("#raise-slider");
  const display = $("#raise-display");
  const bar = $("#raise-bar");
  if (myTurn && me.stack > 0 && maxTotalRaise > g.current_bet) {
    bar.hidden = false;
    slider.min = String(minTotalRaise);
    slider.max = String(maxTotalRaise);
    if (Number(slider.value) < minTotalRaise || Number(slider.value) > maxTotalRaise) {
      slider.value = String(Math.min(maxTotalRaise, minTotalRaise));
    }
    display.textContent = fmt(Number(slider.value));
    raise.textContent = Number(slider.value) >= maxTotalRaise ? "All-in" : "Raise";
  } else {
    bar.hidden = true;
  }
}

$("#raise-slider").addEventListener("input", () => {
  if (!state.game) return;
  const me = state.game.players[0];
  const v = Number($("#raise-slider").value);
  $("#raise-display").textContent = fmt(v);
  const raise = $('button[data-act="raise"]');
  raise.textContent = v >= me.bet + me.stack ? "All-in" : "Raise";
});

document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".action");
  if (!btn || btn.disabled) return;
  const act = btn.dataset.act;
  haptic("medium");
  let payload = { action: act };
  if (act === "raise") {
    const v = Number($("#raise-slider").value);
    const me = state.game.players[0];
    if (v >= me.bet + me.stack) {
      payload = { action: "allin" };
    } else {
      payload.amount = v;
    }
  }
  try {
    const g = await api("/api/poker/action", payload);
    renderGame(g);
  } catch (err) {
    toast("Action failed");
  }
});

function showResult(g) {
  const overlay = $("#result-overlay");
  const delta = g.delta || 0;
  const won = delta > 0;
  $("#result-title").textContent = won ? "You won" : delta < 0 ? "You lost" : "Even";
  const d = $("#result-delta");
  d.textContent = (delta > 0 ? "+" : "") + fmt(delta);
  d.className = "result-delta " + (won ? "win" : delta < 0 ? "loss" : "");
  const winnerLine = (g.winners || [])
    .map(w => `${w.name} · ${w.hand} (+${fmt(w.amount)})`)
    .join("<br>");
  $("#result-detail").innerHTML = winnerLine || "";
  overlay.hidden = false;

  // settle balance
  api("/api/poker/settle").then(r => {
    if (state.profile) {
      state.profile.balance = r.balance;
      renderTopBar();
    }
  }).catch(() => {});
}

$("#btn-next").addEventListener("click", async () => {
  haptic("light");
  $("#result-overlay").hidden = true;
  await startHand();
});
$("#btn-leave").addEventListener("click", () => {
  haptic("light");
  $("#result-overlay").hidden = true;
  showView("lobby");
  loadProfile();
});
$("#btn-play").addEventListener("click", async () => {
  haptic("medium");
  showView("poker");
  await startHand();
});

async function startHand() {
  try {
    applyTableTheme();
    if (state.shopItems.length === 0) await loadShop();
    const g = await api("/api/poker/new");
    renderGame(g);
  } catch (e) {
    let msg = "Could not start hand";
    try { msg = JSON.parse(e.message).detail || msg; } catch (_) {}
    toast(msg);
  }
}

// ---- boot ------------------------------------------------------------------

(async function boot() {
  await loadProfile();
  await loadShop();
  applyTableTheme();
  renderProfile();
})();
