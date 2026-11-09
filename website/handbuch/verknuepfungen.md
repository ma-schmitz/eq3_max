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
  einmal drücken; bei beiden geht auch die Anlerntaste, das Gerät bleibt angelernt). Gesendet
  wird ohne Weckpräambel, 80 ms nach dem letzten Telegramm des Geräts – ein Versuch je
  Gelegenheit, denn ein Kontakt hört nach eigenem Senden nur einen Moment zu. Mehrere
  Gelegenheiten je Ereignis sind normal: Der Kontakt meldet sich bei der Zentrale, dann bei
  jedem Partner und bei unerreichbaren Partnern minutenlang immer wieder. Bleibt der Auftrag
  mehrere Ereignisse lang „wartet auf …“, hilft der Telegramm-Trace
  ([Betrieb](betrieb.md#diagnose)).
- Zustände in `ausstehend`: ausstehend · wartet auf … · fehlgeschlagen (wird wiederholt) ·
  **fehlgeschlagen (abgelehnt)** (Gerät hat abgelehnt, keine automatische Wiederholung) ·
  einseitig (nur eine Seite kennt die andere).
- Bekannt (09.10.2026): Ein Heizkörperthermostat **lehnt das Entfernen eines Wandthermostats ab**;
  Hinzufügen funktioniert.
- Ein Werksreset löst die Verknüpfungen auch bei den früheren Partnern.
