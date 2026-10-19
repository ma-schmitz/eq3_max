# eq3_max

Home-Assistant-Integration für eQ-3 MAX! über einen CUL mit culfw: USB-Stick (z. B. nanoCUL868)
oder im Netzwerk (a-culfw auf CUN oder geflashtem MAX! Cube).
Ersetzt Homegear und die legacy `homematic`-Integration. Hieß bis 2026-10-09 `max_cul`.

**Dokumentation:** https://ma-schmitz.github.io/eq3_max/ – Installation, Umstieg von Homegear,
Handbuch und FAQ. Quelle im Ordner `website/` (Material for MkDocs, lokal:
`uv venv .venv-docs && uv pip install -p .venv-docs -r requirements_docs.txt &&
.venv-docs/bin/mkdocs serve`).

## Funktionen

- Heizkörper- und Wandthermostate als `climate`, Ventilstellung als eigener Sensor
- Fensterkontakte, Eco-Taster (als Event-Entitäten), Batterie, RSSI, Funkfehler
- Zustand übersteht Neustarts, verlorene Befehle werden erkannt und wiederholt
- Übernahme bestehender Homegear-Kopplungen und -Entity-IDs ohne Neuanlernen
- Übernahme der Entity-IDs des Vorgängers `max_cul` (gleiche unique_ids)
- Sendezeit-Sensor und Bremse auf 1 % (36 s pro Stunde, bei neuen Einträgen an)
- Preset „Abwesend“ (temporär mit Endzeit), Werksreset und Löschen von Geräten
- Gerätekonfiguration (Komfort-/Eco-Temperatur, Offset, Fenster, Boost, Entkalkung, Ventil)
- Verknüpfungen zwischen Geräten anlegen und lösen (Fensterkontakt, Taster, Wand- und Heizkörperthermostat)
- CUL per USB oder im Netzwerk (CUN, geflashter Cube), Wechsel in den Optionen
- Mehrere Funkmodule mit einer Zentralen-Adresse (z. B. eins pro Etage); Geräte ohne
  Neuanlernen einem anderen Modul zuordnen
- Seite „eQ-3 MAX!“ in der Seitenleiste: Überblick, Verknüpfungen und Gerätekonfiguration

## Verbindung (USB oder Netzwerk)

Der erste Einrichtungsschritt fragt nach der Anbindung:

- **USB-Stick**: serieller Port aus `/dev/serial/by-path/` (38400 Baud), wie bisher.
- **Netzwerk (CUN, geflashter Cube)**: Host und Port (Standard 2323). a-culfw auf
  einem CUN oder einem mit a-culfw geflashten MAX! Cube spricht dort dasselbe
  Textprotokoll wie der Stick. Vor dem Weiter wird `V` gesendet; ohne Antwort
  „V …“ binnen 5 s erscheint „Dort antwortet keine culfw“.

Danach geht es wie gewohnt mit Zentralen-Adresse und Geräteübernahme weiter. Die
unique_id bleibt die Zentralen-Adresse.

Die Verbindung lässt sich später unter Optionen → „Verbindung ändern“ wechseln
(USB ↔ Netzwerk oder anderer Port/Host), ohne die Integration neu anzulegen. Sie
wird wie bei der Einrichtung geprüft; eine geänderte Verbindung lädt die
Integration neu. Die gerade genutzte Verbindung wird nicht geprüft, weil die
Integration sie belegt; unverändert gespeichert bleibt sie ohne Neustart. Einträge von vor dieser Option (ohne `connection`) gelten als USB.

Netzwerkverbindung: Verbindungsaufbau mit 10 s Timeout, TCP-Keepalive (ein
verschwundenes Gerät fällt nach etwa 90 s auf) und TCP_USER_TIMEOUT 120 s, wo das
System es kennt; Wiederverbinden alle 30 s. Als Host nur Hostname oder IP-Adresse
eintragen (kein `http://`, kein Pfad). Wenn
der Wächter oder das schnelle Neuöffnen den CUL „neu öffnet“, wird nur die
TCP-Verbindung getrennt und neu aufgebaut. Anders als das Neuöffnen des Sticks
(DTR) setzt das das Funkmodul selbst nicht zurück; hilft es nicht, das Gerät
stromlos machen. a-culfw nimmt je nach Build nur einen TCP-Client gleichzeitig an;
andere Programme auf demselben Port stören. Zeilenenden `\r\n` und `\n` werden
beide akzeptiert.

