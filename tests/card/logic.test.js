import { test } from "node:test";
import assert from "node:assert/strict";

import {
  rssiLevel,
  findEntities,
  windowState,
  contactIcon,
  contactKind,
  thermostatIcon,
  profileDay,
  weekRows,
  segmentsToProfile,
  tabsFor,
  canEdit,
  changedValues,
  stepTarget,
  baseTarget,
  profileErrors,
  configNumber,
  ringTemperature,
  ringAngle,
  ringHit,
  tempRange,
  numberLocale,
  isUnavailable,
  sensorValue,
  entitySuggestion,
  currentReading,
  moduleLabel,
  sectionColumns,
  timeOptions,
  FACTORY_WEEK_PROFILE,
  WEEKDAYS,
  ROOM_KEYS,
  t,
} from "../../custom_components/eq3_max/frontend/eq3-max-thermostat-card.js";

const CLIMATE = "climate.ht_wohnzimmer";
const DEV = "dev1";

function entity(entity_id, translation_key, device_id = DEV, platform = "eq3_max") {
  return { entity_id, translation_key, device_id, platform };
}

function hassWith(states = {}, extra = {}) {
  const entities = {
    [CLIMATE]: entity(CLIMATE, undefined),
    "sensor.ht_wohnzimmer_ventil": entity("sensor.ht_wohnzimmer_ventil", "ventil"),
    "sensor.ht_wohnzimmer_rssi": entity("sensor.ht_wohnzimmer_rssi", "rssi"),
    "binary_sensor.ht_wohnzimmer_lowbat": entity("binary_sensor.ht_wohnzimmer_lowbat", "lowbat"),
    "number.umbenannt": entity("number.umbenannt", "komfort"),
    "number.ht_wohnzimmer_fenster_temperatur": entity("number.ht_wohnzimmer_fenster_temperatur", "fenster_temperatur"),
    "number.fremd_komfort": entity("number.fremd_komfort", "komfort", "dev2"),
    "sensor.other_platform": entity("sensor.other_platform", "ventil", DEV, "mqtt"),
  };
  return { entities, states, user: { is_admin: false }, locale: { language: "de" }, ...extra };
}

test("rssiLevel thresholds and radio error", () => {
  assert.equal(rssiLevel(-61, false), "good");
  assert.equal(rssiLevel(-70, false), "mid");
  assert.equal(rssiLevel(-85, false), "mid");
  assert.equal(rssiLevel(-88, false), "weak");
  assert.equal(rssiLevel(-61, true), "off");
  assert.equal(rssiLevel(null, false), null);
});

test("findEntities matches device, platform and translation_key, survives renames", () => {
  const found = findEntities(hassWith(), CLIMATE);
  assert.equal(found.ventil, "sensor.ht_wohnzimmer_ventil");
  assert.equal(found.komfort, "number.umbenannt");
  assert.equal(found.lowbat, "binary_sensor.ht_wohnzimmer_lowbat");
  assert.equal(found.funkfehler, undefined);
  assert.equal(findEntities(hassWith(), "climate.unknown").ventil, undefined);
});

test("windowState from linked contacts", () => {
  const climate = { state: "heat", attributes: { fenster: ["binary_sensor.fk"], temperature: 21 } };
  const hass = hassWith({ "binary_sensor.fk": { state: "on", attributes: { friendly_name: "Terrassentür" } } });
  assert.deepEqual(windowState(hass, climate, {}), {
    shown: true, open: true, names: ["Terrassentür"], icon: "mdi:window-open-variant", kind: "window" });
  hass.states["binary_sensor.fk"].state = "off";
  assert.equal(windowState(hass, climate, {}).open, false);
});

