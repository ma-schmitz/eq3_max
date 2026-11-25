// eQ-3 MAX! Thermostat Card – Lovelace-Karte für Thermostate der Integration eq3_max.
// Wird mit der Integration ausgeliefert und von ihr als Dashboard-Ressource eingetragen.
// Eine Datei ohne Build-Schritt. Oben die reinen Funktionen (exportiert, mit node --test
// geprüft), unten die Karte, das Pop-up und der Editor (nur im Browser).

// Gleich der Version der Integration (tests/ha/test_card_resource.py prüft das).
export const VERSION = "0.11.0";

// Wochentage, wie eq3_max sie speichert und der Dienst set_week_profile sie nimmt.
export const WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

// Werte, die eq3_max an die Thermostate des Raums weitergibt (ROOM_CONFIG_KEYS).
export const ROOM_KEYS = [
  "komfort", "eco", "maximal", "minimal", "fenster_temperatur", "fenster_dauer",
  "boost_dauer", "boost_ventil", "entkalkung_tag", "entkalkung_stunde",
];

export const MIN_TEMP = 4.5;
export const MAX_TEMP = 30.5;
// Range and step of a MAX! thermostat in °C: the week program, and the target where the
// climate entity says nothing else.
const MAX_RANGE = { min: MIN_TEMP, max: MAX_TEMP, step: 0.5 };

const WORKDAY = [
  { temperature: 17, until: "06:00" }, { temperature: 21, until: "09:00" },
  { temperature: 17, until: "17:00" }, { temperature: 21, until: "23:00" }, { temperature: 17, until: "24:00" },
];
const WEEKEND = [{ temperature: 17, until: "06:00" }, { temperature: 21, until: "22:00" }, { temperature: 17, until: "24:00" }];
// Werksprogramm der Thermostate (wie eq3_max: FACTORY_WEEK_PROFILE).
export const FACTORY_WEEK_PROFILE = {
  Montag: WORKDAY, Dienstag: WORKDAY, Mittwoch: WORKDAY, Donnerstag: WORKDAY, Freitag: WORKDAY,
  Samstag: WEEKEND, Sonntag: WEEKEND,
};

// --- Texte (Schlüssel = deutscher Text) -------------------------------------
const EN = {
  "Manuell": "Manual", "Auto": "Auto", "Komfort": "Comfort", "Eco": "Eco", "Boost": "Boost", "Aus": "Off",
  "Abwesend bis {time}": "Away until {time}", "Abwesend": "Away",
  "Ventil": "Valve", "Fenster": "Window", "offen": "open", "zu": "closed",
  "Fenster offen": "Window open", "Fenster geschlossen": "Window closed",
  "Tür offen": "Door open", "Tür geschlossen": "Door closed",
  "Batterie ok": "Battery ok", "Batterie schwach": "Battery low",
  "Funk {dbm} dBm": "Radio {dbm} dBm", "Funkfehler": "Radio error",
  "verknüpft mit {names}": "linked with {names}", "Bediensperre": "Operation locked",
  "Befehl ausstehend": "Command pending", "vor {n} min": "{n} min ago", "vor {n} h": "{n} h ago", "gerade eben": "just now",
  "Heizkörperthermostat": "Radiator thermostat", "Wandthermostat": "Wall thermostat",
  "Einstellungen": "Settings", "Temperaturen": "Temperatures", "Boost & Ventil": "Boost & valve",
  "Boost & Anzeige": "Boost & display", "Wochenprogramm": "Week program", "Info": "Info",
  "Komforttemperatur": "Comfort temperature", "Eco-Temperatur": "Eco temperature",
  "Maximaltemperatur": "Maximum temperature", "Minimaltemperatur": "Minimum temperature",
  "Temperatur-Offset": "Temperature offset", "Korrektur der Messung": "Correction of the measurement",
  "Grenze am Drehrad": "Limit on the wheel", "Fenster-auf-Temperatur": "Window-open temperature",
  "Fenster-auf-Dauer": "Window-open duration", "0 = Erkennung aus": "0 = detection off",
  "Boost-Dauer": "Boost duration", "Boost-Ventilstellung": "Boost valve position", "Entkalkung Tag": "Decalcification day",
  "Entkalkung Stunde": "Decalcification hour", "Ventil maximal": "Valve maximum", "Ventil-Offset": "Valve offset",
  "Anzeige": "Display", "Soll-Temperatur": "Set temperature", "Ist-Temperatur": "Current temperature",
  "gilt für den Raum": "applies to the room", "ausstehend: {value}": "pending: {value}",
  "{n} geändert": "{n} changed", "Verwerfen": "Discard", "Übernehmen": "Apply", "Schließen": "Close",
  "Verknüpfte Fensterkontakte": "Linked window contacts", "keiner": "none",
  "Batterie": "Battery", "Funk": "Radio", "Zuletzt": "Last seen", "Verknüpft": "Linked", "Gerät": "Device",
  "ok": "ok", "schwach": "low", "an": "on", "aus": "off",
  "Nur Anzeige: Änderungen sind für dein Konto gesperrt (Option der Integration).":
    "View only: changes are locked for your account (option of the integration).",
  "unbekannt": "unknown", "{day} bearbeiten": "Edit {day}", "Vorlage: Werksprogramm": "Template: factory program",
  "Zeitraum einfügen": "Insert period", "Schreiben auf:": "Write to:", "alle": "all", "keinen": "none",
  "Auf {n} Tage schreiben": "Write to {n} days", "Auf 1 Tag schreiben": "Write to 1 day",
  "Kopieren von …": "Copy from …", "Geht auch an: {names}": "Also goes to: {names}",
  "schreibt: {days}": "writing: {days}",
  "Das Gerät meldet sein Programm nicht. Gezeigt wird, was es zuletzt quittiert hat. Jeder Tag ist ein Funktelegramm; bei knappem Funkbudget kann eine Woche einige Minuten dauern.":
    "The device does not report its program. Shown is what it acknowledged last. Every day is one radio telegram; with little airtime left a week can take a few minutes.",
  "Letztes Schreiben abgebrochen": "Last write stopped",
  "Gesendet – wartet auf Quittung.": "Sent – waiting for acknowledgement.",
  "Vom Gerät quittiert.": "Acknowledged by the device.",
  "Wochenprogramm wird geschrieben.": "Week program is being written.",
  "bis": "until", "Montag": "Monday", "Dienstag": "Tuesday", "Mittwoch": "Wednesday", "Donnerstag": "Thursday",
  "Freitag": "Friday", "Samstag": "Saturday", "Sonntag": "Sunday",
  "Mo": "Mo", "Di": "Tu", "Mi": "We", "Do": "Th", "Fr": "Fr", "Sa": "Sa", "So": "Su",
  "Kein eq3_max-Thermostat gewählt.": "No eq3_max thermostat selected.",
  "Entität {entity} nicht gefunden.": "Entity {entity} not found.",
  "Entität": "Entity", "Layout": "Layout", "Name (optional)": "Name (optional)", "Modus-Knöpfe zeigen": "Show mode buttons",
  "kompakt": "compact", "ring": "ring", "kachel": "tile",
  "Ist {value} {unit}": "Now {value} {unit}", "nicht verfügbar": "unavailable",
  "Externer Temperatursensor (optional)": "External temperature sensor (optional)",
  "Externer Feuchtesensor (optional)": "External humidity sensor (optional)",
  "Luftfeuchte": "Humidity",
  "Thermostat {value} {unit}": "Thermostat {value} {unit}",
  "Entität {entity} gehört nicht zur Integration eq3_max.": "Entity {entity} does not belong to the eq3_max integration.",
  "Messwert am Thermostat (am Heizkörper)": "Reading at the thermostat (at the radiator)",
  "Temperatur für die Komfort-Taste am Gerät und das Preset „Komfort“. Gilt für den ganzen Raum.": "Temperature of the comfort button on the device and of the preset \"Comfort\". Applies to the whole room.",
  "Absenktemperatur für die Eco-Taste, den Eco-Taster und das Preset „Eco“. Gilt für den ganzen Raum.": "Setback temperature of the eco button, the eco push button and the preset \"Eco\". Applies to the whole room.",
  "Höchster Sollwert, der sich am Gerät einstellen lässt.": "Highest target that can be set on the device.",
  "Niedrigster Sollwert, der sich am Gerät einstellen lässt.": "Lowest target that can be set on the device.",
  "Korrigiert die gemessene Temperatur, z. B. −1 K, wenn das Thermostat direkt am Heizkörper zu warm misst.": "Corrects the measured temperature, e.g. −1 K if the thermostat measures too warm right at the radiator.",
  "Sollwert, solange ein Fenster offen ist – über einen Fensterkontakt oder die eigene Erkennung des Thermostats.": "Target while a window is open – from a window contact or the thermostat's own detection.",
  "So lange gilt die Fenster-auf-Temperatur, wenn das Thermostat selbst einen Temperatursturz erkennt. 0 = eigene Erkennung aus (ein Fensterkontakt wirkt weiter).": "How long the window-open temperature applies when the thermostat itself detects a temperature drop. 0 = own detection off (a window contact still works).",
  "Wie lange Boost das Ventil weit öffnet. Der Wandthermostat zählt seine Anzeige danach herunter.": "How long boost opens the valve wide. The wall thermostat counts its display down by it.",
  "Ventilöffnung während Boost.": "Valve opening during boost.",
  "Wochentag der Ventilfahrt gegen Festsitzen (Entkalkung).": "Weekday of the valve run against sticking (decalcification).",
  "Uhrzeit der wöchentlichen Ventilfahrt.": "Hour of the weekly valve run.",
  "Größte Ventilöffnung – begrenzt die Heizleistung dieses Heizkörpers.": "Largest valve opening – limits the heat output of this radiator.",
  "Verschiebt die Ventilstellung, z. B. bei Ventilen, die erst spät öffnen.": "Shifts the valve position, e.g. for valves that open late.",
  "Was das Display des Wandthermostats zeigt. Am Gerät ist das Menü gesperrt, solange es an einer Zentrale hängt.": "What the wall thermostat's display shows. Its menu is locked while it is paired with a central.",
  "Der Heizkörper meldet seine Ist-Temperatur nur, wenn sich bei ihm etwas ändert. eq3_max stößt ihn in diesem Abstand an (Sollwert +0,5 °C bis zur Meldung, etwa 1 min, dann zurück). Kostet zwei Telegramme und etwas Batterie; ausgelassen, wenn er von selbst gemeldet hat.": "The radiator reports its current temperature only when something changes on it. eq3_max nudges it at this interval (target +0.5 °C until it reports, about 1 min, then back). Costs two telegrams and some battery; skipped when it reported by itself.",
  "Erklärung": "Explanation", "Verlauf": "History",
  "Ist-Temperatur abfragen": "Poll current temperature",
  "Kurzer Anstoß (Sollwert +0,5 °C bis zur Meldung) – kostet Batterie": "Short nudge (target +0.5 °C until it reports) – costs battery",
  "alle 15 min": "every 15 min", "alle 30 min": "every 30 min", "stündlich": "every hour",
  "alle 2 Stunden": "every 2 hours", "alle 4 Stunden": "every 4 hours",
  "Die Endzeiten müssen von oben nach unten steigen.": "End times must rise from top to bottom.",
  "Endzeiten nur in 5-Minuten-Schritten.": "End times only in steps of 5 minutes.", "Seriennummer": "Serial number", "Firmware": "Firmware", "Hauptmodul": "Main module",
};

/** Text in the HA language; German is the key, everything not German falls back to English. */
export function t(lang, key, vars = {}) {
  const text = String(lang || "en").startsWith("de") ? key : (EN[key] ?? key);
  return text.replace(/\{(\w+)\}/g, (_, name) => (name in vars ? String(vars[name]) : `{${name}}`));
}

// --- Zustände -----------------------------------------------------------------