Die Diagnose nennt Art (`usb`/`network`) und Ziel (Pfad bzw. `host:port`), die
Reparaturmeldung „CUL nicht erreichbar“ das Ziel.

## Mehrere Funkmodule

Unter Optionen → „Funkmodule“ kommen weitere USB-Sticks oder Netzwerk-CULs dazu, jedes mit
einem Namen. Alle arbeiten mit derselben Zentralen-Adresse (wie die Interfaces bei
Homegear). Jedes Gerät sendet über ein zugeordnetes Modul, empfangen wird über alle;
doppelt gehörte Telegramme werden einmal ausgewertet, die Empfangsstärke je Modul gemerkt.
Die Zuordnung ändert die Entität `select.<gerät>_funkmodul` oder der Reiter „Funkmodul“
auf der Seite „eQ-3 MAX!“. Am Gerät passiert dabei nichts, wartende Befehle wechseln mit.
Jedes Modul hat sein eigenes Funkbudget und seine eigene Reparaturmeldung. Details:
`website/handbuch/funkmodule.md`.

## Gerätekonfiguration

Jedes Thermostat hat Konfigurationsentitäten (Kategorie „Konfiguration“ auf
der Geräteseite):

| Schlüssel | HT | WT | Bereich |
|---|---|---|---|
| `komfort`, `eco`, `maximal`, `minimal`, `fenster_temperatur` | ja | ja | 4,5–30,5 °C, Schritt 0,5 |
| `offset` (Messwert-Offset) | ja | ja | −3,5…+3,5 K, Schritt 0,5 |
| `fenster_dauer` | ja | ja | 0–60 min, Schritt 5 |
| `boost_dauer` (Auswahl) | ja | – | „0 min“ … „60 min“ (0, 5, 10, 15, 20, 25, 30, 60) |
| `boost_ventil` | ja | – | 0–100 %, Schritt 5 |
| `entkalkung_tag` (Auswahl) | ja | – | Samstag … Freitag |
| `entkalkung_stunde` | ja | – | 0–23 |
| `ventil_max`, `ventil_offset` | ja | – | 0–100 % |

Die entity_ids folgen dem Gerät, z. B. `number.ht_bad_unten_komfort` oder
`select.ht_bad_unten_entkalkung_tag`.

- Die Geräte nehmen nur ganze Sätze (Temperaturen: Telegramm 0x11, Ventil:
  0x12). Wer einen Wert ändert, schickt den ganzen Satz mit den übrigen
  gespeicherten Werten.
  Werte mit Quelle `werksvorgabe` sind nur angenommen und werden dabei
  trotzdem ins Gerät geschrieben; das Log warnt dann mit „Sende angenommene
  Werksvorgaben mit: …“ und nennt die betroffenen Werte.
- Die Geräte melden ihre Konfiguration nicht zurück. Angezeigt wird der
  zuletzt quittierte Wert; ein gesendeter, noch nicht quittierter steht im
  Attribut `ausstehend` und wird wie ein Stellbefehl wiederholt (nächster
  Status nach Fehlschlag, nach Wiederverbinden und Start). Bei mehreren
  schnellen Änderungen geht nur der neueste Satz raus.
- Attribut `quelle`: `homegear` (aus dem Export übernommen), `werksvorgabe`
  (angenommen, weil unbekannt) oder `gesetzt` (aus HA gesendet und vom Gerät
  quittiert – gilt für alle Werte des Satzes).
- Werksvorgaben nach dem Anlernen: Komfort 21,0, Eco 17,0, Maximal 30,5,
  Minimal 4,5 °C, Offset 0,0 K, Fenster 12,0 °C für 15 min, Boost 5 min bei
  80 %, Entkalkung Samstag 12 Uhr, Ventil maximal 100 %, Ventil-Offset 0 %.
- Konfiguration und Quelle stehen im Konfigurationseintrag (und im
  Speicher); ausstehende Sätze nur im Speicher. Beim Start gilt je Wert der
  Eintrag vor dem Speicher.
