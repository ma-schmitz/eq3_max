# Verknüpfungen


Fensterkontakte und Wandthermostate wirken **direkt per Funk** auf verknüpfte Thermostate.

- Anzeige: `sensor.<gerät>_verknuepfungen` — Zahl der vollständigen Verknüpfungen, Attribut
  `partner` (Namen), `ausstehend` (laufende Aufträge mit Zustand).
- Anlegen/Lösen: Dienste `eq3_max.link` / `eq3_max.unlink` mit zwei Geräten; beide Richtungen
  werden gesendet und einzeln quittiert.
  ```yaml
  action: eq3_max.link
  data:
    device_id: <Fensterkontakt>
    partner_device_id: <Thermostat>
  ```
- **Fensterkontakte und Eco-Taster schlafen.** Aufträge an sie warten, bis sie sich melden:
  Zustand „wartet auf Fensterkontakt – bitte Fenster einmal öffnen und schließen“ (Taster:
  einmal drücken). Gesendet wird dann sofort ohne Weckpräambel; nach zwei Fehlversuchen mit
  Präambel.
- Zustände in `ausstehend`: ausstehend · wartet auf … · fehlgeschlagen (wird wiederholt) ·
  **fehlgeschlagen (abgelehnt)** (Gerät hat abgelehnt, keine automatische Wiederholung) ·
  einseitig (nur eine Seite kennt die andere).
- Bekannt (09.10.2026): Ein Heizkörperthermostat **lehnt das Entfernen eines Wandthermostats ab**;
  Hinzufügen funktioniert.
- Ein Werksreset löst die Verknüpfungen auch bei den früheren Partnern.
