// Seite „eQ-3 MAX!“ – Übersicht, Verknüpfungen und Gerätekonfiguration.
// Vanilla Custom Element ohne Build-Schritt und ohne Fremdbibliotheken.
// Daten kommen ausschließlich über die WebSocket-Befehle eq3_max/*.

const AIRTIME_WARN = 0.5;
const AIRTIME_ALARM = 0.8;

const TYPE_ICONS = {
  heating_thermostat: "mdi:radiator",
  wall_thermostat: "mdi:thermostat",
  shutter_contact: "mdi:window-open-variant",
  push_button: "mdi:gesture-tap-button",
  cube: "mdi:cube-outline",
};
const MODE_LABELS = { auto: "Automatik", manual: "Manuell", temporary: "Temporär", boost: "Boost" };
const PRESET_LABELS = { away: "Abwesend", boost: "Boost" };
const HVAC_LABELS = { off: "Aus" };
const SOURCE_LABELS = { homegear: "Homegear", werksvorgabe: "Werksvorgabe", gesetzt: "gesetzt" };
const LINK_LABELS = {
  pending: "ausstehend",
  waiting: "wartet auf Gerät",
  failed: "fehlgeschlagen",
  rejected: "abgelehnt",
  one_sided: "einseitig",
};
const LINK_CHIP = { pending: "warn", waiting: "warn", failed: "error", rejected: "error", one_sided: "warn" };
const SLEEPER_HINTS = {
  shutter_contact:
    "Fensterkontakte hören nur kurz nach dem eigenen Senden zu: Änderungen gehen erst raus, " +
    "wenn das Fenster einmal geöffnet und geschlossen wird.",
  push_button:
    "Eco-Taster hören nur kurz nach dem eigenen Senden zu: Änderungen gehen erst raus, " +
    "wenn der Taster einmal gedrückt wird (oder die Anlerntaste).",
};