- Die Fenster-auf-Temperatur ist zugleich der Wert, an dem die Integration
  einen gemeldeten Fenster-auf-Sollwert von einer Komforttemperatur
  unterscheidet. „Heizen“ ohne gemerkten manuellen Sollwert nimmt die
  Komforttemperatur aus der Konfiguration.

## Verknüpfungen

Verknüpfte Geräte reden direkt miteinander: Ein Fensterkontakt meldet „offen“
an sein Thermostat, ein Wandthermostat führt seine Heizkörperthermostate. Die
Dienste `eq3_max.link` und `eq3_max.unlink` legen eine Verknüpfung an bzw.
lösen sie (Telegramme 0x20 AddLinkPartner und 0x21 RemoveLinkPartner, wie FHEM
`associate`/`deassociate`).

- Erlaubt: Fensterkontakt–Heizkörperthermostat, Fensterkontakt–Wandthermostat,
  Wandthermostat–Heizkörperthermostat, Heizkörperthermostat–Heizkörperthermostat,
  Eco-Taster–Heizkörper- oder Wandthermostat. Andere Paare, ein Gerät mit sich
  selbst, schon verknüpfte (bzw. beim Lösen nicht verknüpfte) Paare und schon
  beauftragte Änderungen lehnt der Dienst mit einer Meldung ab.
- Eine Verknüpfung hat immer zwei Richtungen: Jedes der beiden Geräte bekommt
  den anderen als Partner und quittiert das einzeln. Eine Richtung, die schon
  besteht, wird nicht noch einmal gesendet.
- Der Dienst kehrt nach dem Einreihen sofort zurück. Thermostate bekommen ihren
  Teil gleich. Fensterkontakte und Eco-Taster schlafen und hören nur kurz nach
  einem eigenen Telegramm an die Zentrale zu (Telegramme an ihre Thermostate
  zählen nicht): Ihr Teil wartet, bis sie sich das nächste Mal melden, und geht
  80 ms nach dem letzten Telegramm einer Folge ohne Weckpräambel (`Zf`) raus –
  ein Versuch, höchstens 0,3 s nach dem Auslösen, 0,5 s Quittungswartezeit.
  Kommt er nicht rechtzeitig dran oder bleibt unquittiert, wartet der Auftrag
  wieder auf das nächste Telegramm; nach zwei unquittierten `Zf`-Versuchen geht
  der nächste mit Präambel (`Zs`, wie FHEM) raus. Dafür das Fenster einmal
  öffnen und schließen bzw. den Taster (oder die Anlerntaste) einmal drücken.
  Wartende Aufträge überstehen Neustarts; ein Werksreset des Geräts verwirft sie.
- Diagnosesensor `sensor.<basis>_verknuepfungen` an jedem Gerät: Zustand ist die
  Zahl der vollständigen Verknüpfungen (beide Richtungen quittiert), Attribut
  `partner` die Namen der Partner, Attribut `ausstehend` je unfertigem Paar
  „<Partner>: <Zustand>“ mit `ausstehend` (eingereiht oder unterwegs),
  „wartet auf Fensterkontakt – bitte Fenster einmal öffnen und schließen“
  (bzw. „wartet auf Eco-Taster – bitte Taster einmal drücken (oder
  Anlerntaste)“), `fehlgeschlagen`, `fehlgeschlagen (abgelehnt)` oder
  `einseitig` (nur eines der beiden Geräte kennt die Verknüpfung, nichts
  beauftragt – mit `eq3_max.link` vervollständigen).
- Unquittierte Aufträge an Thermostate gehen wie Stellbefehle erneut raus: beim
  nächsten Status des Geräts, nach dem Wiederverbinden und beim Start. Lehnt ein
  Gerät ab (NAK), bleibt es bei `fehlgeschlagen (abgelehnt)`; erst ein neuer
  Dienstaufruf sendet wieder.
- Quittierte Verknüpfungen (Partner-Seriennummern, Feld `links`) stehen im
  Konfigurationseintrag und im Speicher, offene Aufträge nur im Speicher. Beim
  Start gilt der Eintrag; ein Eintrag ohne `links` nimmt die aus dem Speicher.