test("windowState without contact: own detection at the window-open temperature", () => {
  const ents = { fenster_temperatur: "number.ht_wohnzimmer_fenster_temperatur" };
  const hass = hassWith({ "number.ht_wohnzimmer_fenster_temperatur": { state: "12.0" } });
  const at12 = { state: "heat", attributes: { fenster: [], temperature: 12, preset_mode: "none" } };
  assert.deepEqual(windowState(hass, at12, ents), { shown: true, open: true, names: [], icon: "mdi:window-open-variant", kind: "window" });
  const normal = { state: "heat", attributes: { fenster: [], temperature: 21 } };
  assert.deepEqual(windowState(hass, normal, ents), { shown: false, open: false, names: [], icon: "mdi:window-closed-variant", kind: "window" });
  const auto12 = { state: "auto", attributes: { fenster: [], temperature: 12 } };
  assert.equal(windowState(hass, auto12, ents).shown, false);
});

test("profileDay turns points into segments", () => {
  assert.deepEqual(profileDay([{ temperature: 17, until: "06:00" }, { temperature: 21, until: "24:00" }]), [
    { from: "00:00", to: "06:00", temperature: 17 },
    { from: "06:00", to: "24:00", temperature: 21 },
  ]);
});

test("weekRows: Monday first, unknown days marked", () => {
  const rows = weekRows({ Montag: [{ temperature: 17, until: "24:00" }] });
  assert.deepEqual(rows.map((r) => r.day), ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]);
  assert.equal(rows[0].known, true);
  assert.equal(rows[1].known, false);
  assert.deepEqual(rows[1].segments, []);
  assert.equal(weekRows(undefined).every((r) => !r.known), true);
});

test("factory program as the integration has it", () => {
  assert.deepEqual(FACTORY_WEEK_PROFILE.Montag[0], { temperature: 17, until: "06:00" });
  assert.equal(FACTORY_WEEK_PROFILE.Montag.length, 5);
  assert.equal(FACTORY_WEEK_PROFILE.Samstag.length, 3);
  assert.equal(WEEKDAYS.length, 7);
});

test("segmentsToProfile: last point without until, sorted", () => {
  assert.deepEqual(
    segmentsToProfile([
      { from: "00:00", to: "06:00", temperature: 17 },
      { from: "06:00", to: "24:00", temperature: 21.5 },
    ]),
    [{ temperature: 17, until: "06:00" }, { temperature: 21.5 }],
  );
});

test("tabsFor radiator and wall thermostat", () => {
  assert.deepEqual(tabsFor(false).map((x) => x.id), ["temp", "window", "boost", "week", "info"]);
  assert.equal(tabsFor(false)[2].title, "Boost & Ventil");
  assert.equal(tabsFor(true)[2].title, "Boost & Anzeige");
});

test("canEdit: admin always, others by attribute", () => {
  const locked = { attributes: { einstellungen_frei: false, wochenprogramm_frei: true } };
  assert.equal(canEdit({ user: { is_admin: true } }, locked, "config"), true);
  assert.equal(canEdit({ user: { is_admin: false } }, locked, "config"), false);
  assert.equal(canEdit({ user: { is_admin: false } }, locked, "week"), true);
  assert.equal(canEdit({ user: { is_admin: false } }, { attributes: {} }, "config"), true);
});

test("changedValues only returns differing keys", () => {
  assert.deepEqual(changedValues({ komfort: 21, eco: 17 }, { komfort: 21, eco: 16.5 }), { eco: 16.5 });
  assert.deepEqual(changedValues({ komfort: 21 }, {}), {});
});

test("stepTarget clamps to 4.5..30.5 in 0.5 steps", () => {
  assert.equal(stepTarget(21, +1), 21.5);
  assert.equal(stepTarget(4.5, -1), 4.5);
  assert.equal(stepTarget(30.5, +1), 30.5);
  assert.equal(stepTarget(null, +1), 21);
});

test("room keys and translations", () => {
  assert.ok(ROOM_KEYS.includes("komfort") && !ROOM_KEYS.includes("offset"));
  assert.equal(t("en", "Boost & Ventil"), "Boost & valve");
  assert.equal(t("de", "Boost & Ventil"), "Boost & Ventil");
  assert.equal(t("en", "{n} geändert", { n: 2 }), "2 changed");
  assert.equal(t("fr", "Fenster"), "Window");
});