const STYLE = `
  :host {
    display: block;
    min-height: 100vh;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color, #212121);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
    --e3-gap: 16px;
    --e3-radius: var(--ha-card-border-radius, 12px);
    --e3-card: var(--card-background-color, #fff);
    --e3-divider: var(--divider-color, rgba(0, 0, 0, 0.12));
    --e3-muted: var(--secondary-text-color, #727272);
    --e3-ok: var(--success-color, #43a047);
    --e3-warn: var(--warning-color, #ffa600);
    --e3-error: var(--error-color, #db4437);
    --e3-accent: var(--primary-color, #03a9f4);
  }
  * { box-sizing: border-box; }
  .toolbar {
    display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 16px;
    background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, #fff);
    font-size: 20px; position: sticky; top: 0; z-index: 2;
  }
  .menu-btn { background: none; border: 0; color: inherit; cursor: pointer; padding: 8px; font-size: 22px; }
  main { padding: var(--e3-gap); max-width: 1400px; margin: 0 auto; }
  section.entry { margin-bottom: 32px; }
  .hub {
    background: var(--e3-card); border-radius: var(--e3-radius); padding: 12px 16px;
    display: flex; flex-wrap: wrap; align-items: center; gap: 12px 24px;
    box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.15));
  }
  .hub .title { font-weight: 500; font-size: 16px; }
  .hub .item { display: flex; align-items: center; gap: 8px; color: var(--e3-muted); }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--e3-error); flex: none; }
  .dot.ok { background: var(--e3-ok); }
  .meter { width: 120px; height: 8px; border-radius: 4px; background: var(--e3-divider); overflow: hidden; }
  .meter > span { display: block; height: 100%; background: var(--e3-accent); }
  .meter.warn > span { background: var(--e3-warn); }
  .meter.alarm > span { background: var(--e3-error); }
  .spacer { flex: 1; }
  .radios { flex-basis: 100%; display: grid; gap: 6px; border-top: 1px solid var(--e3-divider); padding-top: 10px; }
  .radio { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; color: var(--e3-muted); }
  .radio .name { color: var(--primary-text-color); font-weight: 500; min-width: 120px; display: flex; align-items: center; gap: 8px; }
  button.action {
    border: 1px solid var(--e3-accent); color: var(--e3-accent); background: transparent;
    border-radius: 18px; padding: 6px 14px; cursor: pointer; font: inherit; font-size: 14px;
  }
  button.action.primary { background: var(--e3-accent); color: var(--text-primary-color, #fff); }
  button.action.danger { border-color: var(--e3-error); color: var(--e3-error); }
  button.action:disabled { opacity: 0.45; cursor: default; }
  h2.area { font-size: 15px; font-weight: 500; color: var(--e3-muted); margin: 24px 4px 8px; }
  .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
  .card {
    background: var(--e3-card); border-radius: var(--e3-radius); padding: 12px 14px; cursor: pointer;
    box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.15)); border: 1px solid transparent;
    display: flex; flex-direction: column; gap: 8px; text-align: left; color: inherit; font: inherit;
  }
  .card:hover, .card:focus-visible { border-color: var(--e3-accent); outline: none; }
  .card.rf { border-color: var(--e3-error); }
  .card .head { display: flex; align-items: center; gap: 4px 8px; flex-wrap: wrap; }
  .card .name { font-weight: 500; flex: 1 1 50%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .card .big { font-size: 22px; }
  .card .sub { color: var(--e3-muted); font-size: 13px; }
  .card .foot { display: flex; flex-wrap: wrap; gap: 4px 12px; color: var(--e3-muted); font-size: 12px; align-items: center; }
  .card .foot .radio-tag { display: inline-flex; align-items: center; gap: 3px; }
  .card .foot .radio-tag ha-icon { --mdc-icon-size: 14px; }
  .chip {
    display: inline-block; border-radius: 10px; padding: 1px 8px; font-size: 12px; white-space: nowrap;
    background: var(--e3-divider); color: var(--primary-text-color);
  }
  .chip.ok { background: var(--e3-ok); color: #fff; }
  .chip.warn { background: var(--e3-warn); color: #000; }
  .chip.error { background: var(--e3-error); color: #fff; }
  .chip.info { background: var(--e3-accent); color: var(--text-primary-color, #fff); }
  .bars { display: inline-flex; align-items: flex-end; gap: 1px; height: 12px; }
  .bars span { width: 3px; background: var(--e3-divider); }
  .bars span.on { background: var(--e3-muted); }
  .valve { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--e3-muted); }
  .valve .meter { flex: 1; width: auto; }
  .empty { color: var(--e3-muted); padding: 16px 4px; }
  .notice { background: var(--e3-card); border-left: 4px solid var(--e3-warn); padding: 10px 14px; border-radius: 6px; }
  .overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: 5; }
  .drawer {
    position: fixed; top: 0; right: 0; bottom: 0; width: min(520px, 100%); z-index: 6;
    background: var(--e3-card); display: flex; flex-direction: column;
    box-shadow: -2px 0 12px rgba(0, 0, 0, 0.3);
  }
  .drawer header { padding: 16px; border-bottom: 1px solid var(--e3-divider); display: flex; gap: 12px; align-items: flex-start; }
  .drawer header .t { flex: 1; }
  .drawer header .t div:first-child { font-size: 18px; font-weight: 500; }
  .drawer header .t div + div { color: var(--e3-muted); font-size: 13px; margin-top: 2px; }
  .close { background: none; border: 0; font-size: 22px; cursor: pointer; color: var(--primary-text-color); }
  .tabs { display: flex; border-bottom: 1px solid var(--e3-divider); }
  .tabs button {
    flex: 1; background: none; border: 0; border-bottom: 2px solid transparent; padding: 12px; cursor: pointer;
    color: var(--e3-muted); font: inherit;
  }
  .tabs button.active { color: var(--e3-accent); border-bottom-color: var(--e3-accent); }
  .body { overflow-y: auto; padding: 16px; flex: 1; display: flex; flex-direction: column; gap: 16px; }
  .row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--e3-divider); flex-wrap: wrap; }
  .row .grow { flex: 1; min-width: 120px; }
  .row .hint { flex-basis: 100%; color: var(--e3-muted); font-size: 12px; }
  .add { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  select, input {
    font: inherit; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--e3-divider);
    background: var(--e3-card); color: var(--primary-text-color);
  }
  input:invalid { border-color: var(--e3-error); }
  input.changed, select.changed { border-color: var(--e3-accent); border-width: 2px; }
  fieldset { border: 1px solid var(--e3-divider); border-radius: 8px; padding: 8px 12px 12px; margin: 0; }
  legend { padding: 0 6px; font-weight: 500; }
  .cfg { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--e3-divider); }
  .cfg .label { font-size: 14px; }
  .cfg .meta { grid-column: 1 / -1; display: flex; gap: 6px; flex-wrap: wrap; font-size: 12px; color: var(--e3-muted); }
  .cfg .ctl { display: flex; align-items: center; gap: 6px; }
  .cfg input { width: 96px; text-align: right; }
  .setfoot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; align-items: center; flex-wrap: wrap; }
  .confirm { border: 1px solid var(--e3-warn); border-radius: 8px; padding: 10px 12px; margin-top: 12px; font-size: 14px; }
  .confirm ul { margin: 6px 0; padding-left: 20px; }
  .toast {
    position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 10; max-width: 90%;
    background: var(--e3-card); color: var(--primary-text-color); border-radius: 8px; padding: 10px 16px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35); border-left: 4px solid var(--e3-ok);
  }
  .toast.error { border-left-color: var(--e3-error); }
  @media (max-width: 600px) {
    main { padding: 8px; }
    .grid { grid-template-columns: 1fr; }
    .hub { gap: 8px 16px; }
  }
`;

// --- Hilfsfunktionen -------------------------------------------------------

/** DOM-Knoten bauen; Texte immer als Textknoten (kein innerHTML). */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (key === "style") el.style.cssText = value;
    else if (key in el && typeof value !== "string") el[key] = value;
    else el.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function num(value, digits = 1) {
  if (value === null || value === undefined) return "–";
  return Number(value).toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function plainNum(value) {
  return Number(value).toLocaleString("de-DE", { maximumFractionDigits: 2 });
}

function ago(ts) {
  if (!ts) return "nie gemeldet";
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 10) return "gerade eben";
  if (s < 60) return `vor ${s} s`;
  if (s < 3600) return `vor ${Math.floor(s / 60)} min`;
  if (s < 86400) return `vor ${Math.floor(s / 3600)} h`;
  const d = Math.floor(s / 86400);
  return d === 1 ? "vor 1 Tag" : `vor ${d} Tagen`;
}

