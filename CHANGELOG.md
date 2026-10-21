# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [0.5.0] – 2026-10-21

### Behoben

- Integration nur über die Oberfläche einrichtbar, als `CONFIG_SCHEMA` erklärt (Hinweis von
  hassfest); ein `eq3_max:`-Block in der `configuration.yaml` wird jetzt mit einer Warnung
  übergangen.
- Ein einzelnes unerreichbares Gerät hielt die Taubheitserkennung für einen tauben Stick: Nach
  jedem gehörten Telegramm eines anderen Geräts durfte der Port erneut „schnell“ neu geöffnet
  werden, und nach jedem Neuverbinden ging der fehlgeschlagene Befehl wieder raus – eine
  Schleife aus Senden, keiner Quittung und Neu-Öffnen (gesehen am 19.10.2026 mit einem
  Thermostat bei −90 dBm). Hört das Modul nach dem Neu-Öffnen andere Geräte, gilt das Gerät
  jetzt als stumm: seine Befehle öffnen den Port nicht mehr neu und gehen erst mit seiner
  nächsten Meldung wieder raus; einmalige Warnung „antwortet nicht … Gerät prüfen“.
- Die Warnung „Port wird neu geoeffnet“ erscheint nur noch, wenn der Port wirklich neu geöffnet
  wird (vorher auch, wenn die Funkverbindung das Neu-Öffnen ablehnte).
- Nach einem Neustart ging ein ausstehender, schon einmal gescheiterter Befehl doppelt raus:
  einmal beim Start und noch einmal beim ersten Verbinden, weil er laut Speicher noch als
  gescheitert galt.

### Geändert

- Seite „eQ-3 MAX!“ neu gestaltet: Kopf mit Zustands-Pille und einer Kachel je Funkmodul,
  Kennzahlen-Leiste (Thermostate, heizen gerade, Fenster offen, Batterie schwach, auffällig),
  Bereichsüberschriften mit Anzahl, Karten mit farbigem Zustand (orange = Ventil bzw. Fenster
  offen, rot = Problem), großer Ist-Temperatur, Sollwert als Pille und Fußzeile mit Symbolen;
  Seitenfenster mit farbigem Gerätesymbol, Merkmalen als Chips und Reitern als Umschalter.
  Farben aus dem HA-Theme (hell/dunkel), Bewegung abschaltbar über „weniger Bewegung“.

- Neue Einträge starten mit eingeschalteter Sendezeit-Bremse (1 % = 36 s pro Stunde je Modul);
  bestehende Einträge ohne gespeicherte Option laufen unverändert weiter.

### Hinzugefügt

- Prüfungen für HACS: GitHub-Workflow mit HACS-Action und hassfest; Manifest-Schlüssel sortiert.
- MIT-Lizenz; README mit Markenhinweis, Hinweis zur 1-%-Grenze und Quellen der Anregungen.

### Dokumentation

- README und Projektseite ohne den früheren Namen `max_cul` (Umzugsanleitung bleibt im
  internen Wiki; der Umzug selbst funktioniert weiter).
- Funkbudget neutral beschrieben (Standard-culfw, Bremse an); kein Hinweis mehr auf culfw-Builds
  ohne Budgetprüfung als erprobte Firmware.

- Projektseite mit Material for MkDocs (Ordner `website/`, `mkdocs.yml`): Startseite mit
  Funktionsübersicht und Bildschirmfoto, Doku in „Loslegen“, „Umstieg“, „Handbuch“ (in
  Einzelseiten aufgeteilt), FAQ und Changelog; Suche, Hell/Dunkel, Schriften selbst
  ausgeliefert (privacy-Plugin). Veröffentlichung über GitHub Pages
  (`.github/workflows/pages.yml`), Versionen fest in `requirements_docs.txt`.
- `docs/handbuch.md` und `docs/migration.md` entfallen, die Website ist jetzt die Quelle.
  Das Gitea-Wiki bleibt als interne Fassung.