test("baseTarget: a pending target counts, so taps add up", () => {
  assert.equal(baseTarget({ temperature: 21, ausstehend: 22 }), 22);
  assert.equal(baseTarget({ temperature: 21, ausstehend: null }), 21);
  assert.equal(stepTarget(baseTarget({ temperature: 21, ausstehend: 21.5 }), +1), 22);
});

test("segmentsToProfile keeps the editor order (no silent re-sorting)", () => {
  assert.deepEqual(
    segmentsToProfile([{ to: "08:00", temperature: 21 }, { to: "06:00", temperature: 17 }, { to: "24:00", temperature: 18 }]),
    [{ temperature: 21, until: "08:00" }, { temperature: 17, until: "06:00" }, { temperature: 18 }],
  );
});

test("profileErrors: end times must rise and lie on 5 minutes", () => {
  assert.deepEqual(profileErrors([{ to: "06:00" }, { to: "22:00" }, { to: "24:00" }]), []);
  assert.deepEqual(profileErrors([{ to: "08:00" }, { to: "06:00" }, { to: "24:00" }]), ["order"]);
  assert.deepEqual(profileErrors([{ to: "06:03" }, { to: "24:00" }]), ["grid"]);
});

test("configNumber: unknown/unavailable states are no number", () => {
  assert.equal(configNumber({ state: "21.0" }), 21);
  assert.equal(configNumber({ state: "unknown" }), null);
  assert.equal(configNumber({ state: "unavailable" }), null);
  assert.equal(configNumber(undefined), null);
});


test("ringTemperature maps the 270° arc to 4.5..30.5 in 0.5 steps", () => {
  // Arc starts bottom-left (135°), runs clockwise over the top to bottom-right (45°).
  const at = (deg) => ringTemperature(Math.cos((deg * Math.PI) / 180), Math.sin((deg * Math.PI) / 180));
  assert.equal(at(135), 4.5);
  assert.equal(at(270), 17.5); // top: half way
  assert.equal(at(45), 30.5);
  assert.equal(at(90), 30.5); // gap below, nearer the end
  assert.equal(at(80), 30.5);
  assert.equal(at(100), 4.5);
  assert.equal(at(120), 4.5); // gap below, nearer the start
});

test("ringAngle is the inverse for the handle", () => {
  assert.equal(ringAngle(4.5), 135);
  assert.equal(ringAngle(30.5), 405);
  assert.equal(ringAngle(17.5), 270);
});


test("isUnavailable: unavailable or unknown climate", () => {
  assert.equal(isUnavailable({ state: "unavailable" }), true);
  assert.equal(isUnavailable({ state: "unknown" }), true);
  assert.equal(isUnavailable({ state: "heat" }), false);
  assert.equal(isUnavailable(undefined), true);
});

test("moduleLabel: rssi_<slug> attribute back to the module's name", () => {
  const names = ["Hauptmodul", "Büro", "Obergeschoss Süd"];
  assert.equal(moduleLabel("rssi_buro", names), "Büro");
  assert.equal(moduleLabel("rssi_obergeschoss_sud", names), "Obergeschoss Süd");
  assert.equal(moduleLabel("rssi_hauptmodul", names), "Hauptmodul");
  assert.equal(moduleLabel("rssi_unbekannt", names), "unbekannt");
});

test("sensorValue: external sensor reading, null when unset, unavailable or not numeric", () => {
  const hass = { states: {
    "sensor.t": { state: "21.4" },
    "sensor.off": { state: "unavailable" },
    "sensor.unk": { state: "unknown" },
    "sensor.txt": { state: "abc" },
  } };
  assert.equal(sensorValue(hass, "sensor.t"), 21.4);
  assert.equal(sensorValue(hass, undefined), null);
  assert.equal(sensorValue(hass, "sensor.missing"), null);
  assert.equal(sensorValue(hass, "sensor.off"), null);
  assert.equal(sensorValue(hass, "sensor.unk"), null);
  assert.equal(sensorValue(hass, "sensor.txt"), null);
});