- Die Homegear-Übernahme liest die Verknüpfungen per `getLinks`.
- Ein quittierter Werksreset entfernt das Gerät auch aus den Verknüpfungen der
  übrigen Geräte. Partner, die es quittiert in ihrer Liste hatten, bekommen
  RemoveLinkPartner (Thermostate gleich, Schläfer beim nächsten Telegramm);
  bis zur Quittung steht das beim Partner unter `ausstehend`.

```yaml
action: eq3_max.link
data:
  device_id: 0123456789abcdef0123456789abcdef          # z. B. Fensterkontakt
  partner_device_id: fedcba9876543210fedcba9876543210  # z. B. Heizkörperthermostat
```

## Seite „eQ-3 MAX!“

Eintrag **„eQ-3 MAX!“** in der Seitenleiste (nur für Administratoren, URL `/eq3-max`); die
Geräteseiten des Funkmoduls und der Geräte verlinken mit „Besuchen“ dorthin
(`configuration_url`). Die Seite ist ein Custom Panel ohne Build-Schritt und ohne
Fremdbibliotheken (`custom_components/eq3_max/frontend/eq3-max-panel.js`, ausgeliefert unter
`/eq3_max_static/`, Cache-Buster aus Version und Inhalt); sie folgt dem hellen bzw. dunklen
HA-Design und passt sich schmalen Bildschirmen an.

- **Kopfzeile je Funkmodul:** verbunden/getrennt, Verbindung (USB-Pfad bzw. `host:port`),
  Sendezeit der letzten Stunde als Balken gegen 36 s, Warteschlange, Knopf
  „Anlernen (60 s)“ mit Countdown (nur bei verbundenem Funkmodul).
- **Gerätekarten nach HA-Bereich** („Ohne Bereich“ zuletzt): Ist → Soll und Modus bzw.
  Preset, Ventilbalken (Heizkörperthermostat), offen/geschlossen (Fensterkontakt),
  Batterie, RSSI, „zuletzt gemeldet“, Zahl der Verknüpfungen; Markierungen „ausstehend“,
  „nicht quittiert“, „Funkfehler“, „Batterie schwach“.
- **Seitenfenster** (Klick auf eine Karte), Reiter **Verknüpfungen:** Partner mit Zustand
  (verknüpft, ausstehend, wartet auf Gerät, fehlgeschlagen, abgelehnt, einseitig) und dem
  Text des Sensors `…_verknuepfungen`, „Lösen“ je Partner, „Erneut senden“ bei
  fehlgeschlagenen, „Partner hinzufügen“ mit nur den Geräten, die der Dienst `link`
  annehmen würde. Bei Fensterkontakten und Tastern der Hinweis, das Fenster einmal zu
  öffnen und zu schließen bzw. den Taster zu drücken.
- Reiter **Konfiguration** (Heizkörper- und Wandthermostat): je Satz („Temperaturen“,
  beim Heizkörperthermostat zusätzlich „Ventil“) ein Formular auf dem Raster der
  Integration, je Wert Quelle (Homegear / Werksvorgabe / gesetzt) und ggf. „ausstehend“ –
  nur bei Werten, die vom quittierten abweichen (gesendet wird immer der ganze Satz; dass
  er unterwegs ist, zeigt „Satz ausstehend“).
  Beliebig viele Werte ändern, dann **„Satz senden“**: Vor dem Senden listet die Seite die
  Änderungen und die angenommenen Werksvorgaben, die mitgehen; gesendet wird **ein**
  Telegramm mit dem ganzen Satz.
- Die Seite aktualisiert sich selbst (Push, entprellt 250 ms); während man tippt, wartet
  die Aktualisierung, bis das Feld verlassen wird.

WebSocket-Befehle (alle nur für Administratoren; Fehler mit deutschem Text):

| Befehl | Daten | Wirkung |
|---|---|---|
| `eq3_max/overview` | – | Funkmodule, Geräte, Bereiche, Verknüpfungen, Konfiguration |
| `eq3_max/subscribe` | – | Ereignis `{"type": "update"}` nach Änderungen |
| `eq3_max/link`, `eq3_max/unlink` | `device_id`, `partner_device_id` | wie die Dienste `link`/`unlink` |
| `eq3_max/pair` | `entry_id` | Anlernen 60 s öffnen |
| `eq3_max/set_config` | `device_id`, `kind` (`temp`/`valve`), `values` | ganzer Satz in einem Telegramm; Antwort `factory_keys` = mitgesendete Werksvorgaben |