- Seite „eQ-3 MAX!“: Funkmodul-Angabe auf den Karten mit kleinerem Symbol auf der Textlinie.

## [0.4.0] – 2026-10-19

Mehrere Funkmodule mit einer Zentralen-Adresse; Geräte lassen sich ohne Neuanlernen einem
anderen Modul zuordnen. Am echten Funk mit zwei Modulen noch nicht erprobt.

### Hinzugefügt

- Mehrere Funkmodule in einem Eintrag, alle mit derselben Zentralen-Adresse (wie die
  Interfaces bei Homegear): Optionen → „Funkmodule“ fügt USB-Sticks oder Netzwerk-CULs mit
  Namen hinzu (geprüft mit `V`) oder entfernt sie (ihre Geräte gehen zurück aufs Hauptmodul).
- Jedes Gerät hat ein zugeordnetes Funkmodul (`radio` in den Eintragsdaten, leer = Hauptmodul).
  Alle Befehle an das Gerät gehen darüber; empfangen wird über alle Module. Umstellen sendet
  nichts an das Gerät, wartende Befehle wechseln mit. Neue Geräte bleiben auf dem Modul, das
  ihre Anmeldung zuerst gehört hat.
- Ein Telegramm, das ein zweites Modul binnen 1 s hört, wird nicht noch einmal ausgewertet;
  die Empfangsstärke steht je Modul im Gerät (`rssi_by_radio`). Die RSSI-Entität zeigt das
  zugeordnete Modul.
- Entität `select.<gerät>_funkmodul` (nur bei mehr als einem Modul) mit den Attributen
  `rssi_<modul>`; Seite „eQ-3 MAX!“: Module im Kopf des Eintrags, Modul auf jeder Karte,
  Reiter „Funkmodul“ mit Empfangsstärke je Modul und „Zuordnen“; WebSocket-Befehl
  `eq3_max/set_radio`.
- Jedes Zusatzmodul ist ein eigenes HA-Gerät; die MAX!-Geräte hängen unter ihrem Modul.
- Eigenes Funkbudget, eigene Reparaturmeldungen (`port_lost_<id>`, `stick_deaf_<id>`) und
  eigene Taubheitserkennung je Modul. `binary_sensor.eq3_max_verbunden` ist an, wenn alle
  Module verbunden sind; `sensor.eq3_max_sendezeit_1h` zeigt das meistbelastete,
  `sensor.eq3_max_warteschlange` die Summe, je mit Attribut `funkmodule`. Diagnose mit
  Modulen und ihrem Zustand.

### Geändert

- Anlernen braucht nur noch irgendein verbundenes Modul, ein Werksreset nur das Modul des
  Geräts.
- Alle Module teilen einen Telegrammzähler (eine Quittung passt nie zu Befehlen zweier
  Module). „Stick empfängt nichts“ verschwindet nur, wenn genau dieses Modul wieder empfängt.
- Entfernen eines Moduls: seine Geräte wechseln sofort aufs Hauptmodul (kein Zurückschreiben
  bis zum Neuladen), seine Reparaturmeldungen und RSSI-Werte gehen mit, seine ID wird nie
  wieder vergeben.

- Homegear-Host hat keine Vorgabe mehr (Einrichtungsdialog und `tools/homegear_export.py`,
  dort jetzt Pflichtangabe `--host`).

### Dokumentation

- README: Installation über HACS (benutzerdefiniertes Repository), Verweis auf die Migrationsanleitung.
- Migrationsanleitung Homegear → eq3_max ergänzt: Tabelle, was woraus wird (Entitäten,
  Konfiguration, Verknüpfungen, Taster-Ereignisse) und was auf Werksvorgabe bleibt
  (Fenster-auf-Dauer, Maximalventil, Ventil-Offset); Zentralen-Adresse aus dem Homegear-Log
  ermitteln; Live-Quelle „Homegear“ im Einrichtungsdialog; Abnahme über die Seite „eQ-3 MAX!“;
  zwei neue Stolperstellen.
