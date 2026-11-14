// Seite „eQ-3 MAX!“ – Übersicht, Verknüpfungen und Gerätekonfiguration.
// Vanilla Custom Element ohne Build-Schritt und ohne Fremdbibliotheken.
// Daten kommen ausschließlich über die WebSocket-Befehle eq3_max/*.

// --- Sprache ---------------------------------------------------------------
// Deutsch ist der Schlüssel (wie bei gettext), Englisch steht in EN. LANG folgt der
// Sprache des Home-Assistant-Benutzers (siehe `set hass`).

let LANG = "de";

const EN = {
  // Betriebsarten, Zustände, Quellen
  "Automatik": "Auto",
  "Manuell": "Manual",
  "Temporär": "Temporary",
  "Boost": "Boost",
  "Abwesend": "Away",
  "Aus": "Off",
  "Homegear": "Homegear",
  "Werksvorgabe": "Factory default",
  "gemeldet": "reported",
  "unbekannt": "unknown",
  "gesetzt": "set",
  "ausstehend": "pending",
  "wartet auf Gerät": "waiting for device",
  "fehlgeschlagen": "failed",
  "fehlgeschlagen (abgelehnt)": "failed (rejected)",
  "abgelehnt": "rejected",
  "einseitig": "one-sided",
  "wartet auf Fensterkontakt – bitte Fenster einmal öffnen und schließen":
    "waiting for window contact – please open and close the window once",
  "wartet auf Eco-Taster – bitte Taster einmal drücken (oder Anlerntaste)":
    "waiting for eco button – please press the button once (or the pairing button)",
  "Fensterkontakte hören nur kurz nach dem eigenen Senden zu: Änderungen gehen erst raus, wenn das Fenster einmal geöffnet und geschlossen wird.":
    "Window contacts only listen briefly after they send themselves: changes go out once the window has been opened and closed.",
  "Eco-Taster hören nur kurz nach dem eigenen Senden zu: Änderungen gehen erst raus, wenn der Taster einmal gedrückt wird (oder die Anlerntaste).":
    "Eco buttons only listen briefly after they send themselves: changes go out once the button has been pressed (or the pairing button).",
  // Gerätetypen
  "Cube": "Cube",
  "Heizkörperthermostat": "Radiator thermostat",
  "Heizkörperthermostat+": "Radiator thermostat+",
  "Wandthermostat": "Wall thermostat",
  "Fensterkontakt": "Window contact",
  "Eco-Taster": "Eco button",
  "Zwischenstecker (noch nicht unterstützt)": "Plug adapter (not supported yet)",
  "Unbekannt": "Unknown",
  // Konfiguration
  "Temperaturen": "Temperatures",
  "Ventil": "Valve",
  "Komforttemperatur": "Comfort temperature",
  "Eco-Temperatur": "Eco temperature",
  "Maximaltemperatur": "Maximum temperature",
  "Minimaltemperatur": "Minimum temperature",
  "Temperatur-Offset": "Temperature offset",
  "Fenster-auf-Temperatur": "Window open temperature",
  "Fenster-auf-Dauer": "Window open duration",
  "Boost-Dauer": "Boost duration",
  "Boost-Ventilstellung": "Boost valve position",
  "Entkalkung Tag": "Decalcification day",
  "Anzeige": "Display",
  "Soll-Temperatur": "Set temperature",
  "Ist-Temperatur": "Current temperature",
  "Entkalkung Stunde": "Decalcification hour",
  "Ventil maximal": "Valve maximum",
  "Ventil-Offset": "Valve offset",
  // Wochentage
  "Montag": "Monday",
  "Dienstag": "Tuesday",
  "Mittwoch": "Wednesday",
  "Donnerstag": "Thursday",
  "Freitag": "Friday",
  "Samstag": "Saturday",
  "Sonntag": "Sunday",
  // Zeit
  "nie gemeldet": "never reported",
  "gerade eben": "just now",
  "vor {n} s": "{n} s ago",
  "vor {n} min": "{n} min ago",
  "vor {n} h": "{n} h ago",
  "vor 1 Tag": "1 day ago",
  "vor {n} Tagen": "{n} days ago",
  // Übersicht
  "kein Empfang bekannt": "no reception known",
  "Hauptmodul": "Main module",
  "Funkmodul": "Radio module",
  "Ohne Bereich": "No area",
  "Anlernen läuft … {n} s": "Pairing … {n} s",
  "Menü": "Menu",
  "Fehler: {error}": "Error: {error}",
  "Lade …": "Loading …",
  "Keine eQ-3-MAX!-Integration eingerichtet.": "No eQ-3 MAX! integration set up.",
  "{title}: Integration nicht geladen (Zustand „{state}“).": "{title}: integration not loaded (state \"{state}\").",
  "Noch keine Geräte angelernt.": "No devices paired yet.",
  "Sendezeit der letzten Stunde (Grenze {limit} s)": "Airtime of the last hour (limit {limit} s)",
  "Sendezeit": "Airtime",
  "1 Gerät · Warteschlange {queue}": "1 device · queue {queue}",
  "{n} Geräte · Warteschlange {queue}": "{n} devices · queue {queue}",
  "verbunden": "connected",
  "nicht alle verbunden": "not all connected",
  "getrennt": "disconnected",
  "Neue Geräte 60 s lang annehmen": "Accept new devices for 60 s",
  "Funkmodul nicht verbunden": "Radio module not connected",
  "Anlernen 60 s geöffnet – jetzt am Gerät die Anlerntaste drücken.": "Pairing open for 60 s – now press the pairing button on the device.",
  "Anlernen (60 s)": "Pair (60 s)",
  "Funkmodul fürs Anlernen": "Radio module for pairing",
  "alle Funkmodule": "all radio modules",
  "Warteschlange {queue}": "Queue {queue}",
  "Die Sendezeit ist aufgebraucht (1-%-Regel); Befehle gehen hinaus, sobald wieder Zeit frei ist.":
    "The airtime is used up (1 % rule); commands go out as soon as time is available again.",
  "wartet auf Sendezeit": "waiting for airtime",
  "Netzwerk": "Network",
  "USB": "USB",
  "Thermostate": "Thermostats",
  "heizt gerade": "heating now",
  "heizen gerade": "heating now",
  "Fenster offen": "Windows open",
  "Batterie schwach": "Battery low",
  "auffällig": "need attention",
  "nicht quittiert": "not acknowledged",
  "Funkfehler": "Radio error",
  "Sollwert": "Target",
  "Ventilöffnung": "Valve opening",
  "unbekannt": "unknown",
  "offen": "open",
  "geschlossen": "closed",
  "Taster für Automatik und Eco": "Button for auto and eco",
  "Batterie": "Battery",
  "schwach": "low",
  "Empfangsstärke": "Signal strength",
  "zuletzt gemeldet": "last reported",
  "Verknüpfungen": "Links",
  // Seitenfenster
  "Konfiguration": "Configuration",
  "Wochenprogramm": "Week program",
  "Zurück": "Back",
  "Zurück zur Übersicht": "Back to overview",
  "Funkmodul {name}": "Radio module {name}",
  "Seriennummer {serial} · Adresse {address}": "Serial number {serial} · address {address}",
  " · Firmware {firmware}": " · firmware {firmware}",
  "Schließen": "Close",
  // Wochenprogramm
  "Punkt {n}: Temperatur muss zwischen 4,5 und 30,5 °C in 0,5-Schritten liegen":
    "Point {n}: temperature must be between 4.5 and 30.5 °C in steps of 0.5",
  "Punkt {n}: Bis-Uhrzeit fehlt (hh:mm)": "Point {n}: until time missing (hh:mm)",
  "Punkt {n}: Bis-Uhrzeit in 5-Minuten-Schritten": "Point {n}: until time in 5-minute steps",
  "Punkt {n}: Bis-Uhrzeiten müssen aufsteigend sein": "Point {n}: until times must be ascending",
  "Punkt {n}: nur der letzte Punkt gilt bis 24:00": "Point {n}: only the last point lasts until 24:00",
  "Wird geschrieben – noch offen: {days}.": "Writing – still to do: {days}.",
  " Das Funkmodul wartet gerade auf Sendezeit (1-%-Regel); je Telegramm kann das zwei Minuten dauern, eine ganze Woche eine Viertelstunde und mehr.":
    " The radio module is waiting for airtime (1 % rule); this can take two minutes per telegram, a whole week a quarter of an hour and more.",
  " Die Seite muss dafür nicht offen bleiben.": " The page does not need to stay open for this.",
  "Letztes Schreiben abgebrochen: ": "Last write aborted: ",
  " Nicht geschrieben: {days}.": " Not written: {days}.",
  "{temperature} °C bis {until}": "{temperature} °C until {until}",
  "wird geschrieben …": "writing …",
  "nicht geschrieben": "not written",
  "In den Editor": "To the editor",
  "keinen": "none",
  "alle": "all",
  "Temperatur Punkt {n}": "Temperature point {n}",
  "bis 24:00": "until 24:00",
  "Bis-Uhrzeit Punkt {n}": "Until time point {n}",
  "bis": "until",
  "Punkt entfernen": "Remove point",
  "Punkt {n} entfernen": "Remove point {n}",
  "Punkt hinzufügen": "Add point",
  "Schreiben": "Write",
  "Wochenprogramm von {name} geschrieben: {days}.": "Week program of {name} written: {days}.",
  "Wochenprogramm von {name} kopiert auf {targets}.": "Week program of {name} copied to {targets}.",
  "wird kopiert …": "copying …",
  "Kopieren": "Copy",
  "Feste Temperatur": "Fixed temperature",
  "Abbrechen": "Cancel",
  "Funkmodul umbenennen": "Rename radio module",
  "Name des Funkmoduls": "Name of the radio module",
  "Speichern": "Save",
  "Funkmodul heißt jetzt „{name}“ – die Integration lädt neu.": "The radio module is now called \"{name}\" – the integration reloads.",
  "Löschen": "Clear",
  "Ein Thermostat hat immer ein Programm. Löschen heißt deshalb: ein neues schreiben, auf alle sieben Tage.":
    "A thermostat always has a program. Clearing therefore means: writing a new one, to all seven days.",
  "Werksprogramm": "Factory program",
  "Mo–Fr 17 °C bis 06:00, 21 °C bis 09:00, 17 °C bis 17:00, 21 °C bis 23:00, 17 °C bis 24:00 · Sa/So 17 °C bis 06:00, 21 °C bis 22:00, 17 °C bis 24:00":
    "Mon–Fri 17 °C until 06:00, 21 °C until 09:00, 17 °C until 17:00, 21 °C until 23:00, 17 °C until 24:00 · Sat/Sun 17 °C until 06:00, 21 °C until 22:00, 17 °C until 24:00",
  "Werksprogramm schreiben": "Write factory program",
  "Werksprogramm auf {name} schreiben? Alle sieben Tage werden überschrieben (sieben Telegramme).":
    "Write the factory program to {name}? All seven days are overwritten (seven telegrams).",
  "Werksprogramm auf {name} geschrieben.": "Factory program written to {name}.",
  "ein Punkt bis 24:00, jeden Tag dieselbe Temperatur": "one point until 24:00, the same temperature every day",
  "Temperatur 4,5 bis 30,5 °C in 0,5-Schritten": "Temperature 4.5 to 30.5 °C in steps of 0.5",
  "Feste Temperatur schreiben": "Write fixed temperature",
  "{temperature} °C den ganzen Tag auf {name} schreiben? Alle sieben Tage werden überschrieben (sieben Telegramme).":
    "Write {temperature} °C all day to {name}? All seven days are overwritten (seven telegrams).",
  "{temperature} °C auf {name} geschrieben.": "{temperature} °C written to {name}.",
  "Das Gerät folgt dem Wochenprogramm im Modus Automatik. Es meldet sein Programm nicht; gezeigt werden die Tage, die es zuletzt quittiert hat.":
    "The device follows the week program in auto mode. It does not report its program; shown are the days it acknowledged last.",
  "Gespeichert": "Stored",
  "Jeder Punkt gilt bis zu seiner Uhrzeit (5-Minuten-Schritte), der letzte bis 24:00. Bis zu 13 Punkte je Tag.":
    "Each point lasts until its time (5-minute steps), the last one until 24:00. Up to 13 points per day.",
  "Je Tag ein bis zwei Telegramme. Geschrieben wird im Hintergrund, auch wenn die Seite geschlossen wird.":
    "One or two telegrams per day. Writing happens in the background, even if the page is closed.",
  "Uhr des Geräts": "Device clock",
  "Uhr stellen": "Set clock",
  "Das Gerät schaltet sein Wochenprogramm nach seiner eigenen Uhr. Gestellt wird sie auf die Zeit von Home Assistant; das Gerät quittiert.":
    "The device switches its week program by its own clock. It is set to the time of Home Assistant; the device acknowledges.",
  "Uhr von {name} gestellt.": "Clock of {name} set.",
  "wird gestellt …": "setting …",
  "Uhr jetzt stellen": "Set clock now",
  "Auf andere Thermostate kopieren": "Copy to other thermostats",
  "Erst ein Programm schreiben, dann lässt es sich kopieren.": "Write a program first, then it can be copied.",
  // Funkmodul
  "Alle Funkmodule nutzen dieselbe Zentralen-Adresse. Das zugeordnete Modul sendet die Befehle an das Gerät, empfangen wird über alle. Umstellen sendet nichts an das Gerät und braucht kein Neuanlernen.":
    "All radio modules use the same central address. The assigned module sends the commands to the device, receiving works through all of them. Switching sends nothing to the device and needs no re-pairing.",
  "nicht gehört": "not heard",
  "bester Empfang": "best reception",
  "zugeordnet": "assigned",
  "Funkmodul ist gerade nicht verbunden": "Radio module is not connected right now",
  "{name} sendet jetzt über {radio}.": "{name} now sends through {radio}.",
  "Zuordnen": "Assign",
  "Empfangswerte stammen aus den letzten Telegrammen des Geräts. Ein Modul, das das Gerät nie gehört hat, erreicht es vermutlich auch beim Senden nicht.":
    "Reception values come from the device's last telegrams. A module that never heard the device probably won't reach it when sending either.",
  // Verknüpfungen
  "Verknüpfung mit {name} beauftragt.": "Link with {name} requested.",
  "Lösen von {name} beauftragt.": "Unlink from {name} requested.",
  "verknüpft": "linked",
  "Lösen": "Unlink",
  "Erneut senden": "Send again",
  "Verknüpfen": "Link",
  "{what}: {text}": "{what}: {text}",
  "Partner auswählen": "Choose partner",
  "Partner auswählen …": "Choose partner …",
  "kein weiteres Gerät möglich": "no further device possible",
  "Keine Verknüpfungen.": "No links.",
  "Mit allen Geräten im Bereich verknüpfen ({n})": "Link with all devices in the area ({n})",
  "Verknüpft dieses Gerät mit allen passenden Geräten, die in Home Assistant im selben Bereich stehen.":
    "Links this device with all suitable devices in the same Home Assistant area.",
  "Diese Verknüpfungen werden beauftragt:": "These links will be requested:",
  "{n} Verknüpfungen beauftragt.": "{n} links requested.",
  "Temperatur für die Komfort-Taste am Gerät und das Preset „Komfort“. Gilt für den ganzen Raum.":
    "Temperature of the comfort button on the device and of the preset \"Comfort\". Applies to the whole room.",
  "Absenktemperatur für die Eco-Taste, den Eco-Taster und das Preset „Eco“. Gilt für den ganzen Raum.":
    "Setback temperature of the eco button, the eco push button and the preset \"Eco\". Applies to the whole room.",
  "Höchster Sollwert, der sich am Gerät einstellen lässt.":
    "Highest target that can be set on the device.",
  "Niedrigster Sollwert, der sich am Gerät einstellen lässt.":
    "Lowest target that can be set on the device.",
  "Korrigiert die gemessene Temperatur, z. B. −1 K, wenn das Thermostat direkt am Heizkörper zu warm misst.":
    "Corrects the measured temperature, e.g. −1 K if the thermostat measures too warm right at the radiator.",
  "Sollwert, solange ein Fenster offen ist – über einen Fensterkontakt oder die eigene Erkennung des Thermostats.":
    "Target while a window is open – from a window contact or the thermostat's own detection.",
  "So lange gilt die Fenster-auf-Temperatur, wenn das Thermostat selbst einen Temperatursturz erkennt. 0 = eigene Erkennung aus (ein Fensterkontakt wirkt weiter).":
    "How long the window-open temperature applies when the thermostat itself detects a temperature drop. 0 = own detection off (a window contact still works).",
  "Wie lange Boost das Ventil weit öffnet. Der Wandthermostat zählt seine Anzeige danach herunter.":
    "How long boost opens the valve wide. The wall thermostat counts its display down by it.",
  "Ventilöffnung während Boost.":
    "Valve opening during boost.",
  "Wochentag der Ventilfahrt gegen Festsitzen (Entkalkung).":
    "Weekday of the valve run against sticking (decalcification).",
  "Uhrzeit der wöchentlichen Ventilfahrt.":
    "Hour of the weekly valve run.",
  "Größte Ventilöffnung – begrenzt die Heizleistung dieses Heizkörpers.":
    "Largest valve opening – limits the heat output of this radiator.",
  "Verschiebt die Ventilstellung, z. B. bei Ventilen, die erst spät öffnen.":
    "Shifts the valve position, e.g. for valves that open late.",
  "Was das Display des Wandthermostats zeigt. Am Gerät ist das Menü gesperrt, solange es an einer Zentrale hängt.":
    "What the wall thermostat's display shows. Its menu is locked while it is paired with a central.",
  "Der Heizkörper meldet seine Ist-Temperatur nur, wenn sich bei ihm etwas ändert. eq3_max stößt ihn in diesem Abstand an (Sollwert +0,5 °C bis zur Meldung, etwa 1 min, dann zurück). Kostet zwei Telegramme und etwas Batterie; ausgelassen, wenn er von selbst gemeldet hat.":
    "The radiator reports its current temperature only when something changes on it. eq3_max nudges it at this interval (target +0.5 °C until it reports, about 1 min, then back). Costs two telegrams and some battery; skipped when it reported by itself.",
  "Ist-Temperatur abfragen": "Poll current temperature",
  "aus": "off", "alle 15 min": "every 15 min", "alle 30 min": "every 30 min", "stündlich": "every hour",
  "alle 2 Stunden": "every 2 hours", "alle 4 Stunden": "every 4 hours",
  "Abfrage: {value}": "Polling: {value}",
  "Erklärung": "Explanation",
  "Gruppen-ID": "Group id",
  "keine": "none",
  "Setzen": "Set",
  "Entfernen": "Remove",
  "Für den Raum vergeben": "Assign for the room",
  "Gruppen-ID {group} gesendet – wartet auf Quittung.": "Group id {group} sent – waiting for acknowledgement.",
  "Gruppen-ID entfernt – wartet auf Quittung.": "Group id removed – waiting for acknowledgement.",
  "Raum bekommt Gruppen-ID {group} ({n} Geräte) – wartet auf Quittung.": "Room gets group id {group} ({n} devices) – waiting for acknowledgement.",
  "Geräte einer Gruppe übernehmen Stellbefehle gemeinsam. „Für den Raum vergeben“ gibt diesem Thermostat und den mit ihm verknüpften Thermostaten eine gemeinsame freie ID (1–255) und entfernt sie bei allen anderen.":
    "Devices of one group take set commands together. \"Assign for the room\" gives this thermostat and the thermostats linked with it one common free id (1–255) and removes it from all others.",
  "Partner hinzufügen": "Add partner",
  "Zur Auswahl stehen nur Geräte, die sich mit diesem verknüpfen lassen und noch nicht verknüpft oder beauftragt sind.":
    "Only devices that can be linked with this one and are not linked or requested yet are offered.",
  // Konfiguration
  "Das Gerät übernimmt nur ganze Sätze: Werte ändern und den Satz mit einem Klick senden. Gezeigt wird der zuletzt quittierte Wert; „ausstehend“ heißt gesendet, aber noch nicht quittiert.":
    "The device only accepts whole sets: change values and send the set with one click. Shown is the last acknowledged value; \"pending\" means sent but not yet acknowledged.",
  "ausstehend: {value}": "pending: {value}",
  "quittiert: {value}": "acknowledged: {value}",
  "{min} … {max}, Schritt {step}": "{min} … {max}, step {step}",
  "Satz ausstehend": "Set pending",
  "nicht quittiert – wird beim nächsten Melden erneut gesendet": "not acknowledged – sent again on the next report",
  "Verwerfen": "Discard",
  "Satz senden": "Send set",
  "Wert muss zwischen {min} und {max} in Schritten von {step} liegen": "Value must be between {min} and {max} in steps of {step}",
  "{n} geändert": "{n} changed",
  "Satz „{title}“ an {name} senden:": "Send set \"{title}\" to {name}:",
  "Mit dem Satz gehen diese angenommenen Werksvorgaben mit (am Gerät nie gelesen):":
    "These assumed factory defaults go along with the set (never read from the device):",
  "Alle übrigen Werte des Satzes sind bekannt.": "All other values of the set are known.",
  "Senden": "Send",
  "Satz „{title}“ gesendet – wartet auf Quittung.": "Set \"{title}\" sent – waiting for acknowledgement.",
  " Werksvorgaben mitgesendet: {labels}.": " Factory defaults sent along: {labels}.",
};