function rssiBars(rssi) {
  const level = rssi === null || rssi === undefined ? 0 : rssi >= -60 ? 4 : rssi >= -70 ? 3 : rssi >= -80 ? 2 : rssi >= -90 ? 1 : 0;
  return h("span", { class: "bars", title: rssi === null || rssi === undefined ? "kein Empfang bekannt" : `${num(rssi)} dBm` },
    [1, 2, 3, 4].map((i) => h("span", { class: i <= level ? "on" : "", style: `height:${i * 3}px` })));
}

function isMulti(entry) {
  return !!(entry && entry.hub && entry.hub.radios && entry.hub.radios.length > 1);
}

function radioName(entry, id) {
  const radio = entry.hub.radios.find((r) => r.id === id);
  return radio ? radio.name : entry.hub.radios[0].name;
}

function chip(text, kind = "") {
  return h("span", { class: `chip ${kind}` }, text);
}

function icon(name) {
  return h("ha-icon", { icon: name });
}

function sameValue(a, b) {
  if (typeof a === "number" || typeof b === "number") return Number(a) === Number(b);
  return String(a) === String(b);
}

function effective(item) {
  return item.pending === null || item.pending === undefined ? item.value : item.pending;
}

function formatConfig(item, value) {
  if (item.type === "select") {
    const opt = item.options.find((o) => sameValue(o.value, value));
    return opt ? opt.label : String(value);
  }
  return `${plainNum(value)}${item.unit ? " " + item.unit : ""}`;
}

// --- Element ---------------------------------------------------------------