- Migration neu gegliedert (Übersicht, Homegear, max_cul; im Wiki als eigene Seiten mit
  Seitenleiste).
- Handbuch Abschnitt 6a „Mehrere Funkmodule“, README-Abschnitt dazu.
- MAX! Cube mit a-culfw als zweites Funkmodul neben dem nanoCUL beschrieben (Wiki: Hardware,
  Einrichtung, Migration, FAQ): austauschbar ohne Neuanlernen, weil die Zentralen-Adresse
  zählt; Prüfen mit `nc` und `V`; Sendezeit-Bremse wegen `LOVF` einschalten.

## [0.3.0] – 2026-10-09

Seite „eQ-3 MAX!“ in der Seitenleiste: Übersicht aller Geräte nach Bereich, Funkmodul-Status mit
Sendezeit und Anlernen, Verknüpfungen und Gerätekonfiguration im Seitenfenster. Im echten HA
(2026.9.4) vom Betreiber gesichtet. Dazu: Gerätesuche ohne veraltetes `async_get_device`.

### Hinzugefügt
- Seite **„eQ-3 MAX!“** in der Seitenleiste (nur Administratoren): Kopfzeile je Funkmodul
  (Verbindung, Sendezeit gegen 36 s, Warteschlange, Anlernen mit Countdown), Gerätekarten nach
  HA-Bereich, Seitenfenster mit Verknüpfungen (Zustand, Lösen, Partner hinzufügen nur mit
  erlaubten Geräten, Hinweise für Fensterkontakt/Taster) und Gerätekonfiguration je Satz
  (Quelle, ausstehend, Raster der Integration, Hinweis auf mitgesendete Werksvorgaben, ein
  Telegramm je Satz). Vanilla Custom Element ohne Build und Fremdbibliotheken, hell/dunkel,
  schmale Bildschirme.
- WebSocket-Befehle `eq3_max/overview`, `subscribe` (entprellt 250 ms), `link`, `unlink`,
  `pair`, `set_config` (alle nur für Administratoren, Fehler mit deutschem Text).
- Hub-Methode `set_config_set`: mehrere Werte eines Satzes auf einmal, genau ein Telegramm;
  liefert die mitgesendeten Werksvorgaben.
- `configuration_url` am Funkmodul und an allen Geräten führt auf die Seite.

### Geändert
- Manifest: `dependencies` `http` und `websocket_api`, `after_dependencies` zusätzlich
  `frontend` und `panel_custom`.
- Bereiche und Raster der Konfigurationswerte stehen in einer gemeinsamen Tabelle
  (`config_defs.py`) für Entitäten und Seite.

## [0.2.0] – 2026-10-09

Am selben Tag nach 0.1.0: Preset „away“ und Werksreset (Block 1), Gerätekonfiguration (Block 2),
Verknüpfungen (Block 3), CUL über Netzwerk (Block 4), dazu Korrekturen aus dem Betrieb. Alles im
Haus eingespielt; Netzwerk-CUL nur simuliert getestet (kein Gerät angeschlossen).

### Gemessen
- Verknüpfungen am 09.10.2026 an der Thermostatseite abgenommen: Wandthermostat ↔ ht-wohnzimmer1
  gelöst und neu angelegt. Der Wandthermostat quittierte das Lösen, **der Heizkörperthermostat
  lehnte das Entfernen des Wandthermostats ab (NAK)**; das erneute Hinzufügen quittierten beide.
  Fensterkontakte wurden bewusst nicht getestet.