/** Text in der Sprache des Benutzers; {name}-Platzhalter aus params. */
function t(text, params) {
  let out = LANG === "de" ? text : (EN[text] !== undefined ? EN[text] : text);
  if (params) out = out.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));
  return out;
}

function numberLocale() {
  return LANG === "de" ? "de-DE" : "en-US";
}

const AIRTIME_WARN = 0.5;
const AIRTIME_ALARM = 0.8;

const TYPE_ICONS = {
  heating_thermostat: "mdi:radiator",
  wall_thermostat: "mdi:thermostat",
  shutter_contact: "mdi:window-open-variant",
  push_button: "mdi:gesture-tap-button",
  plug_adapter: "mdi:power-socket-de",
  cube: "mdi:cube-outline",
};
const MODE_LABELS = { auto: "Automatik", manual: "Manuell", temporary: "Temporär", boost: "Boost" };
const PRESET_LABELS = { away: "Abwesend", boost: "Boost" };
const HVAC_LABELS = { off: "Aus" };
const TONE_COLORS = {
  heat: "var(--e3-heat)", open: "var(--e3-open)", alert: "var(--e3-error)", off: "var(--e3-muted)", idle: "var(--e3-accent)",
};
const WP_DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];
const SOURCE_LABELS = { homegear: "Homegear", werksvorgabe: "Werksvorgabe", gesetzt: "gesetzt", gemeldet: "gemeldet" };
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
    "Fensterkontakte hören nur kurz nach dem eigenen Senden zu: Änderungen gehen erst raus, wenn das Fenster einmal geöffnet und geschlossen wird.",
  push_button:
    "Eco-Taster hören nur kurz nach dem eigenen Senden zu: Änderungen gehen erst raus, wenn der Taster einmal gedrückt wird (oder die Anlerntaste).",
};
// Anzeigenamen nach Schlüssel (der Server schickt sie auch, aber nur auf Deutsch).
const TYPE_NAMES = {
  cube: "Cube",
  heating_thermostat: "Heizkörperthermostat",
  heating_thermostat_plus: "Heizkörperthermostat+",
  wall_thermostat: "Wandthermostat",
  shutter_contact: "Fensterkontakt",
  push_button: "Eco-Taster",
  plug_adapter: "Zwischenstecker (noch nicht unterstützt)",
};
const SET_TITLES = { temp: "Temperaturen", valve: "Ventil", display: "Anzeige" };
const CONFIG_LABELS = {
  komfort: "Komforttemperatur",
  eco: "Eco-Temperatur",
  maximal: "Maximaltemperatur",
  minimal: "Minimaltemperatur",
  offset: "Temperatur-Offset",
  fenster_temperatur: "Fenster-auf-Temperatur",
  fenster_dauer: "Fenster-auf-Dauer",
  boost_dauer: "Boost-Dauer",
  boost_ventil: "Boost-Ventilstellung",
  entkalkung_tag: "Entkalkung Tag",
  entkalkung_stunde: "Entkalkung Stunde",
  ventil_max: "Ventil maximal",
  ventil_offset: "Ventil-Offset",
  anzeige: "Anzeige",
};
// Optionsschlüssel der Anzeige (Wandthermostat) -> deutscher Text (Anzeige über t()).
const DISPLAY_KEYS = { setpoint: "Soll-Temperatur", actual: "Ist-Temperatur" };
// Erklärtexte je Einstellwert (Mouseover und ⓘ).
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
const POLL_LABELS = { 0: "aus", 15: "alle 15 min", 30: "alle 30 min", 60: "stündlich", 120: "alle 2 Stunden", 240: "alle 4 Stunden" };
// Optionsschlüssel von entkalkung_tag -> deutscher Wochentag (Anzeige über t()).
const DAY_KEYS = {
  monday: "Montag", tuesday: "Dienstag", wednesday: "Mittwoch", thursday: "Donnerstag",
  friday: "Freitag", saturday: "Samstag", sunday: "Sonntag",
};
const MAIN_RADIO_NAME = "Hauptmodul";

