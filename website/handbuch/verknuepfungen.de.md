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
- **Altverknüpfungen (ab 0.7.0).** Nach getauschten oder umgezogenen Thermostaten trägt ein
  Gerät manchmal noch einen Partner, den die Integration nicht kennt und der es selbst
  nicht mehr kennt. Der Partner quittiert dann nie: Ein Wandthermostat meldet bei jeder
  Sollwertänderung **Funkfehler**, ein Fensterkontakt wiederholt sein Telegramm minutenlang.
  Im Telegramm-Trace erkennt man es an Telegrammen des Geräts an eine Adresse ohne Antwort.
  Löschen, nur an diesem einen Gerät:
  ```yaml
  action: eq3_max.unlink
  data:
    device_id: <Gerät mit dem Überbleibsel>
    partner_device_id: <alter Partner>
    force: true
  ```
  Der alte Partner bekommt nichts gesendet. Bei Fensterkontakten wartet auch dieser Auftrag
  auf das nächste Fenster-Ereignis.

## Gruppen-ID (ab 0.8.0)

Thermostate einer Gruppe übernehmen Stellbefehle gemeinsam: Die Integration schickt sie dann
mit Gruppenkennung, und alle Geräte der Gruppe stellen sich um. Auf der Seite „eQ-3 MAX!“ im
Reiter **Verknüpfungen** unter **Gruppen-ID**:

- **Setzen**: eine ID 1–255 eintragen; **Entfernen** nimmt sie wieder weg.
- **Für den Raum vergeben**: dieses Thermostat und alle mit ihm verknüpften Thermostate
  bekommen eine gemeinsame ID, die sonst kein Gerät hat (haben sie schon eine gemeinsame,
  bleibt es bei der). Alle **anderen** Thermostate bekommen dabei einmal „Gruppe entfernen“:
  Die Geräte melden ihre Gruppe nicht, und eine alte ID aus Cube- oder Homegear-Zeiten würde
  sonst ein fremdes Thermostat mitschalten.

Die neue ID gilt erst, wenn das Gerät sie quittiert hat; bis dahin steht sie als
„ausstehend“ da, ohne Quittung geht sie beim nächsten Melden des Geräts erneut raus.
Nach einem Werksreset bekommt das Gerät seine ID automatisch zurück.

**Wozu?** Ein Sollwert, den HA an den Wandthermostat schickt, reicht dieser erst mit seiner
nächsten Runde an die Heizkörper weiter (gemessen 2–5 min). Mit einer gemeinsamen Gruppe
übernehmen alle Geräte des Raums ihn aus einem Telegramm (gemessen 1–2 min, die Heizkörper
hören nur in Abständen).