### Hinzugefügt
- CUL über Netzwerk: Neben dem USB-Stick lässt sich ein CUL per TCP anbinden
  (a-culfw auf einem CUN oder geflashten MAX! Cube, Standardport 2323). Der
  erste Einrichtungsschritt fragt „USB-Stick“ oder „Netzwerk (CUN, geflashter
  Cube)“; Netzwerk prüft Host und Port mit `V` (Antwort binnen 5 s, sonst
  „Dort antwortet keine culfw“). Verbindungsaufbau mit 10 s Timeout,
  TCP-Keepalive und TCP_USER_TIMEOUT 120 s (wo verfügbar); Abbrüche werden wie
  beim Stick nach 30 s neu verbunden. Der Host muss ein bloßer Hostname bzw.
  eine IP-Adresse sein („Nur Hostname oder IP-Adresse angeben …“), ein von
  Hand eingegebener serieller Port ein Pfad unter `/dev/`.
- Optionen: Menü „Einstellungen“ / „Verbindung ändern“. Die Verbindung lässt
  sich ohne Neuanlegen zwischen USB und Netzwerk wechseln (geprüft wie bei der
  Einrichtung); eine geänderte Verbindung lädt die Integration neu,
  Urlaubswerte weiterhin nicht. Die gerade genutzte Verbindung wird nicht
  geprüft (die Integration belegt sie); unverändert gespeichert endet der
  Dialog ohne Prüfung und ohne Neustart.
- Diagnose enthält `connection` mit Art (`usb`/`network`) und Ziel (Pfad bzw.
  `host:port`).
- Preset „Abwesend“ (`away`) schaltet den MAX!-Modus temporär mit Endzeit:
  Urlaubstemperatur und -dauer kommen aus den neuen Optionen (Standard 18,0 °C,
  24 h), das Ende wird auf die nächste volle oder halbe Stunde aufgerundet
  (angebrochene Minuten zählen mit). Das vom Gerät gemeldete Ende steht im
  Attribut `bis` (Ortszeit mit Zeitzonenversatz). Ändern der Urlaubswerte
  startet die Integration nicht neu. Ein ausstehender Befehl, dessen Ende
  schon vorbei ist, wird verworfen statt wiederholt.
- Dienst `eq3_max.set_away`: Thermostate bis zu einem Zeitpunkt auf eine
  Temperatur setzen (ohne Temperatur gilt die Urlaubstemperatur).
- Dienst `eq3_max.factory_reset`: Werksreset eines Geräts per Funk; nur bei
  Quittung wird es aus der Integration entfernt. Ohne verbundenes Funkmodul
  wird abgelehnt; der Reset geht höchstens 30 s lang raus. Fehlermeldungen:
  „Werksreset nicht gesendet“ oder „Gerät hat den Werksreset nicht quittiert –
  es wurde eventuell trotzdem zurückgesetzt“ (dann über „Gerät löschen“
  entfernen und neu anlernen).
- Geräte lassen sich auf der Geräteseite löschen („Gerät löschen“); das
  vergisst sie nur, ohne Funk. Das Funkmodul ist ausgenommen.
- Gerätekonfiguration als Entitäten der Kategorie „Konfiguration“: Komfort-,
  Eco-, Maximal-, Minimal- und Fenster-auf-Temperatur, Temperatur-Offset und
  Fenster-auf-Dauer für Heizkörper- und Wandthermostate (Telegramm 0x11),
  zusätzlich Boost-Dauer und -Ventilstellung, Entkalkungstag und -stunde,
  maximale Ventilstellung und Ventil-Offset nur für Heizkörperthermostate
  (0x12). `number`/`select`, entity_id `<plattform>.<basis>_<schlüssel>`
  (z. B. `number.ht_bad_unten_komfort`, `select.ht_bad_unten_entkalkung_tag`);
  die Migration legt sie auch für bestehende Geräte an.
  Geräte nehmen nur ganze Sätze: Eine Änderung schickt den ganzen Satz mit
  den übrigen Werten. Die Geräte melden ihre Konfiguration nicht zurück;
  angezeigt wird der zuletzt quittierte Wert, ein gesendeter, noch nicht
  quittierter steht im Attribut `ausstehend` und geht wie Stellbefehle erneut
  raus (nächster Status nach Fehlschlag, Wiederverbinden, Start; der neueste
  gewinnt). Attribut `quelle`: `homegear` (übernommen), `werksvorgabe`
  (angenommen) oder `gesetzt` (aus HA gesendet und quittiert; gilt für alle
  Werte des quittierten Satzes). Ein unquittierter Satz zeigt sich auch am
  Funkfehler-Sensor; der Fehlschlag gilt je Satz, eine Änderung am anderen
  Satz löscht ihn nicht. Werden angenommene Werksvorgaben mitgesendet, warnt
  das Log („Sende angenommene Werksvorgaben mit: …“). Boost-Dauer wird als
  „5 min“ usw. angeboten; ungültige Werte werden mit deutscher Meldung
  abgelehnt („Wert muss zwischen 4,5 und 30,5 in Schritten von 0,5 liegen“).