class Eq3MaxPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._selected = null; // {entryId, serial}
    this._tab = "links";
    this._drafts = {}; // "serial:kind" -> {key: value}
    this._confirm = null; // "serial:kind"
    this._busy = new Set();
    this._pairingUntil = {}; // entry_id -> ms
    this._toast = null;
    this._narrow = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
    if (first && this.isConnected) this._start();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    const changed = this._narrow !== !!value;
    this._narrow = !!value;
    if (changed) this._render();
  }

  set panel(value) {
    this._panel = value;
  }

  connectedCallback() {
    if (this._hass) this._start();
    this._timer = window.setInterval(() => this._tick(), 1000);
    this._render();
  }

  disconnectedCallback() {
    window.clearInterval(this._timer);
    this._removeEscape();
    this._stop();
  }

  async _start() {
    if (this._started) return;
    this._started = true;
    // Generation: a _stop() while awaiting the subscription makes this start stale.
    const gen = (this._gen = (this._gen || 0) + 1);
    const connection = this._hass.connection;
    let unsub = null;
    try {
      unsub = await connection.subscribeMessage(() => this._load(), { type: "eq3_max/subscribe" });
    } catch (err) {
      this._error = err.message || String(err);
    }
    if (gen !== this._gen || !this._started) {
      if (unsub) unsub().catch(() => {});
      return;
    }
    this._unsub = unsub;
    this._onReady = () => this._load();
    this._readyConnection = connection;
    connection.addEventListener("ready", this._onReady);
    await this._load();
  }

  _stop() {
    this._gen = (this._gen || 0) + 1;
    if (this._unsub) {
      this._unsub().catch(() => {});
      this._unsub = null;
    }
    if (this._onReady && this._readyConnection) {
      this._readyConnection.removeEventListener("ready", this._onReady);
    }
    this._onReady = null;
    this._readyConnection = null;
    this._started = false;
  }

  async _load() {
    // Only the newest request counts: an older, slower answer must not win.
    const seq = (this._loadSeq = (this._loadSeq || 0) + 1);
    let data;
    let error = null;
    try {
      data = await this._hass.connection.sendMessagePromise({ type: "eq3_max/overview" });
    } catch (err) {
      error = err.message || String(err);
    }
    if (seq !== this._loadSeq) return;
    if (error) {
      this._error = error;
    } else {
      this._data = data;
      this._error = null;
      for (const entry of data.entries) {
        if (!entry.hub) continue;
        const remaining = entry.hub.pairing_remaining;
        this._pairingUntil[entry.entry_id] = remaining > 0 ? Date.now() + remaining * 1000 : 0;
      }
    }
    this._requestRender();
  }

  async _call(busyKey, message, success) {
    this._busy.add(busyKey);
    this._render();
    try {
      const result = await this._hass.connection.sendMessagePromise(message);
      if (success) this._showToast(typeof success === "function" ? success(result) : success);
      return result;
    } catch (err) {
      this._showToast(err.message || String(err), true);
      return undefined;
    } finally {
      this._busy.delete(busyKey);
      await this._load();
    }
  }

  _showToast(text, error = false) {
    this._toast = { text, error };
    window.clearTimeout(this._toastTimer);
    this._toastTimer = window.setTimeout(() => {
      this._toast = null;
      this._requestRender();
    }, error ? 8000 : 4000);
    this._requestRender();
  }

  /** Is the user typing in a form field of the drawer? Then pushes wait. */
  _editing() {
    const el = this.shadowRoot.activeElement;
    return !!(el && (el.tagName === "INPUT" || el.tagName === "SELECT") && el.closest(".drawer"));
  }

  /** Render for background changes (push, toast): not while typing, then shortly after. */
  _requestRender() {
    if (!this._editing()) {
      this._render();
      return;
    }
    if (this._deferred) return;
    this._deferred = true;
    const retry = () => {
      // Short delay: a click on a button that blurred the field must land first.
      window.setTimeout(() => {
        if (this._editing()) {
          this.shadowRoot.addEventListener("focusout", retry, { once: true });
          return;
        }
        this._deferred = false;
        this._render();
      }, 300);
    };
    this.shadowRoot.addEventListener("focusout", retry, { once: true });
  }

  _tick() {
    for (const el of this.shadowRoot.querySelectorAll("[data-ago]")) el.textContent = ago(Number(el.dataset.ago));
    let ended = false;
    for (const [entryId, until] of Object.entries(this._pairingUntil)) {
      if (!until) continue;
      const left = Math.max(0, Math.round((until - Date.now()) / 1000));
      if (left === 0) {
        // Countdown over: render once, then the entry is 0 and stays quiet.
        this._pairingUntil[entryId] = 0;
        ended = true;
        continue;
      }
      const el = this.shadowRoot.querySelector(`[data-pairing="${CSS.escape(entryId)}"]`);
      if (el) el.textContent = `Anlernen läuft … ${left} s`;
    }
    if (ended) this._requestRender();
  }

  // --- Lookup ---

  _device(entryId, serial) {
    const entry = this._data && this._data.entries.find((e) => e.entry_id === entryId);
    return entry ? entry.devices.find((d) => d.serial === serial) : undefined;
  }

  // --- Rendering ---

  _render() {
    const root = this.shadowRoot;
    const active = root.activeElement;
    const focusKey = active && active.dataset ? active.dataset.focus : undefined;
    const scroll = root.querySelector(".body");
    const scrollTop = scroll ? scroll.scrollTop : 0;

    const nodes = [
      h("style", {}, STYLE),
      this._renderToolbar(),
      h("main", {}, this._renderMain()),
      this._renderDrawer(),
      this._toast ? h("div", { class: `toast ${this._toast.error ? "error" : ""}`, role: "status" }, this._toast.text) : null,
    ];
    root.replaceChildren(...nodes.flat(Infinity).filter((node) => node));

    const body = root.querySelector(".body");
    if (body) body.scrollTop = scrollTop;
    if (focusKey) {
      const el = root.querySelector(`[data-focus="${CSS.escape(focusKey)}"]`);
      if (el) el.focus();
    }
  }

  _renderToolbar() {
    let menu = null;
    if (customElements.get("ha-menu-button")) {
      // Hides itself when the sidebar is docked.
      menu = h("ha-menu-button", {});
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    } else if (this._narrow) {
      menu = h("button", {
        class: "menu-btn",
        title: "Menü",
        "aria-label": "Menü",
        onclick: () => this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })),
      }, "☰");
    }
    return h("div", { class: "toolbar" }, menu, h("span", {}, "eQ-3 MAX!"));
  }

  _renderMain() {
    if (this._error && !this._data) return h("div", { class: "notice" }, `Fehler: ${this._error}`);
    if (!this._data) return h("div", { class: "empty" }, "Lade …");
    if (!this._data.entries.length) return h("div", { class: "empty" }, "Keine eQ-3-MAX!-Integration eingerichtet.");
    return this._data.entries.map((entry) => this._renderEntry(entry));
  }

  _renderEntry(entry) {
    if (!entry.loaded) {
      return h("section", { class: "entry" },
        h("div", { class: "notice" }, `${entry.title}: Integration nicht geladen (Zustand „${entry.state}“).`));
    }
    const groups = new Map();
    for (const dev of entry.devices) {
      const key = dev.area_id || "";
      if (!groups.has(key)) groups.set(key, { name: dev.area_name || "Ohne Bereich", devices: [] });
      groups.get(key).devices.push(dev);
    }
    const ordered = [...groups.entries()].sort(([ka, a], [kb, b]) => {
      if (!ka) return 1;
      if (!kb) return -1;
      return a.name.localeCompare(b.name, "de");
    });
    return h("section", { class: "entry" },
      this._renderHub(entry),
      entry.devices.length ? null : h("div", { class: "empty" }, "Noch keine Geräte angelernt."),
      ordered.map(([, group]) => [
        h("h2", { class: "area" }, group.name),
        h("div", { class: "grid" }, group.devices.map((dev) => this._renderCard(entry, dev))),
      ]),
    );
  }

  _airtime(airtime, limit) {
    const ratio = Math.min(1, airtime / limit);
    const meterClass = ratio >= AIRTIME_ALARM ? "alarm" : ratio >= AIRTIME_WARN ? "warn" : "";
    return h("span", { class: "item", title: `Sendezeit der letzten Stunde (Grenze ${limit} s)` },
      "Sendezeit", h("span", { class: `meter ${meterClass}` }, h("span", { style: `width:${ratio * 100}%` })),
      `${num(airtime)} / ${limit} s`);
  }

  _connection(item) {
    return h("span", { class: "item", title: item.version || "" },
      icon(item.connection === "network" ? "mdi:lan" : "mdi:usb"),
      `${item.connection === "network" ? "Netzwerk" : "USB"} · ${item.target}`);
  }

  _renderHub(entry) {
    const hub = entry.hub;
    const multi = isMulti(entry);
    const left = Math.max(0, Math.round(((this._pairingUntil[entry.entry_id] || 0) - Date.now()) / 1000));
    const busy = this._busy.has(`pair:${entry.entry_id}`);
    return h("div", { class: "hub" },
      h("span", { class: "title" }, entry.title),
      h("span", { class: "item" }, h("span", { class: `dot ${hub.connected ? "ok" : ""}` }),
        hub.connected ? "verbunden" : multi ? "nicht alle verbunden" : "getrennt"),
      multi ? null : this._connection(hub),
      multi ? null : this._airtime(hub.airtime, hub.airtime_limit),
      h("span", { class: "item" }, `Warteschlange: ${hub.queue}`),
      h("span", { class: "spacer" }),
      h("button", {
        class: "action primary",
        "data-pairing": entry.entry_id,
        disabled: left > 0 || busy || !hub.any_connected,
        title: hub.any_connected ? "Neue Geräte 60 s lang annehmen" : "Funkmodul nicht verbunden",
        onclick: () => this._call(`pair:${entry.entry_id}`, { type: "eq3_max/pair", entry_id: entry.entry_id },
          "Anlernen 60 s geöffnet – jetzt am Gerät die Anlerntaste drücken."),
      }, left > 0 ? `Anlernen läuft … ${left} s` : "Anlernen (60 s)"),
      multi
        ? h("div", { class: "radios" }, hub.radios.map((radio) => h("div", { class: "radio" },
          h("span", { class: "name" }, h("span", { class: `dot ${radio.connected ? "ok" : ""}` }), radio.name),
          this._connection(radio),
          this._airtime(radio.airtime, hub.airtime_limit),
          h("span", { class: "item" }, `Warteschlange: ${radio.queue}`))))
        : null,
    );
  }

  _renderCard(entry, dev) {
    const st = dev.state;
    const badges = [];
    if (dev.pending) badges.push(chip("ausstehend", "warn"));
    if (st.command_failed || st.config_failed.length) badges.push(chip("nicht quittiert", "error"));
    if (st.rf_error) badges.push(chip("Funkfehler", "error"));
    if (st.battery_low) badges.push(chip("Batterie schwach", "error"));

    let body;
    if (dev.type === "heating_thermostat" || dev.type === "wall_thermostat") {
      const mode = st.hvac === "off" ? HVAC_LABELS.off : PRESET_LABELS[st.preset] || MODE_LABELS[st.mode] || "–";
      body = [
        h("div", { class: "big" }, `${num(st.measured)} °C → ${num(st.target)} °C`),
        h("div", { class: "sub" }, mode),
        dev.type === "heating_thermostat"
          ? h("div", { class: "valve" }, "Ventil",
            h("span", { class: "meter" }, h("span", { style: `width:${st.valve || 0}%` })),
            st.valve === null ? "–" : `${st.valve} %`)
          : null,
      ];
    } else if (dev.type === "shutter_contact") {
      body = h("div", { class: "big" }, st.window_open === null ? "unbekannt" : st.window_open ? "offen" : "geschlossen");
    } else {
      body = h("div", { class: "sub" }, dev.type_name);
    }
    const linkCount = dev.links.partners.length;
    const open = () => this._open(entry.entry_id, dev.serial);
    return h("div", {
      class: `card ${st.rf_error ? "rf" : ""}`,
      "data-serial": dev.serial,
      tabindex: "0",
      role: "button",
      onclick: open,
      onkeydown: (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } },
    },
      h("div", { class: "head" }, icon(TYPE_ICONS[dev.type] || "mdi:help"), h("span", { class: "name", title: dev.name }, dev.name), badges),
      body,
      h("div", { class: "foot" },
        h("span", {}, st.battery_low ? "Batterie schwach" : st.battery_low === false ? "Batterie ok" : "Batterie ?"),
        h("span", {}, rssiBars(st.rssi), " ", st.rssi === null ? "– dBm" : `${num(st.rssi)} dBm`),
        h("span", { "data-ago": st.last_seen || 0 }, ago(st.last_seen)),
        h("span", {}, linkCount === 1 ? "1 Verknüpfung" : `${linkCount} Verknüpfungen`),
        isMulti(entry) ? h("span", { class: "radio-tag", title: "Funkmodul" }, icon("mdi:radio-tower"), radioName(entry, dev.radio)) : null,
      ),
    );
  }

  _open(entryId, serial) {
    this._selected = { entryId, serial };
    this._tab = "links";
    this._confirm = null;
    this._render();
    // Escape closes from anywhere while the drawer is open.
    this._removeEscape();
    this._onEscape = (ev) => {
      if (ev.key === "Escape" && this._selected) this._close();
    };
    document.addEventListener("keydown", this._onEscape);
    const target = this.shadowRoot.querySelector(".drawer .close");
    if (target) target.focus();
  }

  _removeEscape() {
    if (this._onEscape) document.removeEventListener("keydown", this._onEscape);
    this._onEscape = null;
  }

  _close() {
    const serial = this._selected ? this._selected.serial : null;
    this._selected = null;
    this._confirm = null;
    this._removeEscape();
    this._render();
    // Back to the card the drawer was opened from.
    const card = serial && this.shadowRoot.querySelector(`.card[data-serial="${CSS.escape(serial)}"]`);
    if (card) card.focus();
  }

  _renderDrawer() {
    if (!this._selected) return null;
    const dev = this._device(this._selected.entryId, this._selected.serial);
    if (!dev) {
      this._selected = null;
      this._removeEscape();
      return null;
    }
    const entry = this._data.entries.find((e) => e.entry_id === this._selected.entryId);
    const available = [["links", "Verknüpfungen"]];
    if (dev.config.length > 0) available.push(["config", "Konfiguration"]);
    if (isMulti(entry)) available.push(["radio", "Funkmodul"]);
    if (!available.some(([key]) => key === this._tab)) this._tab = "links";
    const tabs = available.length > 1
      ? h("div", { class: "tabs", role: "tablist" },
        available.map(([key, label]) =>
          h("button", {
            class: this._tab === key ? "active" : "",
            role: "tab",
            "aria-selected": this._tab === key ? "true" : "false",
            onclick: () => { this._tab = key; this._confirm = null; this._render(); },
          }, label)))
      : null;
    return [
      h("div", { class: "overlay", onclick: () => this._close() }),
      h("aside", { class: "drawer", role: "dialog", "aria-modal": "true", "aria-label": dev.name },
        h("header", {},
          icon(TYPE_ICONS[dev.type] || "mdi:help"),
          h("div", { class: "t" },
            h("div", {}, dev.name),
            h("div", {}, `${dev.type_name} · ${dev.area_name || "Ohne Bereich"}`),
            h("div", {}, `Seriennummer ${dev.serial} · Adresse ${dev.address}${dev.firmware ? " · Firmware " + dev.firmware : ""}`)),
          h("button", { class: "close", title: "Schließen", "aria-label": "Schließen", onclick: () => this._close() }, "✕")),
        tabs,
        h("div", { class: "body" },
          this._tab === "config" ? this._renderConfig(dev)
            : this._tab === "radio" ? this._renderRadio(entry, dev)
              : this._renderLinks(dev)),
      ),
    ];
  }

  // --- Funkmodul ---

  _renderRadio(entry, dev) {
    const rssi = dev.state.rssi_by_radio || {};
    const heard = entry.hub.radios.filter((r) => rssi[r.id] !== undefined);
    const best = heard.length ? heard.reduce((a, b) => (rssi[b.id] > rssi[a.id] ? b : a)).id : null;
    const busy = this._busy.has(`radio:${dev.serial}`);
    return [
      h("div", { class: "notice" },
        "Alle Funkmodule nutzen dieselbe Zentralen-Adresse. Das zugeordnete Modul sendet die Befehle an das Gerät, "
        + "empfangen wird über alle. Umstellen sendet nichts an das Gerät und braucht kein Neuanlernen."),
      h("div", {}, entry.hub.radios.map((radio) => h("div", { class: "row" },
        h("span", { class: "grow" }, h("span", { class: `dot ${radio.connected ? "ok" : ""}`, style: "display:inline-block;margin-right:8px" }), radio.name),
        rssiBars(rssi[radio.id]),
        h("span", {}, rssi[radio.id] === undefined ? "nicht gehört" : `${num(rssi[radio.id])} dBm`),
        radio.id === best && heard.length > 1 ? chip("bester Empfang", "ok") : null,
        dev.radio === radio.id
          ? chip("zugeordnet", "ok")
          : h("button", {
            class: "action",
            disabled: busy || !dev.device_id,
            title: radio.connected ? "" : "Funkmodul ist gerade nicht verbunden",
            onclick: () => this._call(`radio:${dev.serial}`,
              { type: "eq3_max/set_radio", device_id: dev.device_id, radio: radio.id },
              `${dev.name} sendet jetzt über ${radio.name}.`),
          }, "Zuordnen"),
        h("span", { class: "hint" }, `${radio.connection === "network" ? "Netzwerk" : "USB"} · ${radio.target}`)))),
      h("div", { class: "sub", style: "margin-top:6px;color:var(--e3-muted);font-size:12px" },
        "Empfangswerte stammen aus den letzten Telegrammen des Geräts. Ein Modul, das das Gerät nie gehört hat, "
        + "erreicht es vermutlich auch beim Senden nicht."),
    ];
  }

  // --- Verknüpfungen ---

  _linkCall(op, dev, partner) {
    const key = `${op}:${dev.serial}:${partner.serial}`;
    const text = op === "link"
      ? `Verknüpfung mit ${partner.name} beauftragt.`
      : `Lösen von ${partner.name} beauftragt.`;
    return this._call(key, { type: `eq3_max/${op}`, device_id: dev.device_id, partner_device_id: partner.device_id }, text);
  }

  _linkButton(op, dev, partner, label, danger = false) {
    return h("button", {
      class: `action ${danger ? "danger" : ""}`,
      disabled: this._busy.has(`${op}:${dev.serial}:${partner.serial}`) || !partner.device_id || !dev.device_id,
      onclick: (ev) => { ev.stopPropagation(); this._linkCall(op, dev, partner); },
    }, label);
  }

  _renderLinks(dev) {
    const rows = [];
    for (const partner of dev.links.partners) {
      rows.push(h("div", { class: "row" },
        h("span", { class: "grow" }, partner.name),
        chip("verknüpft", "ok"),
        this._linkButton("unlink", dev, partner, "Lösen", true)));
    }
    for (const item of dev.links.pending) {
      const buttons = [];
      if (item.state === "failed" || item.state === "rejected") {
        buttons.push(this._linkButton(item.op === "remove" ? "unlink" : "link", dev, item, "Erneut senden"));
      }
      if (item.state === "one_sided") buttons.push(this._linkButton("link", dev, item, "Verknüpfen"));
      if (item.op !== "remove") buttons.push(this._linkButton("unlink", dev, item, "Lösen", true));
      const what = item.op === "remove" ? "Lösen" : item.op === "add" ? "Verknüpfen" : null;
      rows.push(h("div", { class: "row" },
        h("span", { class: "grow" }, item.name),
        chip(LINK_LABELS[item.state] || item.state, LINK_CHIP[item.state] || ""),
        buttons,
        h("span", { class: "hint" }, what ? `${what}: ${item.text}` : item.text)));
    }

    const select = h("select", { "data-focus": `cand:${dev.serial}`, "aria-label": "Partner auswählen" },
      h("option", { value: "" }, dev.candidates.length ? "Partner auswählen …" : "kein weiteres Gerät möglich"),
      dev.candidates.map((c) => h("option", { value: c.serial }, c.name)));
    if (this._candidate && dev.candidates.some((c) => c.serial === this._candidate)) select.value = this._candidate;
    select.addEventListener("change", () => { this._candidate = select.value; this._render(); });
    const chosen = dev.candidates.find((c) => c.serial === select.value);

    return [
      dev.sleeper && SLEEPER_HINTS[dev.type] ? h("div", { class: "notice" }, SLEEPER_HINTS[dev.type]) : null,
      h("div", {},
        rows.length ? rows : h("div", { class: "empty" }, "Keine Verknüpfungen.")),
      h("div", {},
        h("div", { class: "sub", style: "margin-bottom:6px;font-weight:500" }, "Partner hinzufügen"),
        h("div", { class: "add" },
          select,
          h("button", {
            class: "action primary",
            disabled: !chosen || this._busy.has(`link:${dev.serial}:${chosen ? chosen.serial : ""}`),
            onclick: async () => {
              if (!chosen) return;
              this._candidate = null;
              await this._linkCall("link", dev, chosen);
            },
          }, "Verknüpfen")),
        h("div", { class: "sub", style: "margin-top:6px;color:var(--e3-muted);font-size:12px" },
          "Zur Auswahl stehen nur Geräte, die sich mit diesem verknüpfen lassen und noch nicht verknüpft oder beauftragt sind.")),
    ];
  }

  // --- Konfiguration ---

  _draftKey(dev, set) {
    return `${dev.serial}:${set.kind}`;
  }

  _changes(dev, set) {
    const draft = this._drafts[this._draftKey(dev, set)] || {};
    const changes = {};
    for (const item of set.values) {
      if (!(item.key in draft)) continue;
      const raw = draft[item.key];
      const value = item.type === "number" ? Number(String(raw).replace(",", ".")) : this._optionValue(item, raw);
      if (!sameValue(value, effective(item))) changes[item.key] = value;
    }
    return changes;
  }

  _optionValue(item, raw) {
    const opt = item.options.find((o) => String(o.value) === String(raw));
    return opt ? opt.value : raw;
  }

  _valid(item, raw) {
    if (item.type !== "number") return true;
    const value = Number(String(raw).replace(",", "."));
    if (String(raw).trim() === "" || Number.isNaN(value) || value < item.min || value > item.max) return false;
    const steps = (value - item.min) / item.step;
    return Math.abs(steps - Math.round(steps)) < 1e-9;
  }

  _renderConfig(dev) {
    return [
      h("div", { class: "sub", style: "color:var(--e3-muted);font-size:13px" },
        "Das Gerät übernimmt nur ganze Sätze: Werte ändern und den Satz mit einem Klick senden. " +
        "Gezeigt wird der zuletzt quittierte Wert; „ausstehend“ heißt gesendet, aber noch nicht quittiert."),
      dev.config.map((set) => this._renderSet(dev, set)),
    ];
  }

  _renderSet(dev, set) {
    const dk = this._draftKey(dev, set);
    const busy = this._busy.has(`cfg:${dk}`);
    const draftOf = () => this._drafts[dk] || {};
    const refs = []; // {item, control, error}

    const rows = set.values.map((item) => {
      const draft = draftOf();
      const current = item.key in draft ? draft[item.key] : effective(item);
      let control;
      if (item.type === "select") {
        control = h("select", { "data-focus": `cfg:${dk}:${item.key}`, "aria-label": item.label },
          item.options.map((o) => h("option", { value: String(o.value) }, o.label)));
      } else {
        control = h("input", {
          type: "number", min: String(item.min), max: String(item.max), step: String(item.step),
          inputmode: "decimal", "data-focus": `cfg:${dk}:${item.key}`, "aria-label": item.label,
        });
      }
      control.value = String(current);
      // Nur den Entwurf merken und den Satz vor Ort auffrischen: kein Neuaufbau, der
      // Fokus und Eingabe stören würde.
      control.addEventListener(item.type === "select" ? "change" : "input", () => {
        this._drafts[dk] = { ...draftOf(), [item.key]: control.value };
        if (this._confirm === dk) {
          this._confirm = null;
          confirmBox.replaceChildren();
        }
        update();
      });
      const error = h("span", { style: "color:var(--e3-error)" });
      refs.push({ item, control, error });
      const meta = [chip(SOURCE_LABELS[item.source] || item.source || "?",
        item.source === "werksvorgabe" ? "warn" : item.source === "gesetzt" ? "ok" : "info")];
      if (item.pending !== null && item.pending !== undefined) {
        meta.push(chip(`ausstehend: ${formatConfig(item, item.pending)}`, "warn"));
        meta.push(h("span", {}, `quittiert: ${formatConfig(item, item.value)}`));
      }
      if (item.type === "number") {
        meta.push(h("span", {}, `${plainNum(item.min)} … ${plainNum(item.max)}, Schritt ${plainNum(item.step)}`));
      }
      meta.push(error);
      return h("div", { class: "cfg" },
        h("span", { class: "label" }, item.label),
        h("span", { class: "ctl" }, control, item.unit ? h("span", { class: "sub" }, item.unit) : null),
        h("div", { class: "meta" }, meta));
    });

    const status = [];
    if (set.pending) status.push(chip("Satz ausstehend", "warn"));
    if (set.failed) status.push(chip("nicht quittiert – wird beim nächsten Melden erneut gesendet", "error"));

    const count = h("span", { class: "sub" });
    const discard = h("button", {
      class: "action",
      onclick: () => { delete this._drafts[dk]; this._confirm = null; this._render(); },
    }, "Verwerfen");
    const send = h("button", { class: "action primary", onclick: () => { this._confirm = dk; this._render(); } }, "Satz senden");
    const confirmBox = h("div", {});

    const update = () => {
      const draft = draftOf();
      const changes = this._changes(dev, set);
      let invalid = false;
      for (const { item, control, error } of refs) {
        const bad = item.key in draft && !this._valid(item, draft[item.key]);
        invalid = invalid || bad;
        control.classList.toggle("changed", item.key in changes);
        error.textContent = bad
          ? `Wert muss zwischen ${plainNum(item.min)} und ${plainNum(item.max)} in Schritten von ${plainNum(item.step)} liegen`
          : "";
      }
      const n = Object.keys(changes).length;
      count.textContent = n ? `${n} geändert` : "";
      discard.style.display = Object.keys(draft).length ? "" : "none";
      send.disabled = !n || invalid || busy || !dev.device_id;
      return { changes, invalid };
    };
    const { changes, invalid } = update();

    if (this._confirm === dk && Object.keys(changes).length && !invalid) {
      const factory = set.values.filter((item) => !(item.key in changes) && item.source === "werksvorgabe" &&
        (item.pending === null || item.pending === undefined));
      confirmBox.append(h("div", { class: "confirm" },
        h("div", {}, `Satz „${set.title}“ an ${dev.name} senden:`),
        h("ul", {}, set.values.filter((item) => item.key in changes).map((item) =>
          h("li", {}, `${item.label}: ${formatConfig(item, effective(item))} → ${formatConfig(item, changes[item.key])}`))),
        factory.length
          ? h("div", {}, "Mit dem Satz gehen diese angenommenen Werksvorgaben mit (am Gerät nie gelesen):",
            h("ul", {}, factory.map((item) => h("li", {}, `${item.label}: ${formatConfig(item, item.value)}`))))
          : h("div", {}, "Alle übrigen Werte des Satzes sind bekannt."),
        h("div", { class: "setfoot" },
          h("button", { class: "action", onclick: () => { this._confirm = null; this._render(); } }, "Abbrechen"),
          h("button", { class: "action primary", disabled: busy || !dev.device_id, onclick: () => this._sendSet(dev, set, changes) }, "Senden"))));
    }

    return h("fieldset", {},
      h("legend", {}, set.title),
      status.length ? h("div", { class: "add", style: "margin-bottom:6px" }, status) : null,
      rows,
      h("div", { class: "setfoot" }, count, discard, send),
      confirmBox);
  }

  async _sendSet(dev, set, changes) {
    const dk = this._draftKey(dev, set);
    const result = await this._call(`cfg:${dk}`,
      { type: "eq3_max/set_config", device_id: dev.device_id, kind: set.kind, values: changes },
      (res) => {
        const labels = set.values.filter((item) => res.factory_keys.includes(item.key)).map((item) => item.label);
        return `Satz „${set.title}“ gesendet – wartet auf Quittung.` +
          (labels.length ? ` Werksvorgaben mitgesendet: ${labels.join(", ")}.` : "");
      });
    if (result !== undefined) {
      delete this._drafts[dk];
      this._confirm = null;
      this._render();
    }
  }
}

if (!customElements.get("eq3-max-panel")) customElements.define("eq3-max-panel", Eq3MaxPanel);