/** Radio quality from the RSSI (dBm) and the device's radio-error flag. */
export function rssiLevel(dbm, rfError) {
  if (rfError) return "off";
  if (dbm === null || dbm === undefined || Number.isNaN(Number(dbm))) return null;
  const v = Number(dbm);
  if (v > -70) return "good";
  if (v >= -85) return "mid";
  return "weak";
}

/** Entities of the thermostat's device by eq3_max key (translation_key); renames do not matter. */
export function findEntities(hass, climateId) {
  const all = hass?.entities;
  const own = all?.[climateId];
  if (!own || !own.device_id) return {};
  // Home Assistant sets hass on every state change of any entity, but replaces hass.entities
  // only when the registry changes: search once per registry and thermostat.
  let cache = ENTITY_CACHE.get(all);
  if (!cache) ENTITY_CACHE.set(all, (cache = new Map()));
  let found = cache.get(climateId);
  if (!found) {
    found = {};
    for (const entry of Object.values(all)) {
      if (entry.device_id !== own.device_id || entry.platform !== "eq3_max" || !entry.translation_key) continue;
      if (!(entry.translation_key in found)) found[entry.translation_key] = entry.entity_id;
    }
    cache.set(climateId, Object.freeze(found));
  }
  return found;
}
const ENTITY_CACHE = new WeakMap();

/** Range, step and unit of the target temperature as the climate entity reports them (Home
 *  Assistant converts to °F on an imperial system); the MAX! values where it says nothing. */
export function tempRange(hass, climate) {
  const attrs = climate?.attributes || {};
  const step = num(attrs.target_temp_step);
  return {
    min: num(attrs.min_temp) ?? MIN_TEMP,
    max: num(attrs.max_temp) ?? MAX_TEMP,
    step: step !== null && step > 0 ? step : 0.5,
    unit: hass?.config?.unit_system?.temperature || "°C",
  };
}

function snap(value, range) {
  const stepped = Math.round(value / range.step) * range.step;
  return Math.min(range.max, Math.max(range.min, Number(stepped.toFixed(2))));
}

/** Locale for numbers as set in the user's profile (hass.locale); undefined = the browser's. */
export function numberLocale(locale) {
  switch (locale?.number_format) {
    case "comma_decimal": return "en-US";
    case "decimal_comma": return "de";
    case "space_comma": return "fr";
    case "system": return undefined;
    default: return locale?.language || undefined;
  }
}

function num(value) {
  const n = Number(value);
  return value === null || value === undefined || value === "" || Number.isNaN(n) ? null : n;
}

// Symbols of a contact by the device class set in Home Assistant: [open, closed].
const CONTACT_ICONS = {
  door: ["mdi:door-open", "mdi:door-closed"],
  garage_door: ["mdi:garage-open", "mdi:garage"],
  window: ["mdi:window-open-variant", "mdi:window-closed-variant"],
};

/** Symbol of a contact: the one chosen for the entity in Home Assistant, else by its
 *  device class (door, garage door; everything else is a window). */
export function contactIcon(stateObj, open) {
  const attrs = stateObj?.attributes || {};
  if (attrs.icon) return attrs.icon;
  return (CONTACT_ICONS[attrs.device_class] || CONTACT_ICONS.window)[open ? 0 : 1];
}

/** "door" where every contact is a door (or garage door), else "window". */
export function contactKind(states) {
  const doors = states.filter((s) => ["door", "garage_door"].includes(s?.attributes?.device_class));
  return states.length && doors.length === states.length ? "door" : "window";
}

/** Symbol of the thermostat: the one chosen for the entity in Home Assistant, else by type. */
export function thermostatIcon(climate, isWall) {
  return climate?.attributes?.icon || (isWall ? "mdi:thermostat" : "mdi:radiator");
}

/** Window shown/open: linked contacts (attribute fenster), else the thermostat's own detection
 *  (manual mode at its window-open temperature). icon and kind follow what is set for the
 *  contacts in Home Assistant (an open one first). */
export function windowState(hass, climate, ents) {
  const contacts = climate?.attributes?.fenster || [];
  if (contacts.length) {
    const states = contacts.map((id) => hass.states[id]).filter(Boolean);
    const opened = states.filter((s) => s.state === "on");
    const open = opened.length > 0;
    return {
      shown: true,
      open,
      names: states.map((s) => s.attributes?.friendly_name || s.entity_id),
      icon: contactIcon(opened[0] || states[0], open),
      kind: contactKind(open ? opened : states),
    };
  }
  const windowTemp = ents?.fenster_temperatur ? num(hass.states[ents.fenster_temperatur]?.state) : null;
  const target = num(climate?.attributes?.temperature);
  const own = climate?.state === "heat" && windowTemp !== null && target === windowTemp;
  return { shown: own, open: own, names: [], icon: contactIcon(undefined, own), kind: "window" };
}

/** Points [{temperature, until}] → segments [{from, to, temperature}]. */
export function profileDay(points) {
  let from = "00:00";
  return (points || []).map((p) => {
    const to = p.until || "24:00";
    const seg = { from, to, temperature: Number(p.temperature) };
    from = to;
    return seg;
  });
}

/** Week (Monday first) from the attribute wochenprogramm; days it never acknowledged are unknown. */
export function weekRows(profile) {
  return WEEKDAYS.map((day) => {
    const points = profile?.[day];
    return { day, known: Array.isArray(points) && points.length > 0, segments: points?.length ? profileDay(points) : [] };
  });
}

/** Editor segments → profile for set_week_profile (last point without until), in the
 *  order shown; profileErrors says whether that order is valid. */
export function segmentsToProfile(segments) {
  return segments.map((s, i) => (i === segments.length - 1 ? { temperature: Number(s.temperature) } : { temperature: Number(s.temperature), until: s.to }));
}

/** What keeps a day's segments from being written: "order" (end times not rising),
 *  "grid" (not on 5 minutes). */
export function profileErrors(segments) {
  const errors = [];
  const ends = segments.map((s) => s.to);
  const mins = ends.map((x) => {
    const [hh, mm] = String(x).split(":").map(Number);
    return hh * 60 + mm;
  });
  if (mins.some((v, i) => i > 0 && v <= mins[i - 1])) errors.push("order");
  if (mins.some((v) => Number.isNaN(v) || v % 5 !== 0)) errors.push("grid");
  return errors;
}

/** Target a −/+ tap builds on: a sent, not yet acknowledged one counts, so taps add up. */
export function baseTarget(attrs) {
  const pending = num(attrs?.ausstehend);
  return pending !== null ? pending : num(attrs?.temperature);
}

/** Temperature for a point (dx, dy) relative to the ring centre (screen coordinates, y down).
 *  The arc starts at 135° (bottom left) and runs 270° clockwise; the gap below snaps to the
 *  nearer end. */
export function ringTemperature(dx, dy, range = MAX_RANGE) {
  const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
  let rel = (angle - 135 + 360) % 360;
  if (rel > 270) rel = rel > 315 ? 0 : 270;
  return snap(range.min + (rel / 270) * (range.max - range.min), range);
}

/** What a press at (dx, dy) from the ring's centre hits: "ring" (the 270° arc band, sets the
 * target), "centre" (history) or "none". The valve arc (r 64) and the gap at the bottom are no
 * ring: a press there set 30.5 °C (16.11.2026). */
export function ringHit(dx, dy) {
  const dist = Math.hypot(dx, dy);
  if (dist < RING_INNER) return "centre";
  if (dist > RING_OUTER) return "none";
  const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
  return (angle - 135 + 360) % 360 > 270 ? "none" : "ring";
}
// The arc has radius 80 (stroke 10, handle 9): the band reaches a little either side of it.
const RING_INNER = 70;
const RING_OUTER = 100;

export const CARD_TYPE = "custom:eq3-max-thermostat-card";

/** Grid columns (of 12) of a compact or ring card in its section. `siblings.half` says for
 * every card of the section whether it is such a card, `index` which one this is. Cards of
 * a run pair up side by side; one that is left alone (a single card, the last of three)
 * takes the whole width. Unknown surroundings: half, as before 0.1.5. */
export function sectionColumns(siblings) {
  if (!siblings || !siblings.half?.[siblings.index]) return 6;
  const { half, index } = siblings;
  let start = index;
  while (start > 0 && half[start - 1]) start -= 1;
  let end = index;
  while (end + 1 < half.length && half[end + 1]) end += 1;
  const count = end - start + 1;
  return count % 2 === 1 && index === end ? 12 : 6;
}

/** Hours and minutes of the day in 5-minute steps for the two lists of a time of day. A
 * minute off the grid (never from a MAX! program) is kept as it is. */
export function timeOptions(value) {
  const [hh, mm] = String(value || "00:00").split(":").map(Number);
  const two = (n) => String(n).padStart(2, "0");
  const minutes = Array.from({ length: 12 }, (_, i) => i * 5);
  if (!minutes.includes(mm)) minutes.push(mm);
  return { hour: two(hh), minute: two(mm), hours: Array.from({ length: 24 }, (_, i) => two(i)), minutes: minutes.sort((x, y) => x - y).map(two) };
}

/** Angle (degrees, 135..405) of a temperature on the ring, for the handle. */
export function ringAngle(temperature, range = MAX_RANGE) {
  const frac = (Math.min(range.max, Math.max(range.min, Number(temperature))) - range.min) / (range.max - range.min);
  return 135 + frac * 270;
}

/** The thermostat cannot be shown or operated (Home Assistant has no state for it). */
export function isUnavailable(climate) {
  return !climate || climate.state === "unavailable" || climate.state === "unknown";
}

/** Card picker suggestion (HA >= 2026.6): only for climate entities of eq3_max. */
export function entitySuggestion(hass, entityId) {
  if (!entityId || !entityId.startsWith("climate.")) return null;
  const ent = hass.entities && hass.entities[entityId];
  if (!ent || ent.platform !== "eq3_max") return null;
  return { config: { type: CARD_TYPE, entity: entityId, layout: "kompakt" } };
}