const STYLE = `
  :host {
    display: block;
    min-height: 100vh;
    background: var(--primary-background-color, #f5f6f8);
    color: var(--primary-text-color, #1c2430);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
    --e3-gap: 16px;
    --e3-radius: var(--ha-card-border-radius, 14px);
    --e3-card: var(--card-background-color, #fff);
    --e3-divider: var(--divider-color, rgba(0, 0, 0, 0.12));
    --e3-muted: var(--secondary-text-color, #6b7380);
    --e3-ok: var(--success-color, #43a047);
    --e3-warn: var(--warning-color, #ffa600);
    --e3-error: var(--error-color, #db4437);
    --e3-accent: var(--primary-color, #03a9f4);
    --e3-heat: var(--state-climate-heat-color, #ff8100);
    --e3-open: var(--warning-color, #ff9800);
    --e3-shadow: var(--ha-card-box-shadow, 0 1px 2px rgba(0, 0, 0, .08), 0 2px 8px rgba(0, 0, 0, .05));
  }
  * { box-sizing: border-box; }
  ha-icon { --mdc-icon-size: 20px; display: inline-flex; }
  .toolbar {
    display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 16px;
    background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, #fff);
    font-size: 20px; position: sticky; top: 0; z-index: 2;
  }
  .menu-btn { background: none; border: 0; color: inherit; cursor: pointer; padding: 8px; font-size: 22px; }
  main { padding: 20px var(--e3-gap) 32px; max-width: 1400px; margin: 0 auto; }
  section.entry { margin-bottom: 40px; }

  /* --- Kopf: Funkmodule und Kennzahlen --- */
  .hub {
    background: var(--e3-card); border-radius: var(--e3-radius); padding: 16px 18px;
    box-shadow: var(--e3-shadow); display: flex; flex-direction: column; gap: 14px;
  }
  .hub-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .hub-head .title { font-weight: 600; font-size: 17px; }
  .hub-head .sub { color: var(--e3-muted); font-size: 13px; }
  .pill {
    display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 3px 10px;
    font-size: 13px; font-weight: 500;
    background: color-mix(in srgb, var(--e3-ok) 14%, transparent); color: var(--e3-ok);
  }
  .pill.bad { background: color-mix(in srgb, var(--e3-error) 14%, transparent); color: var(--e3-error); }
  .pill .dot { width: 8px; height: 8px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--e3-error); flex: none; }
  .dot.ok { background: var(--e3-ok); }
  .spacer { flex: 1; }
  .radios { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
  .radio {
    border: 1px solid var(--e3-divider); border-radius: 12px; padding: 10px 12px;
    display: flex; flex-direction: column; gap: 8px; min-width: 0;
  }
  .radio .top { display: flex; align-items: center; gap: 8px; }
  .radio .name { font-weight: 600; flex: 1; }
  .radio .conn { display: flex; align-items: center; gap: 6px; color: var(--e3-muted); font-size: 12.5px; min-width: 0; }
  .radio .conn span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .radio .conn ha-icon { --mdc-icon-size: 16px; }
  .air { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--e3-muted); }
  .air .meter { flex: 1; }
  .meter { width: 120px; height: 6px; border-radius: 3px; background: var(--e3-divider); overflow: hidden; }
  .meter > span { display: block; height: 100%; border-radius: 3px; background: var(--e3-accent); transition: width .3s; }
  .wp-note { margin: 8px 0; padding: 8px 10px; border-radius: 8px; font-size: 13px; background: color-mix(in srgb, var(--e3-accent) 12%, transparent); }
  .wp-note.bad { background: color-mix(in srgb, var(--e3-error) 12%, transparent); color: var(--e3-error); }
  .meter.warn > span { background: var(--e3-warn); }
  .meter.alarm > span { background: var(--e3-error); }
  .stats { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(165px, 1fr)); }
  .stat {
    border-radius: 12px; padding: 10px 12px; display: flex; align-items: center; gap: 10px;
    background: color-mix(in srgb, var(--e3-divider) 45%, transparent);
  }
  .stat .ic { width: 34px; height: 34px; }
  .stat .v { font-size: 20px; font-weight: 600; line-height: 1.1; }
  .stat .l { font-size: 12px; color: var(--e3-muted); white-space: nowrap; }
  .stat.heat { background: color-mix(in srgb, var(--e3-heat) 12%, transparent); }
  .stat.open { background: color-mix(in srgb, var(--e3-open) 14%, transparent); }
  .stat.alert { background: color-mix(in srgb, var(--e3-error) 12%, transparent); }

  button.action {
    border: 1px solid var(--e3-accent); color: var(--e3-accent); background: transparent;
    border-radius: 999px; padding: 7px 16px; cursor: pointer; font: inherit; font-size: 14px; font-weight: 500;
    transition: background .15s, box-shadow .15s;
  }
  button.action:hover:not(:disabled) { background: color-mix(in srgb, var(--e3-accent) 10%, transparent); }
  button.action.primary { background: var(--e3-accent); color: var(--text-primary-color, #fff); border-color: var(--e3-accent); }
  button.action.primary:hover:not(:disabled) { box-shadow: 0 2px 8px color-mix(in srgb, var(--e3-accent) 40%, transparent); background: var(--e3-accent); }
  button.action.danger { border-color: var(--e3-error); color: var(--e3-error); }
  button.action:disabled { opacity: 0.45; cursor: default; }

  /* --- Bereiche und Karten --- */
  h2.area {
    display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; letter-spacing: .02em;
    color: var(--e3-muted); margin: 28px 2px 10px; text-transform: uppercase;
  }
  h2.area .count {
    font-size: 11px; font-weight: 600; border-radius: 999px; padding: 1px 7px;
    background: color-mix(in srgb, var(--e3-divider) 70%, transparent); color: var(--e3-muted);
  }
  h2.area::after { content: ""; flex: 1; height: 1px; background: var(--e3-divider); margin-left: 4px; }
  .grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); }
  .card {
    --tone: var(--e3-muted);
    position: relative; overflow: hidden;
    background: var(--e3-card); border-radius: var(--e3-radius); padding: 14px 16px 12px; cursor: pointer;
    box-shadow: var(--e3-shadow); border: 1px solid transparent;
    display: flex; flex-direction: column; gap: 10px; text-align: left; color: inherit; font: inherit;
    transition: transform .15s, box-shadow .15s, border-color .15s;
  }
  .card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: transparent; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0, 0, 0, .12); }
  .card:focus-visible { border-color: var(--e3-accent); outline: none; }
  .card.tone-idle { --tone: var(--e3-accent); }
  .card.tone-heat { --tone: var(--e3-heat); }
  .card.tone-open { --tone: var(--e3-open); }
  .card.tone-alert { --tone: var(--e3-error); }
  .card.tone-heat::before, .card.tone-open::before, .card.tone-alert::before { background: var(--tone); }
  .ic {
    width: 38px; height: 38px; border-radius: 50%; flex: none; display: inline-flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--tone, var(--e3-muted)) 14%, transparent); color: var(--tone, var(--e3-muted));
  }
  .card .head { display: flex; align-items: center; gap: 10px; }
  .card .who { flex: 1; min-width: 0; }
  .card .name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .card .kind { color: var(--e3-muted); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .card .badges { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }
  .temps { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
  .temps .cur { font-size: 30px; font-weight: 400; letter-spacing: -.02em; line-height: 1; }
  .temps .cur small { font-size: 15px; color: var(--e3-muted); margin-left: 2px; }
  .target {
    display: inline-flex; align-items: center; gap: 4px; border-radius: 999px; padding: 3px 10px; font-size: 13px; font-weight: 500;
    background: color-mix(in srgb, var(--tone) 14%, transparent); color: var(--primary-text-color);
  }
  .target ha-icon { --mdc-icon-size: 15px; color: var(--tone); }
  .valve { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--e3-muted); }
  .valve .meter { flex: 1; width: auto; height: 6px; }
  .valve .meter > span { background: var(--tone); }
  .card.tone-idle .valve .meter > span, .card:not([class*="tone-"]) .valve .meter > span { background: var(--e3-muted); }
  .wstate { display: flex; align-items: center; gap: 8px; font-size: 22px; font-weight: 500; }
  .wstate.open { color: var(--e3-open); }
  .card .foot {
    display: flex; flex-wrap: wrap; gap: 4px 14px; color: var(--e3-muted); font-size: 12px; align-items: center;
    border-top: 1px solid var(--e3-divider); padding-top: 9px; margin-top: auto;
  }
  .card .foot > span { display: inline-flex; align-items: center; gap: 4px; }
  .card .foot ha-icon { --mdc-icon-size: 14px; }
  .card .foot .low { color: var(--e3-error); }
  .info-btn { border: 0; background: none; color: var(--e3-muted); cursor: pointer; padding: 0 0 0 4px; vertical-align: middle; display: inline-flex; }
  .info-btn ha-icon { --mdc-icon-size: 15px; }
  .help { grid-column: 1 / -1; font-size: 12.5px; color: var(--e3-muted); background: color-mix(in srgb, var(--e3-accent) 8%, transparent);
    border-radius: 8px; padding: 6px 10px; margin: 2px 0 4px; }
  .chip {
    display: inline-block; border-radius: 999px; padding: 1px 8px; font-size: 11.5px; font-weight: 500; white-space: nowrap;
    background: var(--e3-divider); color: var(--primary-text-color);
  }
  .chip.ok { background: color-mix(in srgb, var(--e3-ok) 16%, transparent); color: var(--e3-ok); }
  .chip.warn { background: color-mix(in srgb, var(--e3-warn) 22%, transparent); color: color-mix(in srgb, var(--e3-warn) 55%, var(--primary-text-color)); }
  .chip.error { background: color-mix(in srgb, var(--e3-error) 15%, transparent); color: var(--e3-error); }
  .chip.info { background: color-mix(in srgb, var(--e3-accent) 15%, transparent); color: var(--e3-accent); }
  .bars { display: inline-flex; align-items: flex-end; gap: 1px; height: 12px; }
  .bars span { width: 3px; border-radius: 1px; background: var(--e3-divider); }
  .bars span.on { background: var(--e3-muted); }
  .empty { color: var(--e3-muted); padding: 16px 4px; }
  .notice {
    background: color-mix(in srgb, var(--e3-warn) 10%, var(--e3-card)); border-left: 4px solid var(--e3-warn);
    padding: 10px 14px; border-radius: 8px; font-size: 14px; line-height: 1.45;
  }

  /* --- Seitenfenster --- */
  .overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: 5; animation: fade .15s; }
  .drawer {
    position: fixed; top: 0; right: 0; bottom: 0; width: min(540px, 100%); z-index: 6;
    background: var(--e3-card); display: flex; flex-direction: column;
    box-shadow: -4px 0 24px rgba(0, 0, 0, 0.25); animation: slide .2s ease-out;
  }
  @keyframes slide { from { transform: translateX(24px); opacity: .6; } to { transform: none; opacity: 1; } }
  @keyframes fade { from { opacity: 0; } to { opacity: 1; } }
  .drawer header { padding: 18px 18px 14px; display: flex; gap: 14px; align-items: flex-start; }
  .drawer header .ic { width: 46px; height: 46px; }
  .drawer header .ic ha-icon { --mdc-icon-size: 24px; }
  .drawer header .t { flex: 1; min-width: 0; }
  .drawer header .t .n { font-size: 19px; font-weight: 600; }
  .drawer header .t .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .drawer header .t .meta { color: var(--e3-muted); font-size: 12px; margin-top: 8px; }
  .close {
    background: none; border: 0; font-size: 18px; cursor: pointer; color: var(--e3-muted);
    width: 34px; height: 34px; border-radius: 50%;
  }
  .close:hover { background: color-mix(in srgb, var(--e3-divider) 60%, transparent); color: var(--primary-text-color); }
  /* Zurück-Knopf des Seitenfensters: nur auf schmalen Bildschirmen (siehe @media unten). */
  .back { display: none; }
  .radio .rename {
    background: none; border: 0; cursor: pointer; color: var(--e3-muted); flex: none;
    width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
  }
  .radio .rename ha-icon { --mdc-icon-size: 18px; }
  .radio .rename:hover:not(:disabled) { background: color-mix(in srgb, var(--e3-divider) 60%, transparent); color: var(--primary-text-color); }
  .radio .rename:disabled { opacity: 0.45; cursor: default; }
  .radio .rename-input {
    flex: 1; min-width: 0; font: inherit; font-weight: 600; padding: 4px 8px; border-radius: 8px;
    border: 1px solid var(--e3-accent); background: var(--e3-card); color: var(--primary-text-color);
  }
  .pair-radio {
    font: inherit; font-size: 14px; padding: 6px 8px; border-radius: 8px; max-width: 12em;
    border: 1px solid var(--e3-divider); background: var(--e3-card); color: var(--primary-text-color);
  }
  .tabs {
    display: flex; gap: 4px; margin: 0 18px 4px; padding: 4px; border-radius: 12px;
    background: color-mix(in srgb, var(--e3-divider) 45%, transparent);
  }
  .tabs button {
    flex: 1; background: none; border: 0; padding: 8px 10px; cursor: pointer; border-radius: 9px;
    color: var(--e3-muted); font: inherit; font-size: 14px; font-weight: 500; transition: background .15s, color .15s;
  }
  .tabs button.active { background: var(--e3-card); color: var(--primary-text-color); box-shadow: 0 1px 3px rgba(0, 0, 0, .12); }
  .body { overflow-y: auto; padding: 14px 18px 18px; flex: 1; display: flex; flex-direction: column; gap: 16px; }
  .row { display: flex; align-items: center; gap: 8px; padding: 10px 4px; border-bottom: 1px solid var(--e3-divider); flex-wrap: wrap; }
  .row:last-child { border-bottom: 0; }
  .row .grow { flex: 1; min-width: 120px; font-weight: 500; }
  .row .hint { flex-basis: 100%; color: var(--e3-muted); font-size: 12px; }
  .add { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  select, input {
    font: inherit; padding: 7px 10px; border-radius: 8px; border: 1px solid var(--e3-divider);
    background: var(--e3-card); color: var(--primary-text-color);
  }
  select:focus, input:focus { outline: 2px solid color-mix(in srgb, var(--e3-accent) 45%, transparent); outline-offset: 0; }
  input:invalid { border-color: var(--e3-error); }
  input.changed, select.changed { border-color: var(--e3-accent); border-width: 2px; }
  fieldset { border: 1px solid var(--e3-divider); border-radius: 12px; padding: 8px 14px 14px; margin: 0; }
  legend { padding: 0 6px; font-weight: 600; }
  .cfg { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--e3-divider); }
  .cfg .label { font-size: 14px; }
  .cfg .meta { grid-column: 1 / -1; display: flex; gap: 6px; flex-wrap: wrap; font-size: 12px; color: var(--e3-muted); align-items: center; }
  .cfg .ctl { display: flex; align-items: center; gap: 6px; }
  .cfg input { width: 96px; text-align: right; }
  .sub { color: var(--e3-muted); font-size: 13px; }
  .setfoot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; align-items: center; flex-wrap: wrap; }
  .confirm { border: 1px solid var(--e3-warn); border-radius: 10px; padding: 10px 12px; margin-top: 12px; font-size: 14px; }
  .confirm ul { margin: 6px 0; padding-left: 20px; }
  .wp-day { display: flex; gap: 10px; align-items: center; padding: 7px 0; border-bottom: 1px solid var(--e3-divider); font-size: 14px; }
  .wp-day .wp-name { width: 92px; font-weight: 500; }
  .wp-days { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; padding: 4px 0; }
  .wp-check { display: inline-flex; align-items: center; gap: 4px; font-size: 14px; cursor: pointer; }
  .wp-point { display: flex; gap: 10px; align-items: center; padding: 5px 0; border-bottom: 1px solid var(--e3-divider); flex-wrap: wrap; }
  .wp-point .ctl { display: flex; align-items: center; gap: 6px; }
  .wp-point input[type=number] { width: 80px; text-align: right; }
  .wp-point input[type=text] { width: 68px; text-align: center; }
  .toast {
    position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); z-index: 10; max-width: 90%;
    background: var(--e3-card); color: var(--primary-text-color); border-radius: 10px; padding: 10px 16px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.3); border-left: 4px solid var(--e3-ok); animation: fade .15s;
  }
  .toast.error { border-left-color: var(--e3-error); }
  @media (max-width: 600px) {
    /* The drawer fills the screen: no overlay to tap, no Escape key. Keep the way back
       reachable: below the status bar, with a large back button on the left. */
    .drawer {
      padding-top: var(--safe-area-inset-top, env(safe-area-inset-top, 0px));
      padding-bottom: var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px));
    }
    .drawer header { padding: 12px 12px 10px; gap: 10px; align-items: center; }
    .drawer header .ic { display: none; }
    .back {
      display: inline-flex; align-items: center; justify-content: center; flex: none;
      width: 44px; height: 44px; border-radius: 50%; border: 0; cursor: pointer;
      background: color-mix(in srgb, var(--e3-divider) 55%, transparent); color: var(--primary-text-color);
    }
    .back ha-icon { --mdc-icon-size: 24px; }
    .close { width: 44px; height: 44px; font-size: 20px; flex: none; }
    /* Reiter: nicht stauchen, sondern seitlich schieben. */
    .tabs {
      margin: 0 12px 4px; flex: none; overflow-x: auto; overscroll-behavior-x: contain;
      scrollbar-width: none; -webkit-overflow-scrolling: touch;
    }
    .tabs::-webkit-scrollbar { display: none; }
    .tabs button { flex: 1 0 auto; white-space: nowrap; padding: 10px 14px; }
    .body { padding: 12px 12px 18px; overscroll-behavior: contain; }
    main { padding: 12px 8px 24px; }
    .grid { grid-template-columns: 1fr; }
    .hub { padding: 14px; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
  @media (prefers-reduced-motion: reduce) {
    .card, .drawer, .overlay, .toast, .meter > span { transition: none; animation: none; }
    .card:hover { transform: none; }
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
  return Number(value).toLocaleString(numberLocale(), { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function plainNum(value) {
  return Number(value).toLocaleString(numberLocale(), { maximumFractionDigits: 2 });
}

function ago(ts) {
  if (!ts) return t("nie gemeldet");
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 10) return t("gerade eben");
  if (s < 60) return t("vor {n} s", { n: s });
  if (s < 3600) return t("vor {n} min", { n: Math.floor(s / 60) });
  if (s < 86400) return t("vor {n} h", { n: Math.floor(s / 3600) });
  const d = Math.floor(s / 86400);
  return d === 1 ? t("vor 1 Tag") : t("vor {n} Tagen", { n: d });
}

function rssiBars(rssi) {
  const level = rssi === null || rssi === undefined ? 0 : rssi >= -60 ? 4 : rssi >= -70 ? 3 : rssi >= -80 ? 2 : rssi >= -90 ? 1 : 0;
  return h("span", { class: "bars", title: rssi === null || rssi === undefined ? t("kein Empfang bekannt") : `${num(rssi)} dBm` },
    [1, 2, 3, 4].map((i) => h("span", { class: i <= level ? "on" : "", style: `height:${i * 3}px` })));
}

function isMulti(entry) {
  return !!(entry && entry.hub && entry.hub.radios && entry.hub.radios.length > 1);
}

/** Name eines Funkmoduls zur Anzeige: nur der unveränderte Name des Hauptmoduls wird übersetzt. */
function radioLabel(radio) {
  return radio.name === MAIN_RADIO_NAME ? t(MAIN_RADIO_NAME) : radio.name;
}

function radioName(entry, id) {
  const radio = entry.hub.radios.find((r) => r.id === id);
  return radioLabel(radio || entry.hub.radios[0]);
}

/** Wochentag zur Anzeige; der Wert selbst (deutscher Name) geht unverändert an den Server. */
function dayLabel(day) {
  return t(day);
}

function daysLabel(days) {
  return days.map(dayLabel).join(", ");
}

/** Gerätetyp nach Schlüssel; der deutsche type_name des Servers wird nicht angezeigt. */
function typeName(dev) {
  const base = TYPE_NAMES[dev.type];
  if (!base) return t("Unbekannt");
  // Der Server fasst Thermostat und Thermostat+ unter einem Schlüssel zusammen; das „+“
  // steht nur im Namen.
  if (dev.type === "heating_thermostat" && typeof dev.type_name === "string" && dev.type_name.endsWith("+")) {
    return t(TYPE_NAMES.heating_thermostat_plus);
  }
  return t(base);
}

function setTitle(set) {
  return SET_TITLES[set.kind] ? t(SET_TITLES[set.kind]) : set.title;
}

function configLabel(item) {
  return CONFIG_LABELS[item.key] ? t(CONFIG_LABELS[item.key]) : item.label;
}

function optionLabel(item, opt) {
  if (item.key === "entkalkung_tag" && DAY_KEYS[opt.label]) return t(DAY_KEYS[opt.label]);
  if (item.key === "anzeige" && DISPLAY_KEYS[opt.label]) return t(DISPLAY_KEYS[opt.label]);
  return opt.label;
}

/** Zustand für Farbe und Akzent der Karte: heat · open · alert · off · idle. */
function cardTone(dev) {
  const st = dev.state;
  if (st.rf_error || st.command_failed || st.config_failed.length || st.battery_low) return "alert";
  if (dev.type === "shutter_contact") return st.window_open ? "open" : "idle";
  if (st.hvac === "off") return "off";
  if (dev.type === "heating_thermostat" && st.valve > 0) return "heat";
  return "idle";
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
  if (value === null || value === undefined) return "–";
  if (item.type === "select") {
    const opt = item.options.find((o) => sameValue(o.value, value));
    return opt ? optionLabel(item, opt) : String(value);
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
    this._pairRadio = {}; // entry_id -> Funkmodul fürs Anlernen ("*" = alle)
    this._renaming = null; // {entry_id, radio, value}: Funkmodul, dessen Name gerade bearbeitet wird
    this._pairingUntil = {}; // entry_id -> ms
    this._toast = null;
    this._narrow = false;
    this._wpDrafts = {}; // serial -> {days, points, targets}
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const language = (hass && ((hass.locale && hass.locale.language) || hass.language)) || "";
    const lang = String(language).toLowerCase().startsWith("de") ? "de" : "en";
    const langChanged = lang !== LANG;
    LANG = lang;
    if (langChanged || this._exceptionsLang !== language) {
      // Fehlertexte des Servers für die neue Sprache neu laden.
      this._exceptionsLang = language;
      this._exceptionsPromise = null;
      this._exceptionsReady = false;
      this._localize = null;
    }
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
    if (first && this.isConnected) this._start();
    if (langChanged && this.isConnected) this._requestRender();
  }

  // --- Fehlertexte des Servers (translation_key -> Text in der Benutzersprache) ---

  _loadExceptions() {
    const hass = this._hass;
    if (!this._exceptionsPromise) {
      const load = hass && typeof hass.loadBackendTranslation === "function"
        ? Promise.resolve().then(() => hass.loadBackendTranslation("exceptions", "eq3_max"))
        : Promise.resolve(null);
      const promise = load
        .then((localize) => {
          if (promise !== this._exceptionsPromise) return;
          if (typeof localize === "function") this._localize = localize;
        })
        .catch(() => {})
        .then(() => {
          if (promise === this._exceptionsPromise) this._exceptionsReady = true;
        });
      this._exceptionsPromise = promise;
    }
    return this._exceptionsPromise;
  }

  /** Übersetzter Fehlertext oder "" (noch nicht geladen, unbekannt, kein localize). */
  _localizeException(key, placeholders) {
    if (!key || !this._exceptionsReady) return "";
    const params = { ...(placeholders || {}) };
    // Wochentag: eigener Platzhalter je Sprache, die Seite nimmt den der Benutzersprache.
    if (params.day_de || params.day_en) {
      params.day = LANG === "de" ? (params.day_de || params.day_en) : (params.day_en || params.day_de);
    }
    const id = `component.eq3_max.exceptions.${key}.message`;
    for (const fn of [this._hass && this._hass.localize, this._localize]) {
      if (typeof fn !== "function") continue;
      try {
        const text = fn(id, params);
        if (text) return text;
      } catch (_err) { /* nächste Quelle */ }
    }
    return "";
  }

  /** Fehler einer WebSocket-Antwort als Text in der Benutzersprache. */
  async _errorText(err) {
    const fallback = (err && err.message) || String(err);
    const key = err && err.translation_key;
    if (!key || (err.translation_domain && err.translation_domain !== "eq3_max")) return fallback;
    await this._loadExceptions();
    return this._localizeException(key, err.translation_placeholders) || fallback;
  }

  /** Dasselbe beim Rendern (synchron): solange die Texte laden, erst der Ersatztext. */
  _exceptionText(key, placeholders, fallback) {
    if (!key) return fallback;
    if (!this._exceptionsReady) {
      const promise = this._loadExceptions();
      if (!this._exceptionsWaiting) {
        this._exceptionsWaiting = true;
        promise.then(() => {
          this._exceptionsWaiting = false;
          this._requestRender();
        });
      }
      return fallback;
    }
    return this._localizeException(key, placeholders) || fallback;
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
    if (this._onPopState) window.removeEventListener("popstate", this._onPopState);
    this._onPopState = null;
    this._backEntry = false;
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
      this._error = await this._errorText(err);
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
      error = await this._errorText(err);
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
      this._showToast(await this._errorText(err), true);
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
    return !!(el && (el.tagName === "INPUT" || el.tagName === "SELECT") && el.closest(".drawer, .radio"));
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
      if (el) el.textContent = t("Anlernen läuft … {n} s", { n: left });
    }
    if (ended) this._requestRender();
  }

  /** Auswahl des Moduls fürs Anlernen; während des Anlernens das gewählte anzeigen. */
  _pairRadioSelect(entry, locked) {
    const hub = entry.hub;
    if (hub.pairing_remaining > 0) {
      this._pairRadio[entry.entry_id] = hub.pairing_radio === null || hub.pairing_radio === undefined ? "*" : hub.pairing_radio;
    }
    const current = this._pairRadio[entry.entry_id] || "*";
    const select = h("select", {
      class: "pair-radio", "aria-label": t("Funkmodul fürs Anlernen"), title: t("Funkmodul fürs Anlernen"),
      disabled: locked, "data-focus": `pairradio:${entry.entry_id}`,
    },
    h("option", { value: "*" }, t("alle Funkmodule")),
    hub.radios.map((radio) => h("option", { value: radio.id }, radioLabel(radio))));
    select.value = current;
    select.addEventListener("change", () => { this._pairRadio[entry.entry_id] = select.value; this._render(); });
    return select;
  }

  /** Name der Modul-Kachel mit Stift; im Bearbeiten Eingabefeld, Speichern, Abbrechen. */
  _radioName(entry, radio) {
    const editing = this._renaming && this._renaming.entry_id === entry.entry_id && this._renaming.radio === radio.id;
    const busyKey = `rename:${entry.entry_id}:${radio.id}`;
    if (!editing) {
      return [
        h("span", { class: "name" }, radioLabel(radio)),
        h("button", {
          class: "rename", title: t("Funkmodul umbenennen"), "aria-label": t("Funkmodul umbenennen"),
          disabled: this._busy.has(busyKey),
          onclick: () => {
            this._renaming = { entry_id: entry.entry_id, radio: radio.id, value: radioLabel(radio) };
            this._render();
            const input = this.shadowRoot.querySelector(".rename-input");
            if (input) { input.focus(); input.select(); }
          },
        }, icon("mdi:pencil")),
      ];
    }
    const cancel = () => { this._renaming = null; this._render(); };
    const save = async () => {
      const name = (this._renaming.value || "").trim();
      if (name === radioLabel(radio)) { cancel(); return; }
      this._renaming = null;
      await this._call(busyKey, { type: "eq3_max/rename_radio", entry_id: entry.entry_id, radio: radio.id, name },
        t("Funkmodul heißt jetzt „{name}“ – die Integration lädt neu.", { name }));
    };
    const input = h("input", {
      class: "rename-input", type: "text", maxlength: "40", value: this._renaming.value,
      "aria-label": t("Name des Funkmoduls"), "data-focus": `rename:${entry.entry_id}:${radio.id}`,
    });
    input.value = this._renaming.value;
    input.addEventListener("input", () => { if (this._renaming) this._renaming.value = input.value; });
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); save(); }
      if (ev.key === "Escape") { ev.preventDefault(); cancel(); }
    });
    return [
      input,
      h("button", { class: "rename", title: t("Speichern"), "aria-label": t("Speichern"), onclick: save }, icon("mdi:check")),
      h("button", { class: "rename", title: t("Abbrechen"), "aria-label": t("Abbrechen"), onclick: cancel }, icon("mdi:close")),
    ];
  }

  _pairRadioConnected(entry) {
    const choice = this._pairRadio[entry.entry_id] || "*";
    if (choice === "*") return entry.hub.any_connected;
    const radio = entry.hub.radios.find((r) => r.id === choice);
    return !!(radio && radio.connected);
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
    const caret = active && active.tagName === "INPUT" && typeof active.selectionStart === "number"
      ? [active.selectionStart, active.selectionEnd] : null;
    const scroll = root.querySelector(".body");
    const tabChanged = this._renderedTab !== this._tab;
    const scrollTop = scroll && !tabChanged ? scroll.scrollTop : 0;
    const tabBar = root.querySelector(".tabs");
    const tabScroll = tabBar ? tabBar.scrollLeft : 0;

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
    // The tab bar scrolls sideways on narrow screens: keep its position, and bring a
    // newly chosen tab into view.
    const newTabBar = root.querySelector(".tabs");
    if (newTabBar) {
      newTabBar.scrollLeft = tabScroll;
      const activeTab = newTabBar.querySelector("button.active");
      if (tabChanged && activeTab && typeof activeTab.scrollIntoView === "function") {
        activeTab.scrollIntoView({ block: "nearest", inline: "center" });
      }
    }
    this._renderedTab = this._selected ? this._tab : null;
    if (focusKey) {
      const el = root.querySelector(`[data-focus="${CSS.escape(focusKey)}"]`);
      if (el) {
        el.focus();
        if (caret && typeof el.setSelectionRange === "function") {
          try { el.setSelectionRange(caret[0], caret[1]); } catch (_err) { /* not a text field */ }
        }
      }
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
        title: t("Menü"),
        "aria-label": t("Menü"),
        onclick: () => this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })),
      }, "☰");
    }
    return h("div", { class: "toolbar" }, menu, h("span", {}, "eQ-3 MAX!"));
  }

  _renderMain() {
    if (this._error && !this._data) return h("div", { class: "notice" }, t("Fehler: {error}", { error: this._error }));
    if (!this._data) return h("div", { class: "empty" }, t("Lade …"));
    if (!this._data.entries.length) return h("div", { class: "empty" }, t("Keine eQ-3-MAX!-Integration eingerichtet."));
    return this._data.entries.map((entry) => this._renderEntry(entry));
  }

  _renderEntry(entry) {
    if (!entry.loaded) {
      return h("section", { class: "entry" },
        h("div", { class: "notice" }, t("{title}: Integration nicht geladen (Zustand „{state}“).", { title: entry.title, state: entry.state })));
    }
    const groups = new Map();
    for (const dev of entry.devices) {
      const key = dev.area_id || "";
      if (!groups.has(key)) groups.set(key, { name: dev.area_name || t("Ohne Bereich"), devices: [] });
      groups.get(key).devices.push(dev);
    }
    const ordered = [...groups.entries()].sort(([ka, a], [kb, b]) => {
      if (!ka) return 1;
      if (!kb) return -1;
      return a.name.localeCompare(b.name, LANG);
    });
    return h("section", { class: "entry" },
      this._renderHub(entry),
      entry.devices.length ? null : h("div", { class: "empty" }, t("Noch keine Geräte angelernt.")),
      ordered.map(([, group]) => [
        h("h2", { class: "area" }, group.name, h("span", { class: "count" }, String(group.devices.length))),
        h("div", { class: "grid" }, group.devices.map((dev) => this._renderCard(entry, dev))),
      ]),
    );
  }

  _airtime(airtime, limit) {
    const ratio = Math.min(1, airtime / limit);
    const meterClass = ratio >= AIRTIME_ALARM ? "alarm" : ratio >= AIRTIME_WARN ? "warn" : "";
    return h("div", { class: "air", title: t("Sendezeit der letzten Stunde (Grenze {limit} s)", { limit }) },
      t("Sendezeit"), h("span", { class: `meter ${meterClass}` }, h("span", { style: `width:${ratio * 100}%` })),
      `${num(airtime)} / ${limit} s`);
  }

  _renderHub(entry) {
    const hub = entry.hub;
    const multi = isMulti(entry);
    const left = Math.max(0, Math.round(((this._pairingUntil[entry.entry_id] || 0) - Date.now()) / 1000));
    const busy = this._busy.has(`pair:${entry.entry_id}`);
    const radios = hub.radios && hub.radios.length ? hub.radios : [{ ...hub, name: t("Funkmodul"), id: "" }];
    const n = entry.devices.length;
    return h("div", { class: "hub" },
      h("div", { class: "hub-head" },
        h("div", {},
          h("div", { class: "title" }, entry.title),
          h("div", { class: "sub" }, n === 1
            ? t("1 Gerät · Warteschlange {queue}", { queue: hub.queue })
            : t("{n} Geräte · Warteschlange {queue}", { n, queue: hub.queue }))),
        h("span", { class: `pill ${hub.connected ? "" : "bad"}` }, h("span", { class: `dot ${hub.connected ? "ok" : ""}` }),
          hub.connected ? t("verbunden") : multi ? t("nicht alle verbunden") : t("getrennt")),
        h("span", { class: "spacer" }),
        // Mehrere Module: wählen, welches das neue Gerät annimmt (und dem es zugeordnet wird).
        multi ? this._pairRadioSelect(entry, left > 0 || busy) : null,
        h("button", {
          class: "action primary",
          "data-pairing": entry.entry_id,
          disabled: left > 0 || busy || !this._pairRadioConnected(entry),
          title: this._pairRadioConnected(entry) ? t("Neue Geräte 60 s lang annehmen") : t("Funkmodul nicht verbunden"),
          onclick: () => {
            const choice = this._pairRadio[entry.entry_id] || "*";
            const message = { type: "eq3_max/pair", entry_id: entry.entry_id };
            if (multi && choice !== "*") message.radio = choice;
            this._call(`pair:${entry.entry_id}`, message, t("Anlernen 60 s geöffnet – jetzt am Gerät die Anlerntaste drücken."));
          },
        }, left > 0 ? t("Anlernen läuft … {n} s", { n: left }) : t("Anlernen (60 s)"))),
      h("div", { class: "radios" }, radios.map((radio) => h("div", { class: "radio" },
        h("div", { class: "top" },
          h("span", { class: `dot ${radio.connected ? "ok" : ""}`, title: radio.connected ? t("verbunden") : t("getrennt") }),
          this._radioName(entry, radio),
          multi ? h("span", { class: "sub" }, t("Warteschlange {queue}", { queue: radio.queue })) : null,
          radio.waiting_budget
            ? h("span", { class: "pill bad", title: t("Die Sendezeit ist aufgebraucht (1-%-Regel); Befehle gehen hinaus, sobald wieder Zeit frei ist.") }, t("wartet auf Sendezeit"))
            : null),
        h("div", { class: "conn", title: radio.version || "" },
          icon(radio.connection === "network" ? "mdi:lan" : "mdi:usb"),
          h("span", {}, `${radio.connection === "network" ? t("Netzwerk") : t("USB")} · ${radio.target}`)),
        this._airtime(radio.airtime, hub.airtime_limit)))),
      this._renderStats(entry),
    );
  }

  _renderStats(entry) {
    const devs = entry.devices;
    const climates = devs.filter((d) => d.type === "heating_thermostat" || d.type === "wall_thermostat").length;
    const heating = devs.filter((d) => cardTone(d) === "heat").length;
    const open = devs.filter((d) => d.type === "shutter_contact" && d.state.window_open).length;
    const battery = devs.filter((d) => d.state.battery_low).length;
    const attention = devs.filter((d) => d.pending || d.state.command_failed || d.state.config_failed.length || d.state.rf_error).length;
    const tile = (cls, tone, ic, value, label) => h("div", { class: `stat ${value ? cls : ""}` },
      h("span", { class: "ic", style: value && tone ? `--tone:${tone}` : "" }, icon(ic)),
      h("div", {}, h("div", { class: "v" }, String(value)), h("div", { class: "l" }, label)));
    return h("div", { class: "stats" },
      tile("", "", "mdi:thermostat", climates, t("Thermostate")),
      tile("heat", "var(--e3-heat)", "mdi:fire", heating, heating === 1 ? t("heizt gerade") : t("heizen gerade")),
      tile("open", "var(--e3-open)", "mdi:window-open-variant", open, t("Fenster offen")),
      tile("alert", "var(--e3-error)", "mdi:battery-alert-variant-outline", battery, t("Batterie schwach")),
      tile("alert", "var(--e3-error)", "mdi:clock-alert-outline", attention, t("auffällig")));
  }

  _renderCard(entry, dev) {
    const st = dev.state;
    const tone = cardTone(dev);
    const badges = [];
    if (dev.pending) badges.push(chip(t("ausstehend"), "warn"));
    if (st.command_failed || st.config_failed.length) badges.push(chip(t("nicht quittiert"), "error"));
    if (st.rf_error) badges.push(chip(t("Funkfehler"), "error"));

    let kind = typeName(dev);
    let body;
    if (dev.type === "heating_thermostat" || dev.type === "wall_thermostat") {
      const label = st.hvac === "off" ? HVAC_LABELS.off : PRESET_LABELS[st.preset] || MODE_LABELS[st.mode];
      kind = label ? t(label) : typeName(dev);
      body = [
        h("div", { class: "temps" },
          h("span", { class: "cur" }, num(st.measured), h("small", {}, "°C")),
          h("span", { class: "target", title: t("Sollwert") }, icon("mdi:target"), `${num(st.target)} °C`)),
        dev.type === "heating_thermostat"
          ? h("div", { class: "valve", title: t("Ventilöffnung") }, t("Ventil"),
            h("span", { class: "meter" }, h("span", { style: `width:${st.valve || 0}%` })),
            st.valve === null ? "–" : `${st.valve} %`)
          : null,
      ];
    } else if (dev.type === "shutter_contact") {
      const isOpen = st.window_open;
      body = h("div", { class: `wstate ${isOpen ? "open" : ""}` },
        icon(isOpen ? "mdi:window-open-variant" : "mdi:window-closed-variant"),
        isOpen === null ? t("unbekannt") : isOpen ? t("offen") : t("geschlossen"));
    } else {
      body = h("div", { class: "sub" }, t("Taster für Automatik und Eco"));
    }
    const linkCount = dev.links.partners.length;
    const open = () => this._open(entry.entry_id, dev.serial);
    return h("div", {
      class: `card tone-${tone}`,
      "data-serial": dev.serial,
      tabindex: "0",
      role: "button",
      onclick: open,
      onkeydown: (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } },
    },
      h("div", { class: "head" },
        h("span", { class: "ic" }, icon(TYPE_ICONS[dev.type] || "mdi:help")),
        h("div", { class: "who" }, h("div", { class: "name", title: dev.name }, dev.name), h("div", { class: "kind" }, kind)),
        badges.length ? h("div", { class: "badges" }, badges) : null),
      body,
      h("div", { class: "foot" },
        h("span", { class: st.battery_low ? "low" : "", title: t("Batterie") },
          icon(st.battery_low ? "mdi:battery-alert-variant-outline" : "mdi:battery-high"),
          st.battery_low ? t("schwach") : st.battery_low === false ? "ok" : "?"),
        h("span", { title: t("Empfangsstärke") }, rssiBars(st.rssi), st.rssi === null ? "– dBm" : `${num(st.rssi, 0)} dBm`),
        h("span", { title: t("zuletzt gemeldet") }, icon("mdi:clock-outline"), h("span", { "data-ago": st.last_seen || 0 }, ago(st.last_seen))),
        h("span", { title: t("Verknüpfungen") }, icon("mdi:link-variant"), String(linkCount)),
        isMulti(entry) ? h("span", { title: t("Funkmodul") }, icon("mdi:radio-tower"), radioName(entry, dev.radio)) : null,
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
    this._pushBackEntry();
    const target = this.shadowRoot.querySelector(".drawer .close");
    if (target) target.focus();
  }

  // The phone's back gesture closes the drawer instead of leaving the page: opening adds
  // a history entry of our own (same address), going back removes it and closes.
  _pushBackEntry() {
    if (this._backEntry) return;
    try {
      window.history.pushState({ eq3MaxDrawer: true }, "");
      this._backEntry = true;
    } catch (err) {
      this._backEntry = false;
      return;
    }
    if (!this._onPopState) {
      this._onPopState = () => {
        // Our entry is gone (back was used): close without touching the history again.
        if (this._backEntry && !(window.history.state && window.history.state.eq3MaxDrawer)) {
          this._backEntry = false;
          if (this._selected) this._close();
        }
      };
      window.addEventListener("popstate", this._onPopState);
    }
  }

  _dropBackEntry() {
    if (!this._backEntry) return;
    this._backEntry = false;
    try {
      if (window.history.state && window.history.state.eq3MaxDrawer) window.history.back();
    } catch (err) { /* nothing to undo */ }
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
    this._dropBackEntry();
    this._render();
    // Back to the card the drawer was opened from.
    const card = serial && this.shadowRoot.querySelector(`.card[data-serial="${CSS.escape(serial)}"]`);
    if (card) card.focus();
  }

  // Swipe left/right inside the drawer changes the tab (touch screens).
  _swipeStart(ev) {
    this._swipe = null;
    if (!ev.touches || ev.touches.length !== 1) return;
    const touch = ev.touches[0];
    const target = ev.target;
    // Not from the screen edge (the system's own back gesture), not while typing or
    // dragging something that scrolls sideways itself.
    if (touch.clientX < 24 || touch.clientX > window.innerWidth - 24) return;
    if (target && target.closest && target.closest("input, select, textarea, .wp-days")) return;
    this._swipe = { x: touch.clientX, y: touch.clientY, t: Date.now() };
  }

  _swipeEnd(ev) {
    const start = this._swipe;
    this._swipe = null;
    if (!start || !ev.changedTouches || !ev.changedTouches.length) return;
    const touch = ev.changedTouches[0];
    const dx = touch.clientX - start.x;
    const dy = touch.clientY - start.y;
    if (Date.now() - start.t > 700 || Math.abs(dx) < 70 || Math.abs(dx) < 2.5 * Math.abs(dy)) return;
    const keys = this._tabKeys || [];
    const index = keys.indexOf(this._tab);
    const next = index + (dx < 0 ? 1 : -1);
    if (index < 0 || next < 0 || next >= keys.length) return;
    this._tab = keys[next];
    this._confirm = null;
    this._render();
  }

  _renderDrawer() {
    if (!this._selected) return null;
    const dev = this._device(this._selected.entryId, this._selected.serial);
    if (!dev) {
      this._selected = null;
      this._removeEscape();
      this._dropBackEntry();
      return null;
    }
    const entry = this._data.entries.find((e) => e.entry_id === this._selected.entryId);
    const available = [["links", t("Verknüpfungen")]];
    if (dev.config.length > 0) available.push(["config", t("Konfiguration")]);
    if (dev.type === "heating_thermostat" || dev.type === "wall_thermostat") available.push(["week", t("Wochenprogramm")]);
    if (isMulti(entry)) available.push(["radio", t("Funkmodul")]);
    if (!available.some(([key]) => key === this._tab)) this._tab = "links";
    this._tabKeys = available.map(([key]) => key);
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
        h("header", { class: `tone-${cardTone(dev)}` },
          h("button", { class: "back", title: t("Zurück"), "aria-label": t("Zurück zur Übersicht"), onclick: () => this._close() },
            icon("mdi:arrow-left")),
          h("span", { class: "ic", style: `--tone:${TONE_COLORS[cardTone(dev)]}` }, icon(TYPE_ICONS[dev.type] || "mdi:help")),
          h("div", { class: "t" },
            h("div", { class: "n" }, dev.name),
            h("div", { class: "tags" }, chip(typeName(dev)), chip(dev.area_name || t("Ohne Bereich")),
              isMulti(entry) ? chip(t("Funkmodul {name}", { name: radioName(entry, dev.radio) }), "info") : null),
            h("div", { class: "meta" }, t("Seriennummer {serial} · Adresse {address}", { serial: dev.serial, address: dev.address })
              + (dev.firmware ? t(" · Firmware {firmware}", { firmware: dev.firmware }) : ""))),
          h("button", { class: "close", title: t("Schließen"), "aria-label": t("Schließen"), onclick: () => this._close() }, "✕")),
        tabs,
        h("div", { class: "body", ontouchstart: (ev) => this._swipeStart(ev), ontouchend: (ev) => this._swipeEnd(ev) },
          this._tab === "config" ? this._renderConfig(dev)
            : this._tab === "week" ? this._renderWeekProfile(entry, dev)
              : this._tab === "radio" ? this._renderRadio(entry, dev)
              : this._renderLinks(dev)),
      ),
    ];
  }

  // --- Wochenprogramm ---

  /** Grund des abgebrochenen Schreibens: {message, key, placeholders, missing} oder (alt) ein Text. */
  _weekProfileError(error) {
    if (typeof error === "string") return error;
    const text = this._exceptionText(error.key, error.placeholders, error.message || "");
    const missing = Array.isArray(error.missing) && error.missing.length
      ? t(" Nicht geschrieben: {days}.", { days: daysLabel(error.missing) })
      : "";
    return text + missing;
  }

  _wpDraft(dev) {
    if (!this._wpDrafts[dev.serial]) {
      this._wpDrafts[dev.serial] = {
        days: new Set(),
        points: [{ temperature: "17", until: "06:00" }, { temperature: "21", until: "22:00" }, { temperature: "17", until: "" }],
        targets: new Set(),
      };
    }
    return this._wpDrafts[dev.serial];
  }

  _wpValidate(points) {
    let last = -1;
    for (let i = 0; i < points.length; i++) {
      const t = Number(String(points[i].temperature).replace(",", "."));
      if (!Number.isFinite(t) || t < 4.5 || t > 30.5 || Math.round(t * 2) !== t * 2) {
        return t("Punkt {n}: Temperatur muss zwischen 4,5 und 30,5 °C in 0,5-Schritten liegen", { n: i + 1 });
      }
      if (i === points.length - 1) break;
      const m = /^(\d{1,2}):?(\d{2})$/.exec(String(points[i].until || "").trim());
      if (!m) return t("Punkt {n}: Bis-Uhrzeit fehlt (hh:mm)", { n: i + 1 });
      const minutes = Number(m[1]) * 60 + Number(m[2]);
      if (minutes % 5) return t("Punkt {n}: Bis-Uhrzeit in 5-Minuten-Schritten", { n: i + 1 });
      if (minutes <= last) return t("Punkt {n}: Bis-Uhrzeiten müssen aufsteigend sein", { n: i + 1 });
      if (minutes >= 24 * 60) return t("Punkt {n}: nur der letzte Punkt gilt bis 24:00", { n: i + 1 });
      last = minutes;
    }
    return null;
  }

  _renderWeekProfile(entry, dev) {
    const draft = this._wpDraft(dev);
    const key = `wp:${dev.serial}`;
    // A write belongs to the integration and outlives this page: its state comes from the device.
    const writing = dev.week_profile_writing || [];
    const busy = this._busy.has(key) || this._busy.has(`${key}:copy`) || writing.length > 0;
    const radio = entry.hub.radios.find((r) => r.id === (dev.radio || "")) || entry.hub.radios[0];
    const waitingBudget = !!(radio && radio.waiting_budget);
    const progress = writing.length
      ? h("div", { class: "wp-note" },
        h("b", {}, t("Wird geschrieben – noch offen: {days}.", { days: daysLabel(writing) })),
        waitingBudget
          ? t(" Das Funkmodul wartet gerade auf Sendezeit (1-%-Regel); je Telegramm kann das zwei Minuten dauern, eine ganze Woche eine Viertelstunde und mehr.")
          : "",
        t(" Die Seite muss dafür nicht offen bleiben."))
      : null;
    const failure = !writing.length && dev.week_profile_error
      ? h("div", { class: "wp-note bad" }, h("b", {}, t("Letztes Schreiben abgebrochen: ")), this._weekProfileError(dev.week_profile_error))
      : null;
    if (draft.constant === undefined) draft.constant = "17";
    const stored = dev.week_profile || {};
    const fmt = (p) => t("{temperature} °C bis {until}", { temperature: plainNum(p.temperature), until: p.until });

    // Stored days (what the device acknowledged last).
    const storedRows = WP_DAYS.map((day) => h("div", { class: "wp-day" },
      h("span", { class: "wp-name" }, dayLabel(day)),
      writing.includes(day) ? h("span", { class: "sub" }, t("wird geschrieben …")) : null,
      stored[day]
        ? h("span", { class: "grow" }, stored[day].map(fmt).join(" · "))
        : h("span", { class: "grow sub" }, t("nicht geschrieben")),
      stored[day]
        ? h("button", {
          class: "action", disabled: busy,
          onclick: () => {
            draft.points = stored[day].map((p, i) => ({
              temperature: plainNum(p.temperature), until: i === stored[day].length - 1 ? "" : p.until,
            }));
            draft.days = new Set([day]);
            this._render();
          },
        }, t("In den Editor"))
        : null));

    // Editor.
    const dayBoxes = WP_DAYS.map((day) => {
      const box = h("input", { type: "checkbox", "data-focus": `${key}:d:${day}` });
      box.checked = draft.days.has(day);
      box.addEventListener("change", () => { box.checked ? draft.days.add(day) : draft.days.delete(day); update(); });
      return h("label", { class: "wp-check" }, box, dayLabel(day).slice(0, 2));
    });
    const allButton = h("button", {
      class: "action", type: "button",
      onclick: () => { draft.days = draft.days.size === WP_DAYS.length ? new Set() : new Set(WP_DAYS); this._render(); },
    }, draft.days.size === WP_DAYS.length ? t("keinen") : t("alle"));

    const pointRows = draft.points.map((point, i) => {
      const lastPoint = i === draft.points.length - 1;
      const temp = h("input", {
        type: "number", min: "4.5", max: "30.5", step: "0.5", inputmode: "decimal",
        "data-focus": `${key}:t:${i}`, "aria-label": t("Temperatur Punkt {n}", { n: i + 1 }),
      });
      temp.value = String(point.temperature);
      temp.addEventListener("input", () => { point.temperature = temp.value; update(); });
      let until;
      if (lastPoint) {
        until = h("span", { class: "sub" }, t("bis 24:00"));
      } else {
        // Textfeld statt type=time: ein Zeitwähler verliert eine halb eingegebene Zeit, wenn
        // die Seite wegen eines Telegramms neu aufgebaut wird; der Entwurf hält jeden Tastendruck.
        until = h("input", {
          type: "text", placeholder: "hh:mm", maxlength: "5", autocomplete: "off",
          "data-focus": `${key}:u:${i}`, "aria-label": t("Bis-Uhrzeit Punkt {n}", { n: i + 1 }),
        });
        until.value = point.until || "";
        until.addEventListener("input", (ev) => {
          // Der Doppelpunkt kommt von selbst: "06" -> "06:", "0600" -> "06:00" (nicht beim Löschen).
          let value = until.value.replace(/[^\d:]/g, "");
          const deleting = typeof ev.inputType === "string" && ev.inputType.startsWith("delete");
          if (!deleting) {
            if (/^\d{2}$/.test(value)) value += ":";
            else if (/^\d{3,4}$/.test(value)) value = `${value.slice(0, 2)}:${value.slice(2)}`;
          }
          if (value !== until.value) until.value = value;
          point.until = value;
          update();
        });
      }
      return h("div", { class: "wp-point" },
        h("span", { class: "sub" }, `${i + 1}.`),
        h("span", { class: "ctl" }, temp, h("span", { class: "sub" }, "°C")),
        h("span", { class: "ctl" }, lastPoint ? null : h("span", { class: "sub" }, t("bis")), until),
        draft.points.length > 1
          ? h("button", {
            class: "close", title: t("Punkt entfernen"), "aria-label": t("Punkt {n} entfernen", { n: i + 1 }),
            onclick: () => { draft.points.splice(i, 1); draft.points[draft.points.length - 1].until = ""; this._render(); },
          }, "✕")
          : null);
    });
    const addPoint = h("button", {
      class: "action", type: "button", disabled: draft.points.length >= 13,
      onclick: () => {
        const last = draft.points[draft.points.length - 1];
        draft.points.splice(draft.points.length - 1, 0, { temperature: last.temperature, until: "" });
        this._render();
      },
    }, t("Punkt hinzufügen"));

    const error = h("div", { style: "color:var(--e3-error);font-size:13px;min-height:18px" });
    const write = h("button", { class: "action primary" }, busy ? t("wird geschrieben …") : t("Schreiben"));
    write.addEventListener("click", async () => {
      const weekday = WP_DAYS.filter((d) => draft.days.has(d));
      const profile = draft.points.map((p, i) => {
        const item = { temperature: Number(String(p.temperature).replace(",", ".")) };
        if (i < draft.points.length - 1) {
          const m = /^(\d{1,2}):?(\d{2})$/.exec(String(p.until).trim());
          item.until = `${m[1].padStart(2, "0")}:${m[2]}`;
        }
        return item;
      });
      const result = await this._call(key, { type: "eq3_max/set_week_profile", device_id: dev.device_id, weekday, profile },
        t("Wochenprogramm von {name} geschrieben: {days}.", { name: dev.name, days: daysLabel(weekday) }));
      if (result !== undefined) this._render();
    });
    const update = () => {
      const problem = this._wpValidate(draft.points);
      error.textContent = problem || "";
      write.disabled = busy || !dev.device_id || !!problem || draft.days.size === 0;
    };
    update();

    // Copy to other thermostats of the same radio module.
    const others = entry.devices.filter((d) => d.serial !== dev.serial && (d.type === "heating_thermostat" || d.type === "wall_thermostat"));
    const hasStored = Object.keys(stored).length > 0;
    const targetBoxes = others.map((d) => {
      const box = h("input", { type: "checkbox", "data-focus": `${key}:c:${d.serial}` });
      box.checked = draft.targets.has(d.serial);
      box.addEventListener("change", () => { box.checked ? draft.targets.add(d.serial) : draft.targets.delete(d.serial); copyButton.disabled = busy || !draft.targets.size; });
      return h("label", { class: "wp-check" }, box, d.name);
    });
    const copyButton = h("button", {
      class: "action", disabled: busy || !draft.targets.size,
      onclick: async () => {
        const targets = others.filter((d) => draft.targets.has(d.serial));
        const result = await this._call(`${key}:copy`,
          { type: "eq3_max/copy_week_profile", device_id: dev.device_id, target_device_id: targets.map((d) => d.device_id) },
          t("Wochenprogramm von {name} kopiert auf {targets}.", { name: dev.name, targets: targets.map((d) => d.name).join(", ") }));
        if (result !== undefined) { draft.targets = new Set(); this._render(); }
      },
    }, busy ? t("wird kopiert …") : t("Kopieren"));

    // Löschen = ein bestimmtes Programm schreiben: das Werksprogramm oder eine feste Temperatur.
    const factory = this._data.factory_week_profile || {};
    const writeDays = async (groups, done) => {
      // One request for all days: nothing is left to send from this page afterwards.
      const days = {};
      for (const [weekday, profile] of groups) for (const day of weekday) days[day] = profile;
      const result = await this._call(key, { type: "eq3_max/set_week_profile", device_id: dev.device_id, days }, null);
      if (result === undefined) return;
      this._showToast(done);
      this._render();
    };
    const factoryKey = `${key}:factory`;
    const constKey = `${key}:const`;
    const constTemp = h("input", { type: "number", min: "4.5", max: "30.5", step: "0.5", inputmode: "decimal", "data-focus": constKey, "aria-label": t("Feste Temperatur") });
    constTemp.value = draft.constant || "17";
    constTemp.addEventListener("input", () => { draft.constant = constTemp.value; });
    const constValue = () => Number(String(constTemp.value).replace(",", "."));
    const constOk = () => Number.isFinite(constValue()) && constValue() >= 4.5 && constValue() <= 30.5 && Math.round(constValue() * 2) === constValue() * 2;
    const confirmBox = (text, onYes) => h("div", { class: "confirm" },
      h("div", {}, text),
      h("div", { class: "setfoot" },
        h("button", { class: "action", onclick: () => { this._confirm = null; this._render(); } }, t("Abbrechen")),
        h("button", { class: "action danger", disabled: busy, onclick: () => { this._confirm = null; onYes(); } }, t("Schreiben"))));
    const groupsFactory = () => {
      const byProfile = new Map();
      for (const day of WP_DAYS) {
        const sig = JSON.stringify(factory[day] || []);
        if (!byProfile.has(sig)) byProfile.set(sig, { days: [], profile: factory[day] });
        byProfile.get(sig).days.push(day);
      }
      return [...byProfile.values()].map((g) => [g.days, g.profile.map((p, i) => (i === g.profile.length - 1 ? { temperature: p.temperature } : p))]);
    };
    const erase = h("fieldset", {},
      h("legend", {}, t("Löschen")),
      h("div", { class: "sub", style: "margin-bottom:6px" },
        t("Ein Thermostat hat immer ein Programm. Löschen heißt deshalb: ein neues schreiben, auf alle sieben Tage.")),
      h("div", { class: "row" },
        h("span", { class: "grow" }, t("Werksprogramm"), h("span", { class: "hint" },
          t("Mo–Fr 17 °C bis 06:00, 21 °C bis 09:00, 17 °C bis 17:00, 21 °C bis 23:00, 17 °C bis 24:00 · Sa/So 17 °C bis 06:00, 21 °C bis 22:00, 17 °C bis 24:00"))),
        h("button", { class: "action", disabled: busy || !dev.device_id || !Object.keys(factory).length,
          onclick: () => { this._confirm = factoryKey; this._render(); } }, t("Werksprogramm schreiben"))),
      this._confirm === factoryKey
        ? confirmBox(t("Werksprogramm auf {name} schreiben? Alle sieben Tage werden überschrieben (sieben Telegramme).", { name: dev.name }),
          () => writeDays(groupsFactory(), t("Werksprogramm auf {name} geschrieben.", { name: dev.name })))
        : null,
      h("div", { class: "row" },
        h("span", { class: "grow" }, t("Feste Temperatur"), h("span", { class: "hint" }, t("ein Punkt bis 24:00, jeden Tag dieselbe Temperatur"))),
        h("span", { class: "ctl" }, constTemp, h("span", { class: "sub" }, "°C")),
        h("button", { class: "action", disabled: busy || !dev.device_id,
          onclick: () => { if (!constOk()) { this._showToast(t("Temperatur 4,5 bis 30,5 °C in 0,5-Schritten"), true); return; } this._confirm = constKey; this._render(); } },
          t("Feste Temperatur schreiben"))),
      this._confirm === constKey
        ? confirmBox(t("{temperature} °C den ganzen Tag auf {name} schreiben? Alle sieben Tage werden überschrieben (sieben Telegramme).",
          { temperature: plainNum(constValue()), name: dev.name }),
          () => writeDays([[WP_DAYS, [{ temperature: constValue() }]]],
            t("{temperature} °C auf {name} geschrieben.", { temperature: plainNum(constValue()), name: dev.name })))
        : null);

    return [
      h("div", { class: "sub", style: "color:var(--e3-muted);font-size:13px" },
        t("Das Gerät folgt dem Wochenprogramm im Modus Automatik. Es meldet sein Programm nicht; gezeigt werden die Tage, die es zuletzt quittiert hat.")),
      progress,
      failure,
      h("fieldset", {}, h("legend", {}, t("Gespeichert")), storedRows),
      h("fieldset", {},
        h("legend", {}, t("Schreiben")),
        h("div", { class: "wp-days" }, dayBoxes, allButton),
        h("div", { class: "sub", style: "margin:6px 0" }, t("Jeder Punkt gilt bis zu seiner Uhrzeit (5-Minuten-Schritte), der letzte bis 24:00. Bis zu 13 Punkte je Tag.")),
        pointRows,
        h("div", { class: "add", style: "margin-top:6px" }, addPoint),
        error,
        h("div", { class: "setfoot" },
          h("span", { class: "sub" }, t("Je Tag ein bis zwei Telegramme. Geschrieben wird im Hintergrund, auch wenn die Seite geschlossen wird.")),
          write)),
      erase,
      h("fieldset", {},
        h("legend", {}, t("Uhr des Geräts")),
        h("div", { class: "row" },
          h("span", { class: "grow" }, t("Uhr stellen"), h("span", { class: "hint" },
            t("Das Gerät schaltet sein Wochenprogramm nach seiner eigenen Uhr. Gestellt wird sie auf die Zeit von Home Assistant; das Gerät quittiert."))),
          h("button", {
            class: "action", disabled: this._busy.has(`time:${dev.serial}`) || !dev.device_id,
            onclick: () => this._call(`time:${dev.serial}`, { type: "eq3_max/set_time", device_id: dev.device_id },
              t("Uhr von {name} gestellt.", { name: dev.name })),
          }, this._busy.has(`time:${dev.serial}`) ? t("wird gestellt …") : t("Uhr jetzt stellen")))),
      others.length
        ? h("fieldset", {},
          h("legend", {}, t("Auf andere Thermostate kopieren")),
          hasStored
            ? [h("div", { class: "wp-days" }, targetBoxes), h("div", { class: "setfoot" }, copyButton)]
            : h("div", { class: "empty" }, t("Erst ein Programm schreiben, dann lässt es sich kopieren.")))
        : null,
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
        t("Alle Funkmodule nutzen dieselbe Zentralen-Adresse. Das zugeordnete Modul sendet die Befehle an das Gerät, empfangen wird über alle. Umstellen sendet nichts an das Gerät und braucht kein Neuanlernen.")),
      h("div", {}, entry.hub.radios.map((radio) => h("div", { class: "row" },
        h("span", { class: "grow" }, h("span", { class: `dot ${radio.connected ? "ok" : ""}`, style: "display:inline-block;margin-right:8px" }), radioLabel(radio)),
        rssiBars(rssi[radio.id]),
        h("span", {}, rssi[radio.id] === undefined ? t("nicht gehört") : `${num(rssi[radio.id])} dBm`),
        radio.id === best && heard.length > 1 ? chip(t("bester Empfang"), "ok") : null,
        dev.radio === radio.id
          ? chip(t("zugeordnet"), "ok")
          : h("button", {
            class: "action",
            disabled: busy || !dev.device_id,
            title: radio.connected ? "" : t("Funkmodul ist gerade nicht verbunden"),
            onclick: () => this._call(`radio:${dev.serial}`,
              { type: "eq3_max/set_radio", device_id: dev.device_id, radio: radio.id },
              t("{name} sendet jetzt über {radio}.", { name: dev.name, radio: radioLabel(radio) })),
          }, t("Zuordnen")),
        h("span", { class: "hint" }, `${radio.connection === "network" ? t("Netzwerk") : t("USB")} · ${radio.target}`)))),
      h("div", { class: "sub", style: "margin-top:6px;color:var(--e3-muted);font-size:12px" },
        t("Empfangswerte stammen aus den letzten Telegrammen des Geräts. Ein Modul, das das Gerät nie gehört hat, erreicht es vermutlich auch beim Senden nicht.")),
    ];
  }

  // --- Verknüpfungen ---

  _linkCall(op, dev, partner) {
    const key = `${op}:${dev.serial}:${partner.serial}`;
    const text = op === "link"
      ? t("Verknüpfung mit {name} beauftragt.", { name: partner.name })
      : t("Lösen von {name} beauftragt.", { name: partner.name });
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
        chip(t("verknüpft"), "ok"),
        this._linkButton("unlink", dev, partner, t("Lösen"), true)));
    }
    for (const item of dev.links.pending) {
      const buttons = [];
      if (item.state === "failed" || item.state === "rejected") {
        buttons.push(this._linkButton(item.op === "remove" ? "unlink" : "link", dev, item, t("Erneut senden")));
      }
      if (item.state === "one_sided") buttons.push(this._linkButton("link", dev, item, t("Verknüpfen")));
      if (item.op !== "remove") buttons.push(this._linkButton("unlink", dev, item, t("Lösen"), true));
      const what = item.op === "remove" ? t("Lösen") : item.op === "add" ? t("Verknüpfen") : null;
      // item.text kommt vom Server auf Deutsch; die bekannten Texte stehen in EN.
      const text = item.text ? t(item.text) : "";
      rows.push(h("div", { class: "row" },
        h("span", { class: "grow" }, item.name),
        chip(LINK_LABELS[item.state] ? t(LINK_LABELS[item.state]) : item.state, LINK_CHIP[item.state] || ""),
        buttons,
        h("span", { class: "hint" }, what ? t("{what}: {text}", { what, text }) : text)));
    }

    const select = h("select", { "data-focus": `cand:${dev.serial}`, "aria-label": t("Partner auswählen") },
      h("option", { value: "" }, dev.candidates.length ? t("Partner auswählen …") : t("kein weiteres Gerät möglich")),
      dev.candidates.map((c) => h("option", { value: c.serial }, c.area ? `${c.name} · ${c.area}` : c.name)));
    if (this._candidate && dev.candidates.some((c) => c.serial === this._candidate)) select.value = this._candidate;
    select.addEventListener("change", () => { this._candidate = select.value; this._render(); });
    const chosen = dev.candidates.find((c) => c.serial === select.value);

    return [
      dev.sleeper && SLEEPER_HINTS[dev.type] ? h("div", { class: "notice" }, t(SLEEPER_HINTS[dev.type])) : null,
      h("div", {},
        rows.length ? rows : h("div", { class: "empty" }, t("Keine Verknüpfungen."))),
      h("div", {},
        h("div", { class: "sub", style: "margin-bottom:6px;font-weight:500" }, t("Partner hinzufügen")),
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
          }, t("Verknüpfen"))),
        h("div", { class: "sub", style: "margin-top:6px;color:var(--e3-muted);font-size:12px" },
          t("Zur Auswahl stehen nur Geräte, die sich mit diesem verknüpfen lassen und noch nicht verknüpft oder beauftragt sind.")),
        this._renderAreaLink(dev)),
      dev.config && dev.config.length ? this._renderGroup(dev) : null,
    ];
  }

  _renderAreaLink(dev) {
    const partners = dev.area_candidates || [];
    if (!partners.length) return null;
    const key = `arealink:${dev.serial}`;
    const confirm = this._areaConfirm === dev.serial;
    const busy = this._busy.has(key) || !dev.device_id;
    const run = async () => {
      this._areaConfirm = null;
      for (const partner of partners) {
        await this._call(key, { type: "eq3_max/link", device_id: dev.device_id, partner_device_id: partner.device_id });
      }
      this._showToast(t("{n} Verknüpfungen beauftragt.", { n: partners.length }));
    };
    return h("div", { style: "margin-top:10px" },
      h("button", {
        class: "action", disabled: busy, title: t("Verknüpft dieses Gerät mit allen passenden Geräten, die in Home Assistant im selben Bereich stehen."),
        onclick: () => { this._areaConfirm = confirm ? null : dev.serial; this._render(); },
      }, icon("mdi:link-plus"), " ", t("Mit allen Geräten im Bereich verknüpfen ({n})", { n: partners.length })),
      confirm ? h("div", { class: "confirm" },
        h("div", {}, t("Diese Verknüpfungen werden beauftragt:")),
        h("ul", {}, partners.map((p) => h("li", {}, `${dev.name} ↔ ${p.name}`))),
        h("div", { class: "setfoot" },
          h("button", { class: "action", onclick: () => { this._areaConfirm = null; this._render(); } }, t("Abbrechen")),
          h("button", { class: "action primary", disabled: busy, onclick: run }, t("Verknüpfen")))) : null);
  }

  _renderGroup(dev) {
    const key = `group:${dev.serial}`;
    const busy = this._busy.has(key) || !dev.device_id;
    const input = h("input", {
      type: "number", min: "1", max: "255", step: "1", inputmode: "numeric",
      "data-focus": `group:${dev.serial}`, "aria-label": t("Gruppen-ID"), style: "width:80px",
    });
    input.value = String(dev.pending_group ?? (dev.group || ""));
    const status = [chip(dev.group ? String(dev.group) : t("keine"), dev.group ? "ok" : "")];
    if (dev.pending_group !== null && dev.pending_group !== undefined) {
      status.push(chip(t("ausstehend: {value}", { value: dev.pending_group || t("keine") }), "warn"));
    }
    if (dev.group_failed) status.push(chip(t("nicht quittiert – wird beim nächsten Melden erneut gesendet"), "error"));
    const send = (message, text) => this._call(key, { type: "eq3_max/set_group", device_id: dev.device_id, ...message }, text);
    return h("div", {},
      h("div", { class: "sub", style: "margin:12px 0 6px;font-weight:500" }, t("Gruppen-ID")),
      h("div", { class: "add" },
        status,
        input,
        h("button", {
          class: "action primary", disabled: busy,
          onclick: () => {
            const group = Number(input.value);
            if (!Number.isInteger(group) || group < 1 || group > 255) return;
            send({ group }, t("Gruppen-ID {group} gesendet – wartet auf Quittung.", { group }));
          },
        }, t("Setzen")),
        h("button", {
          class: "action danger", disabled: busy || (!dev.group && !dev.pending_group),
          onclick: () => send({ group: 0 }, t("Gruppen-ID entfernt – wartet auf Quittung.")),
        }, t("Entfernen")),
        h("button", {
          class: "action", disabled: busy,
          onclick: () => send({ room: true }, (res) =>
            t("Raum bekommt Gruppen-ID {group} ({n} Geräte) – wartet auf Quittung.", { group: res.group, n: res.devices.length })),
        }, t("Für den Raum vergeben"))),
      h("div", { class: "sub", style: "margin-top:6px;color:var(--e3-muted);font-size:12px" },
        t("Geräte einer Gruppe übernehmen Stellbefehle gemeinsam. „Für den Raum vergeben“ gibt diesem Thermostat und den mit ihm verknüpften Thermostaten eine gemeinsame freie ID (1–255) und entfernt sie bei allen anderen.")));
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
        t("Das Gerät übernimmt nur ganze Sätze: Werte ändern und den Satz mit einem Klick senden. Gezeigt wird der zuletzt quittierte Wert; „ausstehend“ heißt gesendet, aber noch nicht quittiert.")),
      dev.config.map((set) => this._renderSet(dev, set)),
      dev.poll_minutes === null || dev.poll_minutes === undefined ? null : this._renderPoll(dev),
    ];
  }

  _helpToggle(scope, key) {
    if (!CONFIG_HELP[key]) return null;
    const id = `${scope}:${key}`;
    return h("button", {
      class: "info-btn", title: t("Erklärung"), "aria-label": t("Erklärung"),
      onclick: (ev) => { ev.stopPropagation(); this._helpOpen = this._helpOpen === id ? null : id; this._render(); },
    }, icon("mdi:information-outline"));
  }

  _renderPoll(dev) {
    const key = `poll:${dev.serial}`;
    const select = h("select", {
      "aria-label": t("Ist-Temperatur abfragen"), disabled: this._busy.has(key) || !dev.device_id,
      onchange: () => this._call(key, { type: "eq3_max/set_poll", device_id: dev.device_id, minutes: Number(select.value) },
        t("Abfrage: {value}", { value: t(POLL_LABELS[Number(select.value)]) })),
    }, Object.entries(POLL_LABELS).map(([v, label]) => h("option", { value: v }, t(label))));
    select.value = String(dev.poll_minutes);
    return h("fieldset", {},
      h("legend", {}, t("Ist-Temperatur abfragen")),
      h("div", { class: "cfg" },
        h("span", { class: "label", title: t(CONFIG_HELP.ist_abfragen) }, t("Ist-Temperatur abfragen"), this._helpToggle(key, "ist_abfragen")),
        h("span", { class: "ctl" }, select),
        this._helpOpen === `${key}:ist_abfragen` ? h("div", { class: "help" }, t(CONFIG_HELP.ist_abfragen)) : null));
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
        control = h("select", { "data-focus": `cfg:${dk}:${item.key}`, "aria-label": configLabel(item) },
          // Noch unbekannt (Anzeige meldet erst das Gerät): Platzhalter statt einer Option.
          (current === null || current === undefined
            ? [h("option", { value: "", disabled: true }, "–")] : [])
            .concat(item.options.map((o) => h("option", { value: String(o.value) }, optionLabel(item, o)))));
      } else {
        control = h("input", {
          type: "number", min: String(item.min), max: String(item.max), step: String(item.step),
          inputmode: "decimal", "data-focus": `cfg:${dk}:${item.key}`, "aria-label": configLabel(item),
        });
      }
      control.value = current === null || current === undefined ? "" : String(current);
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
      const meta = [chip(SOURCE_LABELS[item.source] ? t(SOURCE_LABELS[item.source]) : item.source || t("unbekannt"),
        item.source === "werksvorgabe" ? "warn" : item.source === "gesetzt" || item.source === "gemeldet" ? "ok" : "info")];
      if (item.pending !== null && item.pending !== undefined) {
        meta.push(chip(t("ausstehend: {value}", { value: formatConfig(item, item.pending) }), "warn"));
        meta.push(h("span", {}, t("quittiert: {value}", { value: formatConfig(item, item.value) })));
      }
      if (item.type === "number") {
        meta.push(h("span", {}, t("{min} … {max}, Schritt {step}", { min: plainNum(item.min), max: plainNum(item.max), step: plainNum(item.step) })));
      }
      meta.push(error);
      return h("div", { class: "cfg" },
        h("span", { class: "label", title: CONFIG_HELP[item.key] ? t(CONFIG_HELP[item.key]) : null },
          configLabel(item), this._helpToggle(dk, item.key)),
        this._helpOpen === `${dk}:${item.key}` && CONFIG_HELP[item.key]
          ? h("div", { class: "help" }, t(CONFIG_HELP[item.key])) : null,
        h("span", { class: "ctl" }, control, item.unit ? h("span", { class: "sub" }, item.unit) : null),
        h("div", { class: "meta" }, meta));
    });

    const status = [];
    if (set.pending) status.push(chip(t("Satz ausstehend"), "warn"));
    if (set.failed) status.push(chip(t("nicht quittiert – wird beim nächsten Melden erneut gesendet"), "error"));

    const count = h("span", { class: "sub" });
    const discard = h("button", {
      class: "action",
      onclick: () => { delete this._drafts[dk]; this._confirm = null; this._render(); },
    }, t("Verwerfen"));
    const send = h("button", { class: "action primary", onclick: () => { this._confirm = dk; this._render(); } }, t("Satz senden"));
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
          ? t("Wert muss zwischen {min} und {max} in Schritten von {step} liegen",
            { min: plainNum(item.min), max: plainNum(item.max), step: plainNum(item.step) })
          : "";
      }
      const n = Object.keys(changes).length;
      count.textContent = n ? t("{n} geändert", { n }) : "";
      discard.style.display = Object.keys(draft).length ? "" : "none";
      send.disabled = !n || invalid || busy || !dev.device_id;
      return { changes, invalid };
    };
    const { changes, invalid } = update();

    if (this._confirm === dk && Object.keys(changes).length && !invalid) {
      const factory = set.values.filter((item) => !(item.key in changes) && item.source === "werksvorgabe" &&
        (item.pending === null || item.pending === undefined));
      confirmBox.append(h("div", { class: "confirm" },
        h("div", {}, t("Satz „{title}“ an {name} senden:", { title: setTitle(set), name: dev.name })),
        h("ul", {}, set.values.filter((item) => item.key in changes).map((item) =>
          h("li", {}, `${configLabel(item)}: ${formatConfig(item, effective(item))} → ${formatConfig(item, changes[item.key])}`))),
        factory.length
          ? h("div", {}, t("Mit dem Satz gehen diese angenommenen Werksvorgaben mit (am Gerät nie gelesen):"),
            h("ul", {}, factory.map((item) => h("li", {}, `${configLabel(item)}: ${formatConfig(item, item.value)}`))))
          : h("div", {}, t("Alle übrigen Werte des Satzes sind bekannt.")),
        h("div", { class: "setfoot" },
          h("button", { class: "action", onclick: () => { this._confirm = null; this._render(); } }, t("Abbrechen")),
          h("button", { class: "action primary", disabled: busy || !dev.device_id, onclick: () => this._sendSet(dev, set, changes) }, t("Senden")))));
    }

    return h("fieldset", {},
      h("legend", {}, setTitle(set)),
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
        const labels = set.values.filter((item) => res.factory_keys.includes(item.key)).map(configLabel);
        return t("Satz „{title}“ gesendet – wartet auf Quittung.", { title: setTitle(set) }) +
          (labels.length ? t(" Werksvorgaben mitgesendet: {labels}.", { labels: labels.join(", ") }) : "");
      });
    if (result !== undefined) {
      delete this._drafts[dk];
      this._confirm = null;
      this._render();
    }
  }
}

if (!customElements.get("eq3-max-panel")) customElements.define("eq3-max-panel", Eq3MaxPanel);