- Homegear-Übernahme liest die Konfiguration aus dem Export
  (`COMFORT_TEMPERATURE`, `ECO_TEMPERATURE`, `MAX_TEMPERATURE`,
  `TEMPERATURE_OFFSET`, `WINDOW_OPEN_TEMPERATURE`, `BOOST_POSITION`,
  `BOOST_TIME_PERIOD`, `DECALCIFICATION_WEEKDAY`, `DECALCIFICATION_TIME`);
  fehlende Werte (Minimaltemperatur, Fenster-auf-Dauer, Ventil maximal,
  Ventil-Offset) gelten als Werksvorgabe. Neu angelernte Geräte und
  bestehende Einträge ohne Konfiguration bekommen die Werksvorgaben (21,0 /
  17,0 / 30,5 / 4,5 °C, Offset 0,0 K, Fenster 12,0 °C für 15 min, Boost 5 min
  bei 80 %, Entkalkung Samstag 12 Uhr, Ventil 100 % / 0 %).
- Verknüpfungen anlegen und lösen: Dienste `eq3_max.link` und
  `eq3_max.unlink` (Felder `device_id`, `partner_device_id`, Geräteauswahl)
  mit den Telegrammen 0x20 AddLinkPartner und 0x21 RemoveLinkPartner
  (Partneradresse + Gerätetyp, nach FHEM `associate`/`deassociate`). Jedes der
  beiden Geräte bekommt den anderen als Partner und quittiert einzeln; das
  Paar gilt erst als vollständig, wenn beide quittiert haben. Erlaubt sind
  Fensterkontakt und Eco-Taster mit Heizkörper- oder Wandthermostat,
  Wandthermostat mit Heizkörperthermostat und Heizkörperthermostate
  untereinander; andere Paare, Selbstverknüpfung, schon bestehende bzw. nicht
  bestehende Verknüpfungen und schon beauftragte Änderungen werden mit
  deutscher Meldung abgelehnt. Die Dienste kehren nach dem Einreihen sofort
  zurück.
- Schlafende Geräte (Fensterkontakte, Eco-Taster) bekommen ihren Auftrag erst
  nach ihrem nächsten Telegramm an die Zentrale (nicht an ihre Thermostate),
  80 ms nach dem letzten einer Folge, ohne Weckpräambel (`Zf`, Sendezeit ohne
  die 1 s): ein Versuch, spätestens 0,3 s nach dem Auslösen, 0,5 s
  Quittungswartezeit. Verpasst oder unquittiert wartet der Auftrag wieder auf
  das nächste Telegramm; nach zwei unquittierten `Zf`-Versuchen geht der
  nächste mit Präambel (`Zs`). Bis dahin zeigt die Verknüpfung „wartet auf
  Fensterkontakt – bitte Fenster einmal öffnen und schließen“ (Taster: „wartet
  auf Eco-Taster – bitte Taster einmal drücken (oder Anlerntaste)“). Wartende
  Aufträge überstehen Neustarts. Unquittierte Aufträge an Thermostate gehen wie
  Konfigurationssätze erneut raus (nächster Status, Wiederverbinden, Start);
  eine Ablehnung (NAK) ist endgültig („fehlgeschlagen (abgelehnt)“), erst ein
  neuer Dienstaufruf sendet wieder.