function slug(text) {
  // Like Home Assistant's slugify for the attribute keys rssi_<module>: ü → u, others → _.
  return String(text).normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

/** Name of the radio module behind an attribute key rssi_<slug>; the slug if unknown. */
export function moduleLabel(key, names) {
  const s = String(key).replace(/^rssi_/, "");
  return (names || []).find((name) => slug(name) === s) ?? s;
}

/** Numeric value of a number entity's state; null while unknown/unavailable. */
export function configNumber(stateObj) {
  return num(stateObj?.state);
}

/** Pop-up tabs; the wall thermostat has the display instead of the valve. */
export function tabsFor(isWall) {
  return [
    { id: "temp", icon: "mdi:thermometer", title: "Temperaturen" },
    { id: "window", icon: "mdi:window-open-variant", title: "Fenster" },
    { id: "boost", icon: "mdi:rocket-launch", title: isWall ? "Boost & Anzeige" : "Boost & Ventil" },
    { id: "week", icon: "mdi:calendar-clock", title: "Wochenprogramm" },
    { id: "info", icon: "mdi:information-outline", title: "Info" },
  ];
}

/** May the current user change settings ("config") or week programs ("week")? */
export function canEdit(hass, climate, kind) {
  if (hass?.user?.is_admin) return true;
  const attr = kind === "week" ? "wochenprogramm_frei" : "einstellungen_frei";
  return climate?.attributes?.[attr] !== false;
}

/** Keys of draft whose value differs from original. */
export function changedValues(original, draft) {
  const out = {};
  for (const [key, value] of Object.entries(draft || {})) {
    if (String(value) !== String(original?.[key])) out[key] = value;
  }
  return out;
}

/** Target ± one step within the range (MAX!: 0.5 within 4.5..30.5); an unknown target starts
 *  at 21, or in the middle of a range that does not hold 21 (°F). */
export function stepTarget(current, dir, range = MAX_RANGE) {
  const base = num(current);
  if (base === null) return range.min <= 21 && range.max >= 21 ? 21 : snap((range.min + range.max) / 2, range);
  return snap(base + dir * range.step, range);
}

// =============================================================================
// Ab hier nur im Browser.
// =============================================================================

const DAY_SHORT = { Montag: "Mo", Dienstag: "Di", Mittwoch: "Mi", Donnerstag: "Do", Freitag: "Fr", Samstag: "Sa", Sonntag: "So" };
const SELECT_DAYS = {
  saturday: "Samstag", sunday: "Sonntag", monday: "Montag", tuesday: "Dienstag", wednesday: "Mittwoch",
  thursday: "Donnerstag", friday: "Freitag",
};
const DISPLAY_OPTIONS = { setpoint: "Soll-Temperatur", actual: "Ist-Temperatur" };
const POLL_OPTIONS = { off: "aus", 15: "alle 15 min", 30: "alle 30 min", 60: "stündlich", 120: "alle 2 Stunden", 240: "alle 4 Stunden" };
const CONFIG_ROWS = {
  temp: [
    ["komfort", "Komforttemperatur"], ["eco", "Eco-Temperatur"], ["maximal", "Maximaltemperatur", "Grenze am Drehrad"],
    ["minimal", "Minimaltemperatur"], ["offset", "Temperatur-Offset", "Korrektur der Messung"],
    ["ist_abfragen", "Ist-Temperatur abfragen", "Kurzer Anstoß (Sollwert +0,5 °C bis zur Meldung) – kostet Batterie"],
  ],
  window: [["fenster_temperatur", "Fenster-auf-Temperatur"], ["fenster_dauer", "Fenster-auf-Dauer", "0 = Erkennung aus"]],
  boost: [
    ["boost_dauer", "Boost-Dauer"], ["boost_ventil", "Boost-Ventilstellung"], ["entkalkung_tag", "Entkalkung Tag"],
    ["entkalkung_stunde", "Entkalkung Stunde"], ["ventil_max", "Ventil maximal"], ["ventil_offset", "Ventil-Offset"],
    ["anzeige", "Anzeige"],
  ],
};
const CONFIG_HELP = {
  komfort: "Temperatur für die Komfort-Taste am Gerät und das Preset „Komfort“. Gilt für den ganzen Raum.",
  eco: "Absenktemperatur für die Eco-Taste, den Eco-Taster und das Preset „Eco“. Gilt für den ganzen Raum.",
  maximal: "Höchster Sollwert, der sich am Gerät einstellen lässt.",
  minimal: "Niedrigster Sollwert, der sich am Gerät einstellen lässt.",
  offset: "Korrigiert die gemessene Temperatur, z. B. −1 K, wenn das Thermostat direkt am Heizkörper zu warm misst.",
  fenster_temperatur: "Sollwert, solange ein Fenster offen ist – über einen Fensterkontakt oder die eigene Erkennung des Thermostats.",
  fenster_dauer: "So lange gilt die Fenster-auf-Temperatur, wenn das Thermostat selbst einen Temperatursturz erkennt. 0 = eigene Erkennung aus (ein Fensterkontakt wirkt weiter).",
  boost_dauer: "Wie lange Boost das Ventil weit öffnet. Der Wandthermostat zählt seine Anzeige danach herunter.",
  boost_ventil: "Ventilöffnung während Boost.",
  entkalkung_tag: "Wochentag der Ventilfahrt gegen Festsitzen (Entkalkung).",
  entkalkung_stunde: "Uhrzeit der wöchentlichen Ventilfahrt.",
  ventil_max: "Größte Ventilöffnung – begrenzt die Heizleistung dieses Heizkörpers.",
  ventil_offset: "Verschiebt die Ventilstellung, z. B. bei Ventilen, die erst spät öffnen.",
  anzeige: "Was das Display des Wandthermostats zeigt. Am Gerät ist das Menü gesperrt, solange es an einer Zentrale hängt.",
  ist_abfragen: "Der Heizkörper meldet seine Ist-Temperatur nur, wenn sich bei ihm etwas ändert. eq3_max stößt ihn in diesem Abstand an (Sollwert +0,5 °C bis zur Meldung, etwa 1 min, dann zurück). Kostet zwei Telegramme und etwas Batterie; ausgelassen, wenn er von selbst gemeldet hat.",
};
const RSSI_ICONS = { good: "mdi:signal-cellular-3", mid: "mdi:signal-cellular-2", weak: "mdi:signal-cellular-1", off: "mdi:signal-off" };

const STYLE = `
  :host {
    --e3-radius: var(--ha-card-border-radius, 14px);
    --e3-card: var(--ha-card-background, var(--card-background-color, #fff));
    --e3-divider: var(--divider-color, rgba(0, 0, 0, .12));
    --e3-muted: var(--secondary-text-color, #6b7380);
    --e3-text: var(--primary-text-color, #1c2430);
    --e3-ok: var(--success-color, #43a047);
    --e3-error: var(--error-color, #db4437);
    --e3-accent: var(--primary-color, #03a9f4);
    --e3-heat: var(--state-climate-heat-color, #ff8100);
    --e3-open: var(--warning-color, #ff9800);
    --e3-cool: var(--state-climate-cool-color, #2b9af9);
  }
  * { box-sizing: border-box; }
  ha-icon { --mdc-icon-size: 18px; display: inline-flex; }
  ha-card { position: relative; overflow: hidden; padding: 14px 16px 12px; display: flex; flex-direction: column; gap: 10px; height: 100%; color: var(--e3-text); }
  ha-card { --tone: var(--e3-accent); }
  ha-card.heat { --tone: var(--e3-heat); } ha-card.open { --tone: var(--e3-open); } ha-card.alert { --tone: var(--e3-error); }
  ha-card.off { --tone: var(--e3-muted); }
  ha-card.heat::before, ha-card.open::before, ha-card.alert::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--tone); }
  .ic { width: 38px; height: 38px; border-radius: 50%; flex: none; display: inline-flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--tone) 14%, transparent); color: var(--tone); }
  .ic ha-icon { --mdc-icon-size: 20px; }
  .head { display: flex; align-items: center; gap: 10px; }
  .who { flex: 1; min-width: 0; }
  .name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .kind { color: var(--e3-muted); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  button { font: inherit; color: inherit; }
  .gear { border: 0; background: none; color: var(--e3-muted); cursor: pointer; padding: 6px; border-radius: 50%; display: inline-flex; }
  .gear:hover { background: color-mix(in srgb, var(--e3-muted) 14%, transparent); }
  .gear ha-icon { --mdc-icon-size: 20px; }
  .temps { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .cur, .valve, .vcol { cursor: pointer; }
  .cur { font-size: 34px; letter-spacing: -.02em; line-height: 1; white-space: nowrap; }
  .cur small { font-size: 15px; color: var(--e3-muted); margin-left: 2px; }
  .curcol { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .hum { cursor: pointer; color: var(--e3-muted); font-size: 12.5px; display: inline-flex; align-items: center; gap: 3px; white-space: nowrap; }
  .hum ha-icon { --mdc-icon-size: 15px; }
  .hum.spare { visibility: hidden; cursor: default; }
  .subs { display: flex; flex-wrap: wrap; gap: 2px 10px; min-width: 0; }
  .tile .subs { flex-wrap: nowrap; overflow: hidden; margin-top: -4px; }
  .stepper { flex: none; display: inline-flex; align-items: center; gap: 2px; border-radius: 999px; padding: 3px; background: color-mix(in srgb, var(--tone) 12%, transparent); }
  .stepper button { width: 32px; height: 32px; border-radius: 50%; border: 0; background: var(--e3-card); cursor: pointer; font-size: 18px; box-shadow: 0 1px 2px rgba(0, 0, 0, .15); }
  .stepper button:disabled { opacity: .4; cursor: default; }
  .stepper .v { min-width: 60px; text-align: center; font-weight: 600; font-size: 15px; display: inline-flex; align-items: center; justify-content: center; gap: 3px; }
  .stepper .v ha-icon { --mdc-icon-size: 15px; color: var(--tone); }
  .modes { display: flex; gap: 6px; flex-wrap: wrap; }
  .mode { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--e3-divider); border-radius: 999px; padding: 4px 10px; font-size: 12.5px; cursor: pointer; background: transparent; }
  .mode ha-icon { --mdc-icon-size: 15px; }
  .mode.on { background: var(--tone); color: var(--text-primary-color, #fff); border-color: var(--tone); }
  .mode.icon { padding: 5px 8px; }
  /* Narrow cards (sections dashboard, phone): modes as symbols in one row. */
  ha-card { container-type: inline-size; }
  @container (max-width: 340px) {
    .mode .lbl { display: none; }
    .mode { padding: 5px 8px; flex: 1; justify-content: center; }
    .modes { flex-wrap: nowrap; }
  }
  .valve { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--e3-muted); }
  .meter { flex: 1; height: 6px; border-radius: 3px; background: var(--e3-divider); overflow: hidden; }
  .meter > span { display: block; height: 100%; border-radius: 3px; background: var(--tone); transition: width .3s; }
  .foot { display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: center; color: var(--e3-muted); font-size: 12px; border-top: 1px solid var(--e3-divider); padding-top: 9px; margin-top: auto; }
  .foot > span { display: inline-flex; align-items: center; gap: 3px; }
  .foot ha-icon { --mdc-icon-size: 17px; }
  .foot .age { margin-left: auto; }
  .warn { color: var(--e3-open); } .bad { color: var(--e3-error); }
  .chip { display: inline-flex; align-items: center; gap: 4px; border-radius: 999px; padding: 2px 9px; font-size: 12px; font-weight: 500;
    background: color-mix(in srgb, var(--e3-open) 16%, transparent); color: var(--e3-open); }
  .chip ha-icon { --mdc-icon-size: 14px; }
  .syms { display: flex; justify-content: center; gap: 6px; flex-wrap: wrap; }
  .sym { display: inline-flex; align-items: center; justify-content: center; gap: 4px; height: 28px; min-width: 28px; padding: 0 8px; border-radius: 999px;
    background: color-mix(in srgb, var(--e3-divider) 50%, transparent); font-size: 12px; color: var(--e3-muted); }
  .sym ha-icon { --mdc-icon-size: 16px; }
  .sym.warn { background: color-mix(in srgb, var(--e3-open) 16%, transparent); color: var(--e3-open); }
  .sym.bad { background: color-mix(in srgb, var(--e3-error) 14%, transparent); color: var(--e3-error); }
  /* Ring */
  /* Shrinks with a narrow card (three sections side by side on a laptop: about 155 px); its
     texts follow in cqw, units of the ring's own width. */
  .ring { position: relative; width: min(230px, 100%); aspect-ratio: 1; margin: 0 auto; container-type: inline-size; }
  .ring svg { position: absolute; inset: 0; touch-action: none; cursor: pointer; }
  .ring .c .hit { pointer-events: auto; cursor: pointer; }
  .ring .c { pointer-events: none; position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; }
  .ring .big { font-size: min(50px, calc(27cqw - 11px)); font-weight: 500; letter-spacing: -.02em; line-height: 1.15; }
  .ring .sub { font-size: clamp(9.5px, 6.9cqw, 15px); color: var(--e3-muted); display: inline-flex; gap: 3px; align-items: center; white-space: nowrap; }
  .ring .sub ha-icon { --mdc-icon-size: 14px; }
  .ringbtns { display: flex; justify-content: center; gap: 44px; margin-top: -10px; }
  /* Very narrow: the modes wrap instead of running out of the card, the name gets the icon's room. */
  @container (max-width: 230px) {
    .modes { flex-wrap: wrap; justify-content: center; }
    .mode { flex: none; }
    .head { gap: 6px; }
    .head .ic { display: none; }
    .name { white-space: normal; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-height: 1.2; overflow-wrap: anywhere; }
    .temps { flex-wrap: wrap; }
    .ringbtns { gap: 24px; margin-top: -4px; }
  }
  .round { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--e3-divider); background: var(--e3-card); font-size: 20px; cursor: pointer; }
  .center { justify-content: center; }
  /* Kachel */
  ha-card.tile { flex-direction: row; align-items: stretch; gap: 14px; }
  .tile .left { display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 0; }
  .tile .right { display: grid; grid-template-columns: repeat(2, 28px); gap: 6px; align-content: center; }
  .tile .right .sym { padding: 0; }
  .vcol { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 11.5px; color: var(--e3-muted); }
  .vbar { width: 10px; flex: 1; min-height: 60px; border-radius: 5px; background: var(--e3-divider); position: relative; overflow: hidden; }
  .vbar > span { position: absolute; left: 0; right: 0; bottom: 0; background: var(--tone); border-radius: 5px; }
  .vcol ha-icon { --mdc-icon-size: 15px; }
  .err { padding: 16px; color: var(--e3-error); }
  .unavail { display: flex; align-items: center; gap: 8px; color: var(--e3-muted); font-size: 15px; padding: 6px 0 4px; }
`;

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "style" && typeof value === "object") Object.assign(el.style, value);
    else if (key in el && typeof value !== "string") el[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

const icon = (name) => h("ha-icon", { icon: name });
/** A time of day as two lists (hours, minutes in 5-minute steps): always 24 hours. A time
 * input shows AM/PM whenever the browser's language says so, whatever the profile wants. */
function timeSelect(value, onchange) {
  const o = timeOptions(value);
  const list = (items, current) => {
    const el = h("select", { class: "tsel" }, items.map((x) => h("option", { value: x }, x)));
    el.value = current;
    return el;
  };
  const hours = list(o.hours, o.hour);
  const minutes = list(o.minutes, o.minute);
  const changed = () => onchange(`${hours.value}:${minutes.value}`);
  hours.addEventListener("change", changed);
  minutes.addEventListener("change", changed);
  return h("span", { class: "time" }, hours, ":", minutes);
}
// Numbers as the user's profile wants them (set with every hass), not as the browser does.
let NUMBER_LOCALE;
function fmt(value, digits = 1) {
  if (value === null || value === undefined) return "–";
  const options = { minimumFractionDigits: digits, maximumFractionDigits: digits };
  try {
    return Number(value).toLocaleString(NUMBER_LOCALE, options);
  } catch {
    return Number(value).toLocaleString(undefined, options); // a language tag the browser does not know
  }
}

/** Attributes of a clickable element that is no button: reachable and usable by keyboard. */
const press = (fn) => ({
  role: "button", tabindex: "0", onclick: fn,
  onkeydown: (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); fn(); } },
});