## Dienste

- `eq3_max.set_away` – Thermostate bis zu einem Zeitpunkt auf eine Temperatur
  setzen (MAX!-Modus temporär, danach zurück in Auto). Ohne `temperature` gilt
  die Urlaubstemperatur aus den Optionen; das Ende wird auf die nächste halbe
  Stunde aufgerundet und muss in der Zukunft liegen. Das Preset „Abwesend“
  macht dasselbe mit der Urlaubsdauer aus den Optionen (Standard 18,0 °C, 24 h).
- `eq3_max.factory_reset` – Gerät per Funk auf Werkseinstellungen zurücksetzen.
  Nur wenn es quittiert, wird es aus der Integration entfernt; danach neu
  anlernen. Ohne Quittung kann es trotzdem zurückgesetzt sein – dann per
  „Gerät löschen“ entfernen. Nur vergessen (ohne Funk) geht über „Gerät löschen“ auf der
  Geräteseite.
- `eq3_max.link` / `eq3_max.unlink` – zwei Geräte verknüpfen bzw. die
  Verknüpfung lösen, siehe „Verknüpfungen“.

```yaml
action: eq3_max.set_away
target:
  entity_id: climate.ht_bad_unten
data:
  temperature: 16
  until: "2026-10-12 18:00:00"
```

```yaml
action: eq3_max.factory_reset
data:
  device_id: 0123456789abcdef0123456789abcdef
```

## Installation

Voraussetzung: Home Assistant 2026.8 oder neuer.

`custom_components/eq3_max` nach `/config/custom_components/` kopieren, Home Assistant
neu starten, Integration „eQ-3 MAX!“ hinzufügen.

Über HACS: dieses Repository unter HACS → Benutzerdefinierte Repositories mit der
Kategorie „Integration“ hinzufügen, „eQ-3 MAX!“ herunterladen, Home Assistant neu starten.

Umstieg von Homegear oder von `max_cul`: siehe `website/umstieg/`.

### Umstieg von `max_cul`

1. Frischen Export (Format wie bei `tools/homegear_export.py`) als
   `/config/eq3_max_export.json` ablegen.
2. `custom_components/max_cul` entfernen, `custom_components/eq3_max` einspielen,
   Home Assistant neu starten. Der alte Eintrag lädt dann nicht mehr, seine
   Entitäten bleiben in der Registry.
3. „eQ-3 MAX!“ per Einrichtungsdialog mit dem Export hinzufügen. Die Entitäten
   von `max_cul` werden mit gleicher entity_id, Bereich, Name und Einstellungen
   übernommen. Solange `max_cul` noch geladen ist, bricht die Einrichtung mit
   einer Reparaturmeldung ab.
4. Danach den alten Eintrag „MAX! CUL“ löschen. Die Hub-Entitäten heißen jetzt
   `binary_sensor.eq3_max_verbunden`, `sensor.eq3_max_sendezeit_1h`,
   `sensor.eq3_max_warteschlange` und `button.eq3_max_anlernen`.

## Entwicklung

    uv venv -p 3.14 .venv && uv pip install -p .venv -r requirements_test.txt
    .venv/bin/pytest


## Lizenz und Hinweise

MIT-Lizenz, siehe [LICENSE](LICENSE).

eq3_max ist ein privates Projekt und nicht mit der eQ-3 AG verbunden. „eQ-3“, „MAX!“ und
„Homematic“ sind Marken ihrer Inhaber und werden nur beschreibend verwendet.

Funkrecht: Im 868-MHz-Band darf jeder Sender höchstens 1 % der Zeit senden (36 s pro Stunde).
eq3_max misst die Sendezeit und hält die Grenze mit der Bremse ein (bei neuen Einträgen an).
Wer sie abschaltet, ist selbst für die Einhaltung verantwortlich.

Anregungen und Protokollwissen stammen aus [FHEM](https://fhem.de) (10_MAX.pm, 14_CUL_MAX.pm),
[Homegear](https://homegear.eu), [culfw](http://culfw.de)/a-culfw und dem Projekt
[maxcul](https://github.com/powerpaul17/maxcul). Code daraus enthält eq3_max nicht.