- Diagnosesensor `sensor.<basis>_verknuepfungen` für alle Geräte: Zahl der
  vollständigen Verknüpfungen, Attribute `partner` (Namen) und `ausstehend`
  („<Partner>: ausstehend / wartet … / fehlgeschlagen / fehlgeschlagen
  (abgelehnt) / einseitig“). Die
  Migration legt ihn auch für bestehende Geräte an.
- Quittierte Verknüpfungen (`links`, Partner-Seriennummern) stehen im
  Konfigurationseintrag und im Speicher, offene Aufträge nur im Speicher.
- Homegear-Übernahme liest die Verknüpfungen per `getLinks` (bei Fehler
  keine).
- Ein quittierter Werksreset entfernt das Gerät auch aus den Verknüpfungen der
  übrigen Geräte und verwirft offene Verknüpfungsaufträge mit ihm; Partner, die
  es quittiert kannten, bekommen RemoveLinkPartner (als ausstehendes Lösen
  angezeigt, Schläfer beim nächsten Telegramm).

### Geändert
- Bestehende Einträge ohne `connection` gelten als USB und laufen unverändert
  über den seriellen Port. Neue Einträge speichern `connection` (`usb` bzw.
  `network` mit `host`/`port`).
- Die Reparaturmeldung heißt „CUL nicht erreichbar“ und nennt das Ziel (Pfad
  bzw. `host:port`); „Stick empfängt nichts“ rät beim Netzwerk-CUL zum
  Neustart des Geräts.
- Der Handshake überspringt Zeilen vor der Antwort auf `V` (über TCP empfängt
  culfw zwischen den Sitzungen weiter), statt dafür einen Versuch zu
  verbrauchen.
- Die Fenster-auf-Temperatur ist jetzt der Konfigurationswert
  `fenster_temperatur` (ein Wert für Anzeige, Senden und die Erkennung der
  Komforttemperatur); das alte Feld `window_open_temperature` im Eintrag wird
  beim Start übernommen. „Heizen“ ohne gemerkte Komforttemperatur nimmt die
  konfigurierte Komforttemperatur, erst danach 21,0 °C.
- Tauber Funkstick wird sofort neu geöffnet: Bleibt ein Stellbefehl oder
  Werksreset nach allen Wiederholungen unquittiert und hat der Stick seit dem
  ersten Senden dieses Befehls gar nichts mehr empfangen, wird der Port gleich
  neu geöffnet (Warnung „CUL empfaengt nach dem Senden nichts mehr – Port wird
  neu geoeffnet“) statt erst nach 600 s Funkstille – höchstens einmal je
  Funkstille; erst ein empfangenes Telegramm erlaubt das nächste. Danach
  übernimmt der Wächter. Ausstehende Befehle gehen nach dem Wiederverbinden
  erneut raus. Das schnelle Neuöffnen löst keine Reparaturmeldung „Stick taub“
  aus (ein unerreichbares Gerät soll keine erzeugen). Ablehnung (NAK),
  abgelaufene und nicht gesendete Befehle, Zeitantworten und Anlern-Antworten
  lösen es nicht aus.
- Neuöffnen durch den Wächter meldet den Stick sofort als getrennt.