function ageText(lang, iso) {
  if (!iso) return null;
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (Number.isNaN(minutes)) return null;
  if (minutes < 1) return t(lang, "gerade eben");
  if (minutes < 120) return t(lang, "vor {n} min", { n: minutes });
  return t(lang, "vor {n} h", { n: Math.round(minutes / 60) });
}

/** Numeric state of an optional external sensor; null when not set or unavailable. */
export function sensorValue(hass, entityId) {
  if (!entityId) return null;
  const s = hass.states[entityId];
  if (!s || isUnavailable(s)) return null;
  return num(s.state);
}

/** Current temperature: an external sensor replaces the thermostat's own reading (falls back
 * when unavailable); the thermostat's reading stays known so the card can show both. */
export function currentReading(hass, config) {
  const own = num(hass.states[config.entity]?.attributes?.current_temperature);
  const ext = sensorValue(hass, config.temperature_sensor);
  return ext !== null
    ? { current: ext, currentEntity: config.temperature_sensor, own, external: true }
    : { current: own, currentEntity: config.entity, own, external: false };
}

/** Everything the card shows, from states and attributes. */
function readModel(hass, config) {
  const climate = hass.states[config.entity];
  if (!climate) return null;
  const ents = findEntities(hass, config.entity);
  const st = (key) => (ents[key] ? hass.states[ents[key]] : undefined);
  const attrs = climate.attributes || {};
  const isWall = !("valve" in attrs) && !ents.ventil;
  const valve = num(st("ventil")?.state ?? attrs.valve);
  const rssi = num(st("rssi")?.state);
  const rf = st("funkfehler")?.state === "on";
  const entry = hass.entities?.[config.entity];
  const device = entry?.device_id ? hass.devices?.[entry.device_id] : undefined;
  const areaId = entry?.area_id || device?.area_id;
  const linkState = st("verknuepfungen");
  return {
    climate, attrs, ents, isWall, valve, rssi, rf,
    range: tempRange(hass, climate),
    deviceId: entry?.device_id,
    name: config.name || device?.name_by_user || device?.name || attrs.friendly_name || config.entity,
    area: areaId ? hass.areas?.[areaId]?.name : undefined,
    ...currentReading(hass, config),
    humidity: sensorValue(hass, config.humidity_sensor),
    target: num(attrs.temperature),
    hvac: climate.state,
    preset: attrs.preset_mode || "none",
    until: attrs.bis,
    pending: attrs.ausstehend !== null && attrs.ausstehend !== undefined || !!attrs.ausstehend_modus,
    hasBattery: !!ents.lowbat,
    lowBattery: st("lowbat")?.state === "on",
    locked: st("gesperrt")?.state === "on",
    lastSeen: st("zuletzt_gemeldet")?.state,
    links: linkState?.attributes?.partner || [],
    window: windowState(hass, climate, ents),
    level: rssiLevel(rssi, rf),
  };
}

function toneOf(m) {
  if (m.lowBattery || m.rf) return "alert";
  if (m.window.open) return "open";
  if (m.hvac === "off") return "off";
  if ((m.valve ?? 0) > 0 || m.preset === "boost") return "heat";
  return "idle";
}

/** Status symbols (window, battery, radio, links, lock, pending). */
function symbols(lang, m) {
  const out = [];
  if (m.window.shown) {
    const door = m.window.kind === "door";
    out.push({ icon: m.window.icon, cls: m.window.open ? "warn" : "",
      title: t(lang, m.window.open ? (door ? "Tür offen" : "Fenster offen") : door ? "Tür geschlossen" : "Fenster geschlossen")
        + (m.window.names.length ? ` (${m.window.names.join(", ")})` : ""),
      text: m.window.open ? t(lang, "offen") : "" });
  }
  if (m.hasBattery) {
    out.push(m.lowBattery
      ? { icon: "mdi:battery-alert-variant-outline", cls: "bad", title: t(lang, "Batterie schwach") }
      : { icon: "mdi:battery", cls: "", title: t(lang, "Batterie ok") });
  }
  if (m.level) {
    out.push({ icon: RSSI_ICONS[m.level], cls: m.level === "off" ? "bad" : m.level === "weak" ? "warn" : "",
      title: m.level === "off" ? t(lang, "Funkfehler") : t(lang, "Funk {dbm} dBm", { dbm: fmt(m.rssi, 0) }) });
  }
  if (m.links.length) out.push({ icon: "mdi:link-variant", cls: "", title: t(lang, "verknüpft mit {names}", { names: m.links.join(", ") }) });
  if (m.locked) out.push({ icon: "mdi:lock", cls: "", title: t(lang, "Bediensperre") });
  if (m.pending) out.push({ icon: "mdi:timer-sand", cls: "warn", title: t(lang, "Befehl ausstehend") });
  return out;
}

const MODES = [
  { id: "manual", icon: "mdi:hand-back-right", label: "Manuell" },
  { id: "auto", icon: "mdi:calendar-clock", label: "Auto" },
  { id: "comfort", icon: "mdi:sun-thermometer", label: "Komfort" },
  { id: "eco", icon: "mdi:leaf", label: "Eco" },
  { id: "boost", icon: "mdi:rocket-launch", label: "Boost" },
  { id: "off", icon: "mdi:power", label: "Aus" },
];

function activeMode(m) {
  if (m.hvac === "off") return "off";
  if (m.hvac === "auto" && m.preset !== "boost" && m.preset !== "away") return "auto";
  if (["boost", "comfort", "eco"].includes(m.preset)) return m.preset;
  if (m.preset === "away") return "away";
  return "manual";
}

async function setMode(hass, entity, mode) {
  if (mode === "auto" || mode === "off" || mode === "manual") {
    await hass.callService("climate", "set_hvac_mode", { entity_id: entity, hvac_mode: mode === "manual" ? "heat" : mode });
  } else {
    await hass.callService("climate", "set_preset_mode", { entity_id: entity, preset_mode: mode });
  }
}

/** Ring arc (270°) as stroke-dasharray for a circle of radius r. */
function arc(r, fraction) {
  const full = 2 * Math.PI * r;
  const len = full * 0.75 * Math.max(0, Math.min(1, fraction));
  return `${len} ${full}`;
}