test("entitySuggestion: only for climate entities of eq3_max", () => {
  const hass = hassWith();
  assert.deepEqual(entitySuggestion(hass, CLIMATE), {
    config: { type: "custom:eq3-max-thermostat-card", entity: CLIMATE, layout: "kompakt" },
  });
  assert.equal(entitySuggestion(hass, "sensor.ht_wohnzimmer_ventil"), null); // not climate
  hass.entities["climate.fremd"] = entity("climate.fremd", undefined, "dev3", "mqtt");
  assert.equal(entitySuggestion(hass, "climate.fremd"), null); // other integration
  assert.equal(entitySuggestion(hass, "climate.unknown"), null); // not in the registry
  assert.equal(entitySuggestion(hass, undefined), null);
});

test("currentReading: external sensor first, the thermostat's own reading stays known", () => {
  const hass = hassWith({
    [CLIMATE]: { state: "heat", attributes: { current_temperature: 19.5 } },
    "sensor.raum": { state: "21.4" },
    "sensor.weg": { state: "unavailable" },
  });
  assert.deepEqual(currentReading(hass, { entity: CLIMATE, temperature_sensor: "sensor.raum" }),
    { current: 21.4, currentEntity: "sensor.raum", own: 19.5, external: true });
  assert.deepEqual(currentReading(hass, { entity: CLIMATE, temperature_sensor: "sensor.weg" }),
    { current: 19.5, currentEntity: CLIMATE, own: 19.5, external: false });
  assert.deepEqual(currentReading(hass, { entity: CLIMATE }),
    { current: 19.5, currentEntity: CLIMATE, own: 19.5, external: false });
});

test("ringHit: only the arc band sets the target, not the valve arc or the gap", () => {
  const at = (deg, r) => ringHit(r * Math.cos((deg * Math.PI) / 180), r * Math.sin((deg * Math.PI) / 180));
  assert.equal(at(270, 80), "ring"); // top of the arc
  assert.equal(at(135, 80), "ring"); // start
  assert.equal(at(45, 80), "ring"); // end
  assert.equal(at(90, 80), "none"); // gap at the bottom: was 30.5 °C
  assert.equal(at(100, 85), "none");
  assert.equal(at(90, 64), "centre"); // valve arc / valve line
  assert.equal(at(200, 64), "centre");
  assert.equal(at(0, 0), "centre");
  assert.equal(at(270, 110), "none");
});

test("findEntities searches once per registry, again when the registry changes", () => {
  const hass = hassWith();
  const first = findEntities(hass, CLIMATE);
  assert.equal(findEntities({ ...hass, states: { x: 1 } }, CLIMATE), first); // same registry object: cached
  const renamed = { ...hass, entities: { ...hass.entities, "sensor.neu": entity("sensor.neu", "zuletzt_gemeldet") } };
  assert.equal(findEntities(renamed, CLIMATE).zuletzt_gemeldet, "sensor.neu");
  assert.equal(first.zuletzt_gemeldet, undefined);
});

test("tempRange: from the climate entity, MAX! values and °C where it says nothing", () => {
  assert.deepEqual(tempRange({}, { attributes: {} }), { min: 4.5, max: 30.5, step: 0.5, unit: "°C" });
  const imperial = { config: { unit_system: { temperature: "°F" } } };
  assert.deepEqual(tempRange(imperial, { attributes: { min_temp: 40.1, max_temp: 86.9, target_temp_step: 0.5 } }),
    { min: 40.1, max: 86.9, step: 0.5, unit: "°F" });
  assert.equal(tempRange({}, { attributes: { target_temp_step: 0 } }).step, 0.5);
});