### Behoben
- „Heizen“ (auch Einschalten und Preset „keins“) aus „Abwesend“ oder „Boost“
  stellt wieder die letzte Komforttemperatur her statt die Urlaubs- bzw.
  Boost-Temperatur manuell festzuschreiben. Die Komforttemperatur ist der
  letzte manuelle Sollwert über 4,5 °C, aus HA gesendet oder vom Gerät
  gemeldet (zuletzt gilt); sie übersteht Neustarts (Gerätespeicher), sonst
  gilt 21,0 °C. Die Fenster-auf-Temperatur (Standard 12,0 °C, aus Homegear
  `WINDOW_OPEN_TEMPERATURE` übernommen) zählt nicht als Komforttemperatur.
- Geräte- und Entitätsnamen nach Übernahme: Die Homegear-Übernahme holt den
  Namen aus den Homegear-Metadaten (`NAME`) statt die Seriennummer zu nehmen.
  Steht trotzdem nur die Seriennummer (oder nichts) im Eintrag, übernimmt die
  Migration den Namen der Vorgänger-Entität (`homematic`/`max_cul`, ohne
  Zusatz wie „ STATE“ oder „ LOWBAT“) und speichert ihn im Eintrag. Beim
  Start werden die Gerätenamen im Geräteregister an die Namen im Eintrag
  angeglichen, außer der Nutzer hat das Gerät selbst umbenannt.

## [0.1.0] – 2026-10-09

Erste produktive Version. Seit 09.10.2026 ~14:10 ersetzt die Integration
Homegear und die legacy `homematic`-Integration im Haus (24 Geräte).

### Hinzugefügt
- Protokollschicht ohne HA-Abhängigkeit: Telegramme (Layout nach FHEM
  `14_CUL_MAX`/`10_MAX`), serieller Transport mit Wächter (tauber Stick,
  verlorener Port), Funkplaner (ein Telegramm unterwegs, Quittung über
  Absender+Zähler, Wiederholung, Sendezeit), Gerätemodell, Hub.
- HA-Integration: Einrichtungsdialog mit Übernahme aus Homegear (live oder
  JSON), Übernahme der Entity-IDs von `homematic`, Plattformen climate, sensor,
  binary_sensor, event, button, Diagnose, Reparaturmeldungen.
- Logo (Icon und Logo, hell und dunkel) unter `custom_components/eq3_max/brand/`,
  erzeugt mit `tools/make_brand.py`; HA ab 2026.9 lädt es direkt aus der
  Integration.
- Werkzeuge `tools/homegear_export.py`, `tools/mitschnitt_umwandeln.py`,
  `tools/make_brand.py`.

### Geändert
- Umbenennung max_cul → eq3_max (noch am selben Tag, nach der Umschaltung):
  Domain `eq3_max`, Name „eQ-3 MAX!“, Hub-Gerät „eQ-3 MAX! Funkmodul“ mit festen
  entity_ids `*.eq3_max_*`, Speicher `eq3_max.devices.<entry_id>`, Exportdatei
  `eq3_max_export.json`. Entitäten von `max_cul` werden wie die von `homematic`
  mit gleicher entity_id übernommen; solange `max_cul` geladen ist, bricht die
  Einrichtung mit der Reparaturmeldung `max_cul_active` ab.
- Stellbefehle gehen ohne Gruppe (Gruppe 00, Flags 00) an alle Geräte; Homegear
  hatte für drei Thermostate Gruppe 01 benutzt.

### Behoben
- Veralteter Parameter `via_device` (Bruch in HA 2027.8) ersetzt: Geräte werden
  nach dem Plattform-Setup per `via_device_id` mit dem Funkmodul verknüpft.

### Gemessen
- Mitschnitt des Funkverkehrs (1,5 h, 94 Telegramme), siehe `docs/mitschnitt.md`:
  0x60/0x70 sind Broadcasts ohne Quittung; 0x30/0x40/0x50 an die Zentrale
  quittiert die culfw per `Za`.
- Umschaltung und Abnahme, siehe `docs/umschaltung.md`: Quittung nach 2–10 s
  (inkl. 1 s Weckpräambel), Gruppe-0-Befehle funktionieren, zwei verlorene
  Quittungen bei gleichzeitiger Bedienung.