// Each block only once: a resource entered twice loads this file twice, and a second
// customElements.define throws.
if (typeof HTMLElement !== "undefined" && typeof customElements !== "undefined" && !customElements.get("eq3-max-thermostat-card")) {
  class Eq3MaxThermostatCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._sig = "";
      this._busy = false;
    }

    static getConfigElement() {
      return document.createElement("eq3-max-thermostat-card-editor");
    }

    static getStubConfig(hass) {
      const first = Object.values(hass.entities || {}).find((e) => e.platform === "eq3_max" && e.entity_id.startsWith("climate."));
      return { entity: first ? first.entity_id : "", layout: "kompakt" };
    }

    setConfig(config) {
      if (!config || !config.entity) throw new Error("entity required (climate.* of eq3_max)");
      const layout = config.layout || "kompakt";
      if (!["kompakt", "ring", "kachel"].includes(layout)) throw new Error(`layout must be kompakt, ring or kachel, got ${layout}`);
      this._config = { show_modes: true, ...config, layout };
      this._sig = "";
      if (this._hass) this._render();
    }

    set hass(hass) {
      this._hass = hass;
      NUMBER_LOCALE = numberLocale(hass.locale);
      const ents = findEntities(hass, this._config?.entity);
      const ids = [this._config?.entity, ...Object.values(ents), ...(hass.states[this._config?.entity]?.attributes?.fenster || []),
        this._config?.temperature_sensor, this._config?.humidity_sensor];
      const sig = ids.map((id) => {
        const s = hass.states[id];
        return s ? `${s.state}|${s.last_updated}` : "";
      }).join(";") + hass.locale?.language;
      if (sig !== this._sig && !this._drag) {
        this._sig = sig;
        this._render();
      }
      if (this._dialog) this._dialog.hass = hass;
    }

    getCardSize() {
      return { kompakt: 4, ring: 6, kachel: 3 }[this._config?.layout] || 4;
    }

    getGridOptions() {
      const layout = this._config?.layout;
      if (layout === "kachel") return { columns: 12, rows: "auto", min_columns: 9 };
      if (layout !== "kompakt" && layout !== "ring") return { columns: 6, rows: 4 };
      // Height follows the content (modes wrap, wall thermostats have no valve row). Width:
      // half the section next to another thermostat, all of it when alone (0.1.5). The
      // section asks again with every state change; grid_options in the card's
      // configuration still win.
      return { columns: sectionColumns(this._siblings()), rows: "auto", min_columns: 6 };
    }

    /** Where this card stands among the cards of its section: {types, index}, or null
     * outside a sections view (or before the card is in the page). */
    _siblings() {
      const card = this.parentElement; // hui-card
      const cards = card?.getRootNode?.()?.host?._config?.cards;
      if (!Array.isArray(cards)) return null;
      let index = cards.indexOf(card.config);
      if (index < 0) index = cards.findIndex((c) => c?.type === CARD_TYPE && c.entity === this._config?.entity);
      if (index < 0) return null;
      return { index, half: cards.map((c) => c?.type === CARD_TYPE && c.layout !== "kachel" && !c.grid_options?.columns) };
    }

    get _lang() {
      return this._hass?.locale?.language || this._hass?.language || "en";
    }

    async _call(fn) {
      try {
        await fn();
      } catch (err) {
        this._toast(err?.message || String(err));
      }
    }

    _moreInfo(entityId) {
      // Home Assistant's own dialog with history graph.
      if (!entityId) return;
      this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
    }

    _toast(message) {
      this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
    }

    disconnectedCallback() {
      // The view changed: the pop-up belongs to this card and goes with it.
      this._dialog?.close();
      // A drag cut off here would keep the card from drawing new states for good.
      this._drag = false;
      clearTimeout(this._localTimer);
      this._local = undefined;
    }

    _openDialog() {
      if (!this._dialog) {
        this._dialog = document.createElement("eq3-max-thermostat-dialog");
        this._dialog.addEventListener("closed", () => {
          this._dialog?.remove();
          this._dialog = null;
        });
        document.body.append(this._dialog);
      }
      this._dialog.setup(this._config, this._hass);
    }

    _render() {
      const root = this.shadowRoot;
      const hass = this._hass;
      if (!hass || !this._config) return;
      const lang = this._lang;
      const m = readModel(hass, this._config);
      root.replaceChildren(h("style", {}, STYLE));
      if (!m) {
        root.append(h("ha-card", {}, h("div", { class: "err" }, t(lang, "Entität {entity} nicht gefunden.", { entity: this._config.entity }))));
        return;
      }
      const entry = hass.entities?.[this._config.entity];
      if (entry && entry.platform !== "eq3_max") {
        root.append(h("ha-card", {}, h("div", { class: "err" }, t(lang, "Entität {entity} gehört nicht zur Integration eq3_max.", { entity: this._config.entity }))));
        return;
      }
      if (isUnavailable(m.climate)) {
        const card = h("ha-card", { class: "off" },
          this._head(lang, m, this._kindText(lang, m)),
          h("div", { class: "unavail" }, icon("mdi:lan-disconnect"), t(lang, "nicht verfügbar")));
        card.querySelector(".gear")?.remove();
        root.append(card);
        return;
      }
      const layout = this._config.layout;
      const card = layout === "ring" ? this._ring(lang, m) : layout === "kachel" ? this._tile(lang, m) : this._compact(lang, m);
      card.classList.add(toneOf(m));
      root.append(card);
    }

    _head(lang, m, kind) {
      return h("div", { class: "head" },
        h("span", { class: "ic" }, icon(thermostatIcon(m.climate, m.isWall))),
        h("div", { class: "who" },
          h("div", { class: "name", title: m.name }, m.name),
          h("div", { class: "kind" }, kind)),
        h("button", { class: "gear", title: t(lang, "Einstellungen"), onclick: () => this._openDialog() }, icon("mdi:cog")));
    }

    _kindText(lang, m) {
      const type = t(lang, m.isWall ? "Wandthermostat" : "Heizkörperthermostat");
      return m.area ? `${type} · ${m.area}` : type;
    }

    _stateText(lang, m) {
      const mode = activeMode(m);
      if (mode === "away") return t(lang, "Abwesend");
      if (m.window.open) return t(lang, m.window.kind === "door" ? "Tür offen" : "Fenster offen");
      return t(lang, MODES.find((x) => x.id === mode)?.label || "Manuell");
    }

    _stepper(m, withIcon = true) {
      const step = (dir) => this._step(dir);
      const off = m.hvac === "off";
      const shown = baseTarget(m.attrs);
      return h("div", { class: "stepper" },
        h("button", { onclick: () => step(-1), disabled: off || (shown !== null && shown <= m.range.min) }, "−"),
        h("span", { class: "v" }, withIcon ? icon("mdi:target") : null, `${fmt(shown)}°`),
        h("button", { onclick: () => step(+1), disabled: off || (shown !== null && shown >= m.range.max) }, "+"));
    }

    _step(dir) {
      // From the latest state (a pending target counts), not from the rendered one.
      const climate = this._hass.states[this._config.entity];
      const target = stepTarget(this._local ?? baseTarget(climate?.attributes), dir, tempRange(this._hass, climate));
      this._local = target;
      clearTimeout(this._localTimer);
      this._localTimer = setTimeout(() => { this._local = undefined; }, 3000);
      this._call(() => this._hass.callService("climate", "set_temperature", { entity_id: this._config.entity, temperature: target }));
    }

    _modes(lang, m, iconsOnly = false) {
      if (!this._config.show_modes) return null;
      const active = activeMode(m);
      return h("div", { class: `modes${iconsOnly ? "" : ""}` }, MODES.map((mode) =>
        h("button", {
          class: `mode${active === mode.id ? " on" : ""}${iconsOnly ? " icon" : ""}`,
          title: t(lang, mode.label),
          onclick: () => this._call(() => setMode(this._hass, this._config.entity, mode.id)),
        }, icon(mode.icon), iconsOnly ? null : h("span", { class: "lbl" }, t(lang, mode.label)))));
    }

    _away(lang, m) {
      if (activeMode(m) !== "away") return null;
      const time = m.until ? new Date(m.until).toLocaleString(lang, { weekday: "short", hour: "2-digit", minute: "2-digit" }) : "?";
      return h("div", {}, h("span", { class: "chip" }, icon("mdi:airplane"), t(lang, "Abwesend bis {time}", { time })));
    }

    _compact(lang, m) {
      return h("ha-card", {},
        this._head(lang, m, this._kindText(lang, m)),
        h("div", { class: "temps" },
          this._current(lang, m),
          this._stepper(m)),
        this._away(lang, m),
        this._modes(lang, m),
        m.isWall ? null : h("div", { class: "valve", title: t(lang, "Verlauf"), ...press(() => this._moreInfo(m.ents.ventil)) }, icon("mdi:valve"), t(lang, "Ventil"),
          h("div", { class: "meter" }, h("span", { style: { width: `${m.valve ?? 0}%` } })), `${m.valve ?? "–"} %`),
        this._foot(lang, m));
    }

    _current(lang, m) {
      const { cur, subs } = this._currentParts(lang, m);
      return h("div", { class: "curcol" }, cur, subs);
    }

    /** The value and the line below it (humidity, the thermostat's own reading). */
    _currentParts(lang, m) {
      const cur = h("div", { class: "cur", title: t(lang, "Verlauf"), ...press(() => this._moreInfo(m.currentEntity)) }, fmt(m.current), h("small", {}, m.range.unit));
      const own = m.external && m.own !== null
        ? h("div", { class: "hum", title: t(lang, "Messwert am Thermostat (am Heizkörper)"), ...press(() => this._moreInfo(this._config.entity)) },
          icon("mdi:thermostat"), t(lang, "Thermostat {value} {unit}", { value: fmt(m.own), unit: m.range.unit }))
        : null;
      const hum = m.humidity === null
        ? null
        : h("div", { class: "hum", title: t(lang, "Luftfeuchte"), ...press(() => this._moreInfo(this._config.humidity_sensor)) },
          icon("mdi:water-percent"), `${fmt(m.humidity, 0)} %`);
      // Always exactly one line below the value (humidity and the thermostat's own reading
      // side by side), so cards next to each other have the same height whether or not an
      // external sensor or a humidity sensor is set.
      const spare = own || hum ? null : h("div", { class: "hum spare", "aria-hidden": "true" }, icon("mdi:thermostat"), "\u00a0");
      return { cur, subs: h("div", { class: "subs" }, hum, own, spare) };
    }

    _foot(lang, m) {
      const syms = symbols(lang, m);
      const age = ageText(lang, m.lastSeen);
      if (!syms.length && !age) return null;
      return h("div", { class: "foot" },
        syms.map((s) => h("span", { class: s.cls, title: s.title }, icon(s.icon), s.text || null)),
        h("span", { class: "age" }, age));
    }

    _ring(lang, m) {
      const ringTarget = baseTarget(m.attrs);
      const range = m.range;
      const span = range.max - range.min;
      const frac = ringTarget === null ? 0 : (ringTarget - range.min) / span;
      const ns = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", "0 0 190 190");
      const circle = (r, width, color, dash) => {
        const c = document.createElementNS(ns, "circle");
        for (const [k, v] of Object.entries({ cx: 95, cy: 95, r, fill: "none", stroke: color, "stroke-width": width,
          "stroke-dasharray": dash, transform: "rotate(135 95 95)", "stroke-linecap": "round" })) c.setAttribute(k, v);
        svg.append(c);
      };
      circle(80, 12, "var(--e3-divider)", arc(80, 1));
      // Always drawn (empty when off): the drag code addresses it as the second circle.
      circle(80, 12, "var(--tone)", arc(80, m.hvac === "off" ? 0 : frac));
      if (!m.isWall) {
        circle(64, 5, "var(--e3-divider)", arc(64, 1));
        if ((m.valve ?? 0) > 0) circle(64, 5, "color-mix(in srgb, var(--tone) 60%, transparent)", arc(64, (m.valve ?? 0) / 100));
      }
      // Drag along the ring (or tap it) to set the target; sent when let go.
      const shown = baseTarget(m.attrs);
      const handle = document.createElementNS(ns, "circle");
      const placeHandle = (temperature) => {
        const rad = (ringAngle(temperature ?? range.min, range) * Math.PI) / 180;
        for (const [k, v] of Object.entries({ cx: 95 + 80 * Math.cos(rad), cy: 95 + 80 * Math.sin(rad), r: 9,
          fill: "var(--e3-card)", stroke: "var(--tone)", "stroke-width": 4 })) handle.setAttribute(k, v);
      };
      placeHandle(m.hvac === "off" ? range.min : shown);
      svg.append(handle);
      const valueArc = svg.querySelectorAll("circle")[1];
      const pick = (ev) => {
        const rect = svg.getBoundingClientRect();
        const scale = 190 / rect.width;
        return { dx: (ev.clientX - rect.left) * scale - 95, dy: (ev.clientY - rect.top) * scale - 95 };
      };
      const show = (temperature) => {
        this._dragValue = temperature;
        placeHandle(temperature);
        if (valueArc) valueArc.setAttribute("stroke-dasharray", arc(80, (temperature - range.min) / span));
        const big = this.shadowRoot.querySelector(".ring .big");
        if (big) big.textContent = `${fmt(temperature)}°`;
      };
      svg.addEventListener("pointerdown", (ev) => {
        const { dx, dy } = pick(ev);
        const hit = ringHit(dx, dy);
        if (hit === "centre") { this._moreInfo(m.currentEntity); return; } // centre: history
        // Only the arc itself sets the target, and not while off (as with − and +).
        if (hit !== "ring" || m.hvac === "off") return;
        ev.preventDefault();
        svg.setPointerCapture(ev.pointerId);
        this._drag = true;
        show(ringTemperature(dx, dy, range));
      });
      svg.addEventListener("pointermove", (ev) => {
        if (!this._drag) return;
        const { dx, dy } = pick(ev);
        show(ringTemperature(dx, dy, range));
      });
      const drop = () => {
        if (!this._drag) return;
        this._drag = false;
        const target = this._dragValue;
        this._sig = ""; // states that came in meanwhile are drawn now
        if (target !== undefined && target !== shown) {
          this._call(() => this._hass.callService("climate", "set_temperature", { entity_id: this._config.entity, temperature: target }));
        } else {
          this._render();
        }
      };
      svg.addEventListener("pointerup", drop);
      svg.addEventListener("pointercancel", drop);
      const step = (dir) => this._step(dir);
      return h("ha-card", {},
        this._head(lang, m, this._stateText(lang, m)),
        h("div", { class: "ring" }, svg,
          h("div", { class: "c" },
            h("div", { class: "big" }, m.hvac === "off" ? t(lang, "Aus") : `${fmt(baseTarget(m.attrs))}°`),
            h("div", {
              class: "sub hit",
              title: m.external && m.own !== null ? t(lang, "Thermostat {value} {unit}", { value: fmt(m.own), unit: range.unit }) : t(lang, "Verlauf"),
              ...press(() => this._moreInfo(m.currentEntity)),
            }, t(lang, "Ist {value} {unit}", { value: fmt(m.current), unit: range.unit })),
            m.humidity === null ? null : h("div", {
              class: "sub hit", title: t(lang, "Luftfeuchte"), ...press(() => this._moreInfo(this._config.humidity_sensor)),
            }, icon("mdi:water-percent"), `${fmt(m.humidity, 0)} %`),
            m.isWall ? null : h("div", {
              class: "sub hit", title: t(lang, "Ventil"), ...press(() => this._moreInfo(m.ents.ventil)),
            }, icon("mdi:valve"), `${m.valve ?? "–"} %`))),
        h("div", { class: "ringbtns" },
          h("button", { class: "round", onclick: () => step(-1), disabled: m.hvac === "off" }, "−"),
          h("button", { class: "round", onclick: () => step(+1), disabled: m.hvac === "off" }, "+")),
        this._away(lang, m),
        h("div", { class: "syms" }, symbols(lang, m).map((s) =>
          h("span", { class: `sym ${s.cls}`, title: s.title }, icon(s.icon), s.text || null))),
        this._centered(this._modes(lang, m)));
    }

    _centered(el) {
      el?.classList.add("center");
      return el;
    }

    _tile(lang, m) {
      const parts = this._currentParts(lang, m);
      return h("ha-card", { class: "tile" },
        h("div", { class: "left" },
          this._head(lang, m, this._stateText(lang, m)),
          // The line below the value gets the full width: next to the stepper it ran into
          // it on a phone (humidity plus the thermostat's own reading).
          h("div", { class: "temps" }, parts.cur, this._stepper(m, false)),
          parts.subs,
          this._away(lang, m),
          this._modes(lang, m, true)),
        h("div", { class: "right" }, symbols(lang, m).slice(0, 6).map((s) =>
          h("span", { class: `sym ${s.cls}`, title: s.title }, icon(s.icon)))),
        m.isWall ? null : h("div", { class: "vcol", title: t(lang, "Ventil"), ...press(() => this._moreInfo(m.ents.ventil)) },
          h("div", { class: "vbar" }, h("span", { style: { height: `${m.valve ?? 0}%` } })),
          icon("mdi:valve"), `${m.valve ?? "–"} %`));
    }
  }

  customElements.define("eq3-max-thermostat-card", Eq3MaxThermostatCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "eq3-max-thermostat-card",
    name: "eQ-3 MAX! Thermostat",
    description: "Thermostat with valve, battery, radio and window – settings and week program in a pop-up (eq3_max).",
    preview: true,
    documentationURL: "https://ma-schmitz.github.io/eq3_max/handbuch/karte/",
    // Card picker suggestion (HA >= 2026.6): only for climate entities of eq3_max
    getEntitySuggestion: entitySuggestion,
  });
  console.info(`%c eq3-max-thermostat-card %c ${VERSION} `, "background:#ff8100;color:#fff", "background:#444;color:#fff");
}