test("stepTarget, ringTemperature and ringAngle follow a given range (°F)", () => {
  const f = { min: 40, max: 87, step: 1 };
  assert.equal(stepTarget(70, +1, f), 71);
  assert.equal(stepTarget(87, +1, f), 87);
  assert.equal(stepTarget(null, +1, f), 64); // 21 is outside: middle of the range
  const at = (deg) => ringTemperature(Math.cos((deg * Math.PI) / 180), Math.sin((deg * Math.PI) / 180), f);
  assert.equal(at(135), 40);
  assert.equal(at(45), 87);
  assert.equal(at(270), 64);
  assert.equal(ringAngle(40, f), 135);
  assert.equal(ringAngle(87, f), 405);
});

test("numberLocale: the profile's number format, else its language", () => {
  assert.equal(numberLocale({ language: "en", number_format: "language" }), "en");
  assert.equal(numberLocale({ language: "en", number_format: "decimal_comma" }), "de");
  assert.equal(numberLocale({ language: "de", number_format: "comma_decimal" }), "en-US");
  assert.equal(numberLocale({ language: "de", number_format: "system" }), undefined);
  assert.equal(numberLocale(undefined), undefined);
});

test("sectionColumns: alone full width, pairs side by side, the odd one out full width", () => {
  const cols = (half) => half.map((_, index) => sectionColumns({ half, index }));
  assert.deepEqual(cols([false, true]), [6, 12]); // heading + one thermostat
  assert.deepEqual(cols([false, true, true]), [6, 6, 6]);
  assert.deepEqual(cols([false, true, true, true]), [6, 6, 6, 12]);
  assert.deepEqual(cols([true, false, true, true]), [12, 6, 6, 6]); // runs count separately
  assert.equal(sectionColumns(null), 6); // not in a sections view
});

test("timeOptions: 24 hours, minutes in steps of five, an odd minute is kept", () => {
  const o = timeOptions("06:30");
  assert.equal(o.hour, "06"); assert.equal(o.minute, "30");
  assert.equal(o.hours.length, 24); assert.equal(o.hours[23], "23");
  assert.deepEqual(o.minutes, ["00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55"]);
  assert.ok(timeOptions("17:03").minutes.includes("03"));
});

test("contactIcon follows the device class and the icon set in Home Assistant", () => {
  assert.equal(contactIcon({ attributes: { device_class: "door" } }, true), "mdi:door-open");
  assert.equal(contactIcon({ attributes: { device_class: "door" } }, false), "mdi:door-closed");
  assert.equal(contactIcon({ attributes: { device_class: "garage_door" } }, false), "mdi:garage");
  assert.equal(contactIcon({ attributes: { device_class: "window" } }, false), "mdi:window-closed-variant");
  assert.equal(contactIcon({ attributes: {} }, true), "mdi:window-open-variant");
  assert.equal(contactIcon({ attributes: { device_class: "door", icon: "mdi:gate" } }, true), "mdi:gate");
  assert.equal(contactIcon(undefined, false), "mdi:window-closed-variant");
});

test("windowState: a door contact shows as a door, the open one decides", () => {
  const climate = { state: "heat", attributes: { fenster: ["binary_sensor.fenster", "binary_sensor.tuer"] } };
  const hass = hassWith({
    "binary_sensor.fenster": { state: "off", attributes: { friendly_name: "Fenster", device_class: "window" } },
    "binary_sensor.tuer": { state: "on", attributes: { friendly_name: "Tür", device_class: "door" } },
  });
  const open = windowState(hass, climate, {});
  assert.equal(open.icon, "mdi:door-open");
  assert.equal(open.kind, "door");
  hass.states["binary_sensor.tuer"].state = "off";
  const closed = windowState(hass, climate, {});
  assert.equal(closed.icon, "mdi:window-closed-variant");
  assert.equal(closed.kind, "window");
  assert.equal(contactKind([]), "window");
});

test("thermostatIcon: the icon set in Home Assistant wins", () => {
  assert.equal(thermostatIcon({ attributes: {} }, false), "mdi:radiator");
  assert.equal(thermostatIcon({ attributes: {} }, true), "mdi:thermostat");
  assert.equal(thermostatIcon({ attributes: { icon: "mdi:heating-coil" } }, false), "mdi:heating-coil");
});