const DIALOG_STYLE = `
  :host { position: fixed; inset: 0; z-index: 9999; display: flex; align-items: center; justify-content: center;
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); color: var(--primary-text-color, #1c2430);
    --e3-card: var(--card-background-color, #fff); --e3-divider: var(--divider-color, rgba(0, 0, 0, .12));
    --e3-muted: var(--secondary-text-color, #6b7380); --e3-accent: var(--primary-color, #03a9f4);
    --e3-heat: var(--state-climate-heat-color, #ff8100); --e3-open: var(--warning-color, #ff9800);
    --e3-error: var(--error-color, #db4437); --e3-ok: var(--success-color, #43a047); }
  * { box-sizing: border-box; }
  button, select, input { font: inherit; color: inherit; }
  ha-icon { --mdc-icon-size: 18px; display: inline-flex; }
  .backdrop { position: absolute; inset: 0; background: rgba(20, 24, 30, .45); }
  .dlg { position: relative; background: var(--e3-card); border-radius: 22px; width: min(540px, calc(100vw - 32px));
    max-height: min(86vh, 760px); display: flex; flex-direction: column; box-shadow: 0 12px 40px rgba(0, 0, 0, .3); overflow: hidden; }
  @media (max-width: 600px) {
    :host { align-items: flex-end; }
    .dlg { width: 100vw; border-radius: 22px 22px 0 0; max-height: 92vh; }
  }
  .grab { width: 40px; height: 4px; border-radius: 2px; background: var(--e3-divider); margin: 8px auto 0; display: none; }
  @media (max-width: 600px) { .grab { display: block; } }
  .dh { display: flex; align-items: center; gap: 10px; padding: 14px 18px 6px; }
  .ic { width: 38px; height: 38px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--e3-heat) 14%, transparent); color: var(--e3-heat); }
  .dh .t { flex: 1; min-width: 0; } .n { font-weight: 600; font-size: 17px; } .k { color: var(--e3-muted); font-size: 12.5px; }
  .x { border: 0; background: none; color: var(--e3-muted); cursor: pointer; padding: 6px; border-radius: 50%; display: inline-flex; }
  .x ha-icon { --mdc-icon-size: 22px; }
  .tabs { display: flex; gap: 2px; padding: 4px 12px 0; border-bottom: 1px solid var(--e3-divider); overflow-x: auto; flex: none; }
  .tab { border: 0; background: none; padding: 9px 10px; font-size: 13.5px; color: var(--e3-muted); border-bottom: 2px solid transparent;
    white-space: nowrap; display: inline-flex; gap: 5px; align-items: center; cursor: pointer; }
  .tab.on { color: var(--e3-accent); border-color: var(--e3-accent); font-weight: 500; }
  .tab span { display: none; } .tab.on span { display: inline; }
  .tabs { scrollbar-width: none; } .tabs::-webkit-scrollbar { display: none; }
  .body { padding: 12px 18px; overflow-y: auto; flex: 1; }
  .row { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid color-mix(in srgb, var(--e3-divider) 50%, transparent); flex-wrap: wrap; }
  .row:last-child { border-bottom: 0; }
  .row .l { flex: 1; font-size: 14px; min-width: 140px; } .row .l small { display: block; color: var(--e3-muted); font-size: 11.5px; }
  .info { border: 0; background: none; color: var(--e3-muted); cursor: pointer; padding: 0 2px; vertical-align: middle; display: inline-flex; }
  .info ha-icon { --mdc-icon-size: 15px; }
  .help { font-size: 12.5px; color: var(--e3-muted); background: color-mix(in srgb, var(--e3-accent) 8%, transparent); border-radius: 8px; padding: 6px 10px; margin-top: 4px; }
  .chip { display: inline-block; border-radius: 999px; padding: 1px 8px; font-size: 11px; font-weight: 500; margin-left: 4px; vertical-align: middle; }
  .chip.room { background: color-mix(in srgb, var(--e3-accent) 12%, transparent); color: var(--e3-accent); }
  .chip.warn { background: color-mix(in srgb, var(--e3-open) 16%, transparent); color: var(--e3-open); }
  .st { display: inline-flex; align-items: center; border: 1px solid var(--e3-divider); border-radius: 999px; }
  .st button { border: 0; background: none; width: 32px; height: 32px; font-size: 17px; cursor: pointer; border-radius: 50%; }
  .st button:disabled { opacity: .35; cursor: default; }
  .st span { min-width: 72px; text-align: center; font-weight: 500; font-size: 14px; }
  .st.changed, select.changed, input.changed { border-color: var(--e3-accent); background: color-mix(in srgb, var(--e3-accent) 8%, transparent); }
  select, input[type=time] { border: 1px solid var(--e3-divider); border-radius: 999px; padding: 6px 12px; font-size: 14px; background: var(--e3-card); }
  .val { font-weight: 500; }
  .foot { display: flex; align-items: center; gap: 8px; padding: 12px 18px 16px; border-top: 1px solid var(--e3-divider); flex: none; flex-wrap: wrap; }
  .foot .info { flex: 1; font-size: 12.5px; color: var(--e3-muted); min-width: 120px; }
  .btn { border: 1px solid var(--e3-accent); color: var(--e3-accent); background: transparent; border-radius: 999px; padding: 7px 16px; font-size: 14px; font-weight: 500; cursor: pointer; }
  .btn.p { background: var(--e3-accent); color: var(--text-primary-color, #fff); }
  .btn:disabled { opacity: .45; cursor: default; }
  .note { margin-top: 10px; padding: 8px 10px; border-radius: 8px; font-size: 12.5px; background: color-mix(in srgb, var(--e3-accent) 10%, transparent); }
  .note.bad { background: color-mix(in srgb, var(--e3-error) 12%, transparent); color: var(--e3-error); }
  .note.warn { background: color-mix(in srgb, var(--e3-open) 14%, transparent); }
  .note.ok { background: color-mix(in srgb, var(--e3-ok) 14%, transparent); color: var(--e3-ok); display: flex; align-items: center; gap: 4px; }
  .grid2 { display: grid; grid-template-columns: auto 1fr; gap: 8px 14px; font-size: 13.5px; }
  .grid2 .key { color: var(--e3-muted); display: inline-flex; gap: 6px; align-items: center; }
  .week { display: grid; grid-template-columns: 30px 1fr; gap: 6px 8px; align-items: center; font-size: 12.5px; }
  .bar { display: flex; height: 22px; border-radius: 6px; overflow: hidden; cursor: pointer; border: 0; padding: 0; outline: 2px solid transparent; outline-offset: 2px; background: var(--e3-divider); }
  .bar.sel { outline-color: var(--e3-accent); }
  .bar span { display: flex; align-items: center; justify-content: center; font-size: 10.5px; color: #fff; font-weight: 500; overflow: hidden; }
  .bar .unknown { flex: 1; color: var(--e3-muted); }
  .axis { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--e3-muted); grid-column: 2; }
  .edit { margin-top: 14px; border: 1px solid var(--e3-divider); border-radius: 14px; padding: 12px; }
  .edit h4 { margin: 0 0 8px; font-size: 13.5px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .pt { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13.5px; flex-wrap: wrap; }
  .pt .from { width: 52px; color: var(--e3-muted); }
  .pt .time { display: inline-flex; align-items: center; gap: 2px; }
  .pt .tsel { font: inherit; color: inherit; background: var(--e3-card); border: 1px solid var(--e3-divider); border-radius: 6px; padding: 3px 2px; }
  .del { border: 0; background: none; color: var(--e3-muted); cursor: pointer; margin-left: auto; display: inline-flex; }
  .link { border: 0; background: none; color: var(--e3-accent); cursor: pointer; font-size: 13px; display: inline-flex; gap: 4px; align-items: center; padding: 4px 0; }
  .days { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px; align-items: center; font-size: 12.5px; color: var(--e3-muted); }
  .d { border: 1px solid var(--e3-divider); border-radius: 999px; padding: 4px 10px; font-size: 12.5px; background: none; cursor: pointer; }
  .d.on { background: var(--e3-accent); color: var(--text-primary-color, #fff); border-color: var(--e3-accent); }
`;

function tempColor(temperature) {
  // 17 °C and below cool blue, 21 °C and above warm orange, in between mixed.
  const f = Math.max(0, Math.min(1, (Number(temperature) - 17) / 4));
  const mix = (a, b) => Math.round(a + (b - a) * f);
  return `rgb(${mix(100, 232)}, ${mix(168, 116)}, ${mix(216, 59)})`;
}

function minutes(hhmm) {
  const [hh, mm] = String(hhmm).split(":").map(Number);
  return hh * 60 + mm;
}

if (typeof HTMLElement !== "undefined" && typeof customElements !== "undefined" && !customElements.get("eq3-max-thermostat-dialog")) {
  class Eq3MaxThermostatDialog extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._tab = "temp";
      this._drafts = {};
      this._message = null;
      this._busy = false;
      this._week = null;
      this._sig = "";
      this._onKey = (ev) => { if (ev.key === "Escape") this.close(); };
    }

    connectedCallback() {
      document.addEventListener("keydown", this._onKey);
      // Back button / back gesture closes the pop-up instead of leaving the dashboard.
      this._onPop = () => { this._historyPushed = false; this.close(); };
      window.addEventListener("popstate", this._onPop);
      history.pushState({ ...(history.state || {}), eq3MaxDialog: true }, "");
      this._historyPushed = true;
    }

    disconnectedCallback() {
      document.removeEventListener("keydown", this._onKey);
      window.removeEventListener("popstate", this._onPop);
    }

    setup(config, hass) {
      this._config = config;
      this._hass = hass;
      NUMBER_LOCALE = numberLocale(hass.locale);
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      NUMBER_LOCALE = numberLocale(hass.locale);
      const ents = findEntities(hass, this._config?.entity);
      const attrs = hass.states[this._config?.entity]?.attributes || {};
      const ids = [this._config?.entity, ...Object.values(ents), ...(attrs.fenster || []), ...(attrs.raum || [])];
      const sig = ids.map((id) => hass.states[id]?.last_updated || "").join(";") + (hass.locale?.language || "");
      if (sig !== this._sig) {
        this._sig = sig;
        // Someone is typing or choosing: rebuild once the field is left.
        const active = this.shadowRoot.activeElement;
        if (active && ["INPUT", "SELECT"].includes(active.tagName)) {
          if (!this._deferred) {
            this._deferred = true;
            active.addEventListener("blur", () => { this._deferred = false; this._render(); }, { once: true });
          }
          return;
        }
        this._render();
      }
    }

    close() {
      if (this._closed) return;
      this._closed = true;
      window.removeEventListener("popstate", this._onPop);
      // Closed by X, Escape or backdrop: take our history entry back out.
      if (this._historyPushed && history.state?.eq3MaxDialog) history.back();
      this._historyPushed = false;
      this.dispatchEvent(new CustomEvent("closed"));
    }

    get _lang() { return this._hass?.locale?.language || "en"; }

    _render() {
      const hass = this._hass;
      const lang = this._lang;
      const m = readModel(hass, this._config);
      const root = this.shadowRoot;
      // Keep the scroll position of the same tab across the rebuild.
      const oldBody = root.querySelector(".body");
      const scroll = oldBody && this._scrollTab === this._tab ? oldBody.scrollTop : 0;
      this._scrollTab = this._tab;
      root.replaceChildren(h("style", {}, DIALOG_STYLE));
      if (!m) { this.close(); return; }
      const tabs = tabsFor(m.isWall);
      const body = this._tab === "week" ? this._weekTab(lang, m) : this._tab === "info" ? this._infoTab(lang, m) : this._configTab(lang, m, this._tab);
      root.append(
        h("div", { class: "backdrop", onclick: () => this.close() }),
        h("div", { class: "dlg", role: "dialog", "aria-modal": "true", "aria-label": m.name },
          h("div", { class: "grab" }),
          h("div", { class: "dh" },
            h("span", { class: "ic" }, icon(thermostatIcon(m.climate, m.isWall))),
            h("div", { class: "t" }, h("div", { class: "n" }, m.name), h("div", { class: "k" }, t(lang, "Einstellungen"))),
            h("button", { class: "x", title: t(lang, "Schließen"), onclick: () => this.close() }, icon("mdi:close"))),
          h("div", { class: "tabs", role: "tablist" }, tabs.map((tab) =>
            h("button", {
              class: `tab${this._tab === tab.id ? " on" : ""}`, role: "tab", "aria-selected": String(this._tab === tab.id), title: t(lang, tab.title),
              onclick: () => { this._tab = tab.id; this._message = null; this._render(); },
            }, icon(tab.icon), h("span", {}, t(lang, tab.title))))),
          body.content,
          body.foot || null));
      const newBody = root.querySelector(".body");
      if (newBody && scroll) newBody.scrollTop = scroll;
      if (!this._focused) {
        // Opened: the keyboard starts inside the pop-up, not on the card behind it.
        this._focused = true;
        root.querySelector(".x")?.focus();
      }
    }

    // --- Einstellungen (number/select der Gerätekonfiguration) -----------------

    _optionLabel(lang, key, option) {
      if (key === "entkalkung_tag" && SELECT_DAYS[option]) return t(lang, SELECT_DAYS[option]);
      if (key === "anzeige" && DISPLAY_OPTIONS[option]) return t(lang, DISPLAY_OPTIONS[option]);
      if (key === "ist_abfragen" && POLL_OPTIONS[option]) return t(lang, POLL_OPTIONS[option]);
      return option;
    }

    _configTab(lang, m, tab) {
      const hass = this._hass;
      const editable = canEdit(hass, m.climate, "config");
      const rows = [];
      const original = {};
      const drafts = this._drafts;
      for (const [key, label, hint] of CONFIG_ROWS[tab] || []) {
        const id = m.ents[key];
        const st = id ? hass.states[id] : undefined;
        if (!st) continue;
        const known = id.startsWith("select.") ? (st.attributes.options || []).includes(st.state) : configNumber(st) !== null;
        if (known) original[key] = st.state;
        const value = key in drafts ? drafts[key] : known ? st.state : null;
        const changed = key in drafts && String(drafts[key]) !== String(st.state);
        if (key in drafts && !known) original[key] = null;
        const isSelect = id.startsWith("select.");
        const unit = st.attributes.unit_of_measurement || "";
        let control;
        if (!editable) {
          control = h("span", { class: "val" }, value === null ? "–" : isSelect ? this._optionLabel(lang, key, value) : `${fmt(value, Number(st.attributes.step) < 1 ? 1 : 0)} ${unit}`);
        } else if (isSelect) {
          control = h("select", { class: changed ? "changed" : "", onchange: (ev) => { drafts[key] = ev.target.value; this._render(); } },
            value === null ? h("option", { value: "", disabled: true, selected: true }, "–") : null,
            (st.attributes.options || []).map((o) => h("option", { value: o, selected: String(o) === String(value) }, this._optionLabel(lang, key, o))));
        } else if (value === null) {
          control = h("span", { class: "val" }, "–");
        } else {
          const min = Number(st.attributes.min), max = Number(st.attributes.max), step = Number(st.attributes.step) || 1;
          const digits = step < 1 ? 1 : 0;
          const set = (dir) => {
            const next = Math.round((Number(value) + dir * step) / step) * step;
            drafts[key] = Math.min(max, Math.max(min, Number(next.toFixed(2))));
            this._render();
          };
          control = h("div", { class: `st${changed ? " changed" : ""}` },
            h("button", { onclick: () => set(-1), disabled: Number(value) <= min }, "−"),
            h("span", {}, `${fmt(value, digits)} ${unit}`),
            h("button", { onclick: () => set(+1), disabled: Number(value) >= max }, "+"));
        }
        const pending = st.attributes.ausstehend;
        rows.push(h("div", { class: "row" },
          h("div", { class: "l", title: CONFIG_HELP[key] ? t(lang, CONFIG_HELP[key]) : null }, t(lang, label),
            CONFIG_HELP[key] ? h("button", { class: "info", title: t(lang, "Erklärung"), "aria-label": t(lang, "Erklärung"),
              onclick: () => { this._help = this._help === key ? null : key; this._render(); } }, icon("mdi:information-outline")) : null,
            ROOM_KEYS.includes(key) ? h("span", { class: "chip room" }, t(lang, "gilt für den Raum")) : null,
            pending !== null && pending !== undefined
              ? h("span", { class: "chip warn" }, t(lang, "ausstehend: {value}", { value: isSelect ? this._optionLabel(lang, key, pending) : pending })) : null,
            hint ? h("small", {}, t(lang, hint)) : null,
            this._help === key && CONFIG_HELP[key] ? h("div", { class: "help" }, t(lang, CONFIG_HELP[key])) : null),
          control));
      }
      const extra = [];
      if (tab === "window") {
        const contacts = (m.attrs.fenster || []).map((id) => hass.states[id]).filter(Boolean);
        extra.push(h("div", { class: "note" }, icon("mdi:link-variant"), " ", t(lang, "Verknüpfte Fensterkontakte"), ": ",
          contacts.length
            ? contacts.map((s) => `${s.attributes.friendly_name || s.entity_id} (${t(lang, s.state === "on" ? "offen" : "zu")})`).join(", ")
            : t(lang, "keiner")));
      }
      if (!editable) extra.push(h("div", { class: "note warn" }, t(lang, "Nur Anzeige: Änderungen sind für dein Konto gesperrt (Option der Integration).")));
      if (this._message?.sent) {
        // Sent values are pending until the device acknowledges; then say so.
        const waiting = (CONFIG_ROWS[tab] || []).some(([key]) => {
          const st = m.ents[key] ? hass.states[m.ents[key]] : undefined;
          return st && st.attributes.ausstehend !== null && st.attributes.ausstehend !== undefined;
        });
        this._message.text = t(lang, waiting ? "Gesendet – wartet auf Quittung." : "Vom Gerät quittiert.");
        this._message.ok = !waiting;
      }
      if (this._message) extra.push(h("div", { class: `note${this._message.bad ? " bad" : this._message.ok ? " ok" : ""}` },
        this._message.ok ? icon("mdi:check-circle") : null, " ", this._message.text));
      const changes = changedValues(original, Object.fromEntries(Object.entries(drafts).filter(([k]) => k in original)));
      const n = Object.keys(changes).length;
      const foot = editable ? h("div", { class: "foot" },
        h("span", { class: "info" }, n ? t(lang, "{n} geändert", { n }) : ""),
        h("button", { class: "btn", disabled: !n || this._busy, onclick: () => { for (const k of Object.keys(changes)) delete drafts[k]; this._render(); } }, t(lang, "Verwerfen")),
        h("button", { class: "btn p", disabled: !n || this._busy, onclick: () => this._apply(m, changes) }, t(lang, "Übernehmen"))) : null;
      return { content: h("div", { class: "body" }, rows, extra), foot };
    }

    async _apply(m, changes) {
      this._busy = true;
      this._message = null;
      this._render();
      try {
        for (const [key, value] of Object.entries(changes)) {
          const id = m.ents[key];
          if (id.startsWith("select.")) await this._hass.callService("select", "select_option", { entity_id: id, option: value });
          else await this._hass.callService("number", "set_value", { entity_id: id, value: Number(value) });
          delete this._drafts[key];
        }
        this._message = { text: t(this._lang, "Gesendet – wartet auf Quittung."), bad: false, sent: true };
      } catch (err) {
        this._message = { text: err?.message || String(err), bad: true };
      } finally {
        this._busy = false;
        this._render();
      }
    }

    // --- Info ------------------------------------------------------------------

    _infoTab(lang, m) {
      const hass = this._hass;
      const entry = hass.entities?.[this._config.entity];
      const device = entry?.device_id ? hass.devices?.[entry.device_id] : undefined;
      const rssiAttrs = m.ents.funkmodul ? hass.states[m.ents.funkmodul]?.attributes || {} : {};
      const moduleNames = m.ents.funkmodul ? hass.states[m.ents.funkmodul]?.attributes?.options || [] : [];
      const perRadio = Object.entries(rssiAttrs).filter(([k, v]) => k.startsWith("rssi_") && v !== null)
        .map(([k, v]) => `${moduleLabel(k, moduleNames)}: ${fmt(v, 0)} dBm`);
      const rows = [
        ["mdi:battery", "Batterie", t(lang, m.lowBattery ? "schwach" : "ok")],
        [RSSI_ICONS[m.level] || "mdi:signal", "Funk", m.rf ? t(lang, "Funkfehler") : perRadio.length ? perRadio.join(", ") : `${fmt(m.rssi, 0)} dBm`],
        ["mdi:clock-outline", "Zuletzt", ageText(lang, m.lastSeen) || "–"],
        ["mdi:link-variant", "Verknüpft", m.links.length ? m.links.join(", ") : t(lang, "keiner")],
        [m.locked ? "mdi:lock" : "mdi:lock-open-variant", "Bediensperre", t(lang, m.locked ? "an" : "aus")],
        ["mdi:barcode", "Seriennummer", device?.serial_number || m.attrs.id || "–"],
        ["mdi:chip", "Firmware", device?.sw_version || "–"],
      ];
      return { content: h("div", { class: "body" }, h("div", { class: "grid2" }, rows.map(([ic, key, value]) =>
        [h("span", { class: "key" }, icon(ic), t(lang, key)), h("span", {}, value)]))) };
    }

    // --- Wochenprogramm ----------------------------------------------------------

    _weekTab(lang, m) {
      const hass = this._hass;
      const editable = canEdit(hass, m.climate, "week");
      const rows = weekRows(m.attrs.wochenprogramm);
      const w = this._week;
      const bars = h("div", { class: "week" },
        rows.map((row) => [
          h("span", {}, t(lang, DAY_SHORT[row.day])),
          h("button", {
            class: `bar${w && w.day === row.day ? " sel" : ""}`, title: t(lang, row.day),
            onclick: editable ? () => this._editDay(row) : null,
          }, row.known
            ? row.segments.map((s) => h("span", { style: { flex: String(minutes(s.to) - minutes(s.from)), background: tempColor(s.temperature) } },
              minutes(s.to) - minutes(s.from) >= 120 ? fmt(s.temperature, s.temperature % 1 ? 1 : 0) : ""))
            : h("span", { class: "unknown" }, t(lang, "unbekannt"))),
        ]),
        h("div", { class: "axis" }, ["0", "6", "12", "18", "24"].map((x) => h("span", {}, x))));
      const parts = [bars];
      if (editable && w) parts.push(this._editor(lang, m));
      const writing = m.attrs.wochenprogramm_schreibt || [];
      if (writing.length) parts.push(h("div", { class: "note warn" }, icon("mdi:timer-sand"), " ",
        t(lang, "schreibt: {days}", { days: writing.map((d) => t(lang, d)).join(", ") })));
      const error = m.attrs.wochenprogramm_fehler;
      if (error && !writing.length) parts.push(h("div", { class: "note bad" }, `${t(lang, "Letztes Schreiben abgebrochen")}: ${this._errorText(error)}`));
      parts.push(h("div", { class: "note" }, t(lang, "Das Gerät meldet sein Programm nicht. Gezeigt wird, was es zuletzt quittiert hat. Jeder Tag ist ein Funktelegramm; bei knappem Funkbudget kann eine Woche einige Minuten dauern.")));
      if (!editable) parts.push(h("div", { class: "note warn" }, t(lang, "Nur Anzeige: Änderungen sind für dein Konto gesperrt (Option der Integration).")));
      if (this._message?.writing) {
        // Started writing; once no day is open any more, say so (or show the error above).
        if (writing.length) this._message.seen = true;
        if ((this._message.seen || Date.now() - this._message.started > 5000) && !writing.length) {
          this._message = error ? null : { text: t(lang, "Vom Gerät quittiert."), ok: true };
        }
      }
      if (this._message) parts.push(h("div", { class: `note${this._message.bad ? " bad" : this._message.ok ? " ok" : ""}` },
        this._message.ok ? icon("mdi:check-circle") : null, " ", this._message.text));
      let foot = null;
      if (editable && w) {
        const n = w.targets.size;
        foot = h("div", { class: "foot" },
          h("span", { class: "info" }, this._copySelect(lang, m)),
          h("button", { class: "btn", onclick: () => { this._week = null; this._message = null; this._render(); } }, t(lang, "Verwerfen")),
          h("button", { class: "btn p", disabled: !n || this._busy || profileErrors(w.segments).length > 0, onclick: () => this._writeWeek(m) },
            n === 1 ? t(lang, "Auf 1 Tag schreiben") : t(lang, "Auf {n} Tage schreiben", { n })));
      }
      return { content: h("div", { class: "body" }, parts), foot };
    }

    _errorText(error) {
      if (typeof error === "string") return error;
      const localized = error.key && this._hass.localize
        ? this._hass.localize(`component.eq3_max.exceptions.${error.key}.message`, error.placeholders || {}) : "";
      if (!localized && error.key && this._hass.loadBackendTranslation && !this._loadedExceptions) {
        // The frontend loads the integration's error texts only on demand.
        this._loadedExceptions = true;
        this._hass.loadBackendTranslation("exceptions", "eq3_max").then(() => this._render()).catch(() => {});
      }
      const missing = Array.isArray(error.missing) && error.missing.length ? ` (${error.missing.map((d) => t(this._lang, d)).join(", ")})` : "";
      return (localized || error.message || "") + missing;
    }

    _editDay(row) {
      const template = !row.known;
      const segments = (template ? profileDay(FACTORY_WEEK_PROFILE[row.day]) : row.segments).map((s) => ({ ...s }));
      this._week = { day: row.day, segments, template, targets: new Set([row.day]) };
      this._message = null;
      this._render();
    }

    _editor(lang, m) {
      const w = this._week;
      const segs = w.segments;
      // "from" always follows the previous "to".
      segs.forEach((s, i) => { s.from = i === 0 ? "00:00" : segs[i - 1].to; });
      const room = (m.attrs.raum || []).map((id) => this._hass.states[id]?.attributes?.friendly_name || id);
      return h("div", { class: "edit" },
        h("h4", {}, icon("mdi:pencil"), t(lang, "{day} bearbeiten", { day: t(lang, w.day) }),
          w.template ? h("span", { class: "chip warn" }, t(lang, "Vorlage: Werksprogramm")) : null),
        segs.map((s, i) => {
          const last = i === segs.length - 1;
          const temp = (dir) => { s.temperature = stepTarget(s.temperature, dir); this._render(); };
          return h("div", { class: "pt" },
            h("span", { class: "from" }, s.from),
            "–",
            last ? h("span", { class: "from" }, "24:00") : timeSelect(s.to, (value) => { s.to = value; this._render(); }),
            h("div", { class: "st" },
              h("button", { onclick: () => temp(-1) }, "−"),
              h("span", {}, `${fmt(s.temperature)} °C`),
              h("button", { onclick: () => temp(+1) }, "+")),
            last ? null : h("button", { class: "del", title: "×", onclick: () => { segs.splice(i, 1); this._render(); } }, icon("mdi:close")));
        }),
        segs.length < 13 ? h("button", { class: "link", onclick: () => this._insertPeriod() }, icon("mdi:plus"), t(lang, "Zeitraum einfügen")) : null,
        h("div", { class: "days" }, t(lang, "Schreiben auf:"),
          WEEKDAYS.map((day) => h("button", {
            class: `d${w.targets.has(day) ? " on" : ""}`,
            onclick: () => { w.targets.has(day) ? w.targets.delete(day) : w.targets.add(day); this._render(); },
          }, t(lang, DAY_SHORT[day]))),
          h("button", { class: "link", onclick: () => {
            w.targets = w.targets.size === WEEKDAYS.length ? new Set() : new Set(WEEKDAYS); this._render();
          } }, t(lang, w.targets.size === WEEKDAYS.length ? "keinen" : "alle"))),
        room.length ? h("div", { class: "note" }, icon("mdi:home-group"), " ", t(lang, "Geht auch an: {names}", { names: room.join(", ") })) : null,
        profileErrors(segs).map((e) => h("div", { class: "note bad" }, t(lang, e === "order"
          ? "Die Endzeiten müssen von oben nach unten steigen." : "Endzeiten nur in 5-Minuten-Schritten."))));
    }

    _insertPeriod() {
      const segs = this._week.segments;
      segs.forEach((s, i) => { s.from = i === 0 ? "00:00" : segs[i - 1].to; });
      let longest = 0;
      segs.forEach((s, i) => { if (minutes(s.to) - minutes(s.from) > minutes(segs[longest].to) - minutes(segs[longest].from)) longest = i; });
      const s = segs[longest];
      const mid = Math.round((minutes(s.from) + minutes(s.to)) / 2 / 30) * 30;
      const hh = String(Math.floor(mid / 60)).padStart(2, "0"), mm = String(mid % 60).padStart(2, "0");
      segs.splice(longest, 0, { from: s.from, to: `${hh}:${mm}`, temperature: s.temperature });
      this._render();
    }

    _copySelect(lang, m) {
      const sources = Object.values(this._hass.entities || {})
        .filter((e) => e.platform === "eq3_max" && e.entity_id.startsWith("climate.") && e.entity_id !== this._config.entity)
        .map((e) => this._hass.states[e.entity_id])
        .filter((s) => s && s.attributes.wochenprogramm && Object.keys(s.attributes.wochenprogramm).length);
      if (!sources.length) return "";
      return h("select", {
        onchange: (ev) => {
          const src = this._hass.states[ev.target.value];
          const points = src?.attributes?.wochenprogramm?.[this._week.day];
          if (points?.length) {
            this._week.segments = profileDay(points);
            this._week.template = false;
          }
          this._render();
        },
      }, h("option", { value: "" }, t(lang, "Kopieren von …")),
      sources.map((s) => h("option", { value: s.entity_id }, s.attributes.friendly_name || s.entity_id)));
    }

    async _writeWeek(m) {
      const w = this._week;
      this._busy = true;
      this._message = null;
      this._render();
      try {
        await this._hass.callService("eq3_max", "set_week_profile", {
          device_id: m.deviceId,
          weekday: WEEKDAYS.filter((d) => w.targets.has(d)),
          profile: segmentsToProfile(w.segments),
        });
        this._week = null;
        this._message = { text: t(this._lang, "Wochenprogramm wird geschrieben."), bad: false, writing: true, started: Date.now() };
      } catch (err) {
        this._message = { text: err?.message || String(err), bad: true };
      } finally {
        this._busy = false;
        this._render();
      }
    }
  }

  customElements.define("eq3-max-thermostat-dialog", Eq3MaxThermostatDialog);
}

if (typeof HTMLElement !== "undefined" && typeof customElements !== "undefined" && !customElements.get("eq3-max-thermostat-card-editor")) {
  class Eq3MaxThermostatCardEditor extends HTMLElement {
    setConfig(config) {
      this._config = { layout: "kompakt", show_modes: true, ...config };
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      if (this._form) this._form.hass = hass;
      else this._render();
    }

    _render() {
      if (!this._hass || !this._config) return;
      const lang = this._hass.locale?.language || "en";
      if (!this._form) {
        this._form = document.createElement("ha-form");
        this._form.addEventListener("value-changed", (ev) => {
          const config = { ...this._config, ...ev.detail.value };
          for (const key of ["name", "temperature_sensor", "humidity_sensor"]) if (!config[key]) delete config[key];
          this._config = config;
          this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
        });
        this.append(this._form);
      }
      this._form.hass = this._hass;
      this._form.schema = [
        { name: "entity", required: true, selector: { entity: { filter: { domain: "climate", integration: "eq3_max" } } } },
        { name: "layout", selector: { select: { mode: "dropdown", options: ["kompakt", "ring", "kachel"].map((v) => ({ value: v, label: t(lang, v) })) } } },
        { name: "name", selector: { text: {} } },
        { name: "temperature_sensor", selector: { entity: { filter: { domain: "sensor", device_class: "temperature" } } } },
        { name: "humidity_sensor", selector: { entity: { filter: { domain: "sensor", device_class: "humidity" } } } },
        { name: "show_modes", selector: { boolean: {} } },
      ];
      const labels = { entity: "Entität", layout: "Layout", name: "Name (optional)", show_modes: "Modus-Knöpfe zeigen",
        temperature_sensor: "Externer Temperatursensor (optional)", humidity_sensor: "Externer Feuchtesensor (optional)" };
      this._form.computeLabel = (schema) => t(lang, labels[schema.name] || schema.name);
      this._form.data = this._config;
    }
  }

  customElements.define("eq3-max-thermostat-card-editor", Eq3MaxThermostatCardEditor);
}
