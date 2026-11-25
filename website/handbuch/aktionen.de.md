# Aktionen und Automationen

Alles, was sich aus Automationen, Skripten und den Entwicklerwerkzeugen mit eq3_max machen
lässt: die Aktionen der Integration, die Standard-Aktionen von Home Assistant an
MAX!-Geräten, die Einstell-Entitäten und die Auslöser. Am Ende stehen fertige Beispiele.

Ausprobieren lässt sich jede Aktion unter **Entwicklerwerkzeuge → Aktionen**. Wer gerade
keine Geräte-ID zur Hand hat: Im visuellen Editor das Gerät auswählen und dann auf
„In YAML bearbeiten“ wechseln – dort steht die ID.

## Überblick

| Aktion | Wofür | Wer darf | Wartet auf das Gerät |
|---|---|---|---|
| [`climate.set_temperature`](#climateset_temperature) | Sollwert, optional mit Modus | alle | nein |
| [`climate.set_hvac_mode`](#climateset_hvac_mode) | Heizbetrieb, Automatik, Aus | alle | nein |
| [`climate.set_preset_mode`](#climateset_preset_mode) | Komfort, Eco, Boost, Abwesend, keins | alle | nein |
| [`climate.turn_on` / `turn_off`](#climateturn_on-und-climateturn_off) | Heizbetrieb bzw. Aus | alle | nein |
| [`eq3_max.set_away`](#eq3_maxset_away) | feste Temperatur bis zu einem Zeitpunkt | alle | nein |
| [`eq3_max.set_week_profile`](#eq3_maxset_week_profile) | Wochenprogramm schreiben | Option¹ | **ja** |
| [`eq3_max.copy_week_profile`](#eq3_maxcopy_week_profile) | Wochenprogramm kopieren | Option¹ | **ja** |
| [`eq3_max.set_time`](#eq3_maxset_time) | Uhr der Thermostate stellen | alle | **ja** |
| [`eq3_max.link`](#eq3_maxlink) | Geräte verknüpfen | Admins | nein |
| [`eq3_max.unlink`](#eq3_maxunlink) | Verknüpfung lösen | Admins | nein |
| [`eq3_max.cancel_link`](#eq3_maxcancel_link) | offenen Verknüpfungsauftrag verwerfen | Admins | – (sendet nichts) |
| [`eq3_max.factory_reset`](#eq3_maxfactory_reset) | Werksreset, Gerät entfernen | Admins | **ja** |
| [`number.set_value` / `select.select_option`](#einstell-entitaten) | Gerätekonfiguration | Option² | nein |
| [`select.select_option` (Funkmodul)](#funkmodul-wechseln) | Gerät einem Funkmodul zuordnen | Admins | nein |
| [`button.press` (Anlernen)](#anlernen) | Anlernfenster 60 s öffnen | Admins | nein |

¹ „Benutzer ohne Admin-Rechte dürfen Wochenprogramme ändern“, ² „… Geräteeinstellungen ändern“
(beide Vorgabe an). Automationen, die durch ihren Auslöser laufen, dürfen immer alles; Näheres
unter [Wer darf was](dienste.md#wer-darf-was-ab-080).

**„Wartet nicht auf das Gerät“** heißt: Die Aktion stellt den Befehl in die Warteschlange und
kehrt sofort zurück. Das Thermostat quittiert ihn Sekunden später; bis dahin steht der Wert im
Attribut `ausstehend`. Kommt keine Quittung, wird bis zu dreimal wiederholt, danach geht
`binary_sensor.…_funkfehler` an, und der Befehl geht bei der nächsten Meldung des Geräts noch
einmal hinaus (siehe [Befehle und Quittungen](bedienung.md#befehle-und-quittungen)). Ein Fehler
der Aktion selbst kommt nur bei ungültigen Eingaben oder fehlenden Rechten.

**„Wartet auf das Gerät“** heißt: Die Aktion endet erst, wenn jedes genannte Gerät quittiert
hat, und meldet einen Fehler, wenn es ablehnt oder nicht antwortet. Eine Automation steht so
lange – beim Wochenprogramm können das bei knapper Sendezeit Minuten sein.

## Thermostat steuern

Alle Aktionen dieses Abschnitts nehmen als Ziel eine `climate`-Entität von eq3_max
(Heizkörper- oder Wandthermostat, auch ein virtuelles Wandthermostat).

### `climate.set_temperature`

| Feld | Pflicht | Werte |
|---|---|---|
| `temperature` | ja (außer mit `hvac_mode` allein) | 4,5 bis 30,5 °C in 0,5-Schritten; 4,5 = aus, 30,5 = ganz auf |
| `hvac_mode` | nein | `heat`, `auto`, `off` |

Was passiert, hängt vom Modus ab:

| Aufruf | Wirkung am Thermostat |
|---|---|
| nur `temperature`, Thermostat in **Automatik** | gilt bis zum nächsten Schaltpunkt, dann wieder das Programm |
| nur `temperature`, Thermostat in **Heizbetrieb** | gilt dauerhaft |
| nur `temperature`, Thermostat in **Abwesend** | beendet Abwesend, gilt dauerhaft |
| `temperature` + `hvac_mode: heat` | dauerhaft, schaltet auf Heizbetrieb |
| `temperature` + `hvac_mode: auto` | zurück ins Programm, die Temperatur hält bis zum nächsten Schaltpunkt |
| `hvac_mode: off` (mit oder ohne Temperatur) | Aus (4,5 °C) |

```yaml
action: climate.set_temperature
target:
  entity_id: climate.ht_wohnzimmer
data:
  temperature: 21.5
  hvac_mode: heat
```

Mehrere schnelle Aufrufe an dasselbe Thermostat senden nur den letzten Stand. Eine Änderung in
Automatik, die bis zum Schaltpunkt nicht quittiert ist, verfällt; das Thermostat folgt dann
seinem Programm.

### `climate.set_hvac_mode`

| `hvac_mode` | Wirkung |
|---|---|
| `heat` | Heizbetrieb mit dem aktuellen Sollwert; kommt das Thermostat aus Aus, Abwesend oder Boost, mit dem zuletzt manuell eingestellten Wert |
| `auto` | Automatik: das Thermostat folgt seinem Wochenprogramm |
| `off` | Aus (manuell 4,5 °C, Frostschutz) |

Ein virtuelles Wandthermostat bietet `auto` erst an, wenn ihm ein vollständiges Wochenprogramm
geschrieben wurde.

```yaml
action: climate.set_hvac_mode
target:
  entity_id: climate.ht_wohnzimmer
data:
  hvac_mode: auto
```

### `climate.set_preset_mode`

| `preset_mode` | Wirkung |
|---|---|
| `comfort` | Komforttemperatur aus der Gerätekonfiguration; in Automatik bis zum nächsten Schaltpunkt |
| `eco` | Eco-Temperatur aus der Gerätekonfiguration; in Automatik bis zum nächsten Schaltpunkt |
| `boost` | Ventil für die Boost-Dauer weit auf, danach zurück |
| `away` | Abwesend-Temperatur aus den Optionen für die Abwesend-Dauer (Vorgabe 18 °C, 24 h) |
| `none` | beendet Abwesend oder Boost (zurück zum letzten manuellen Wert); in Automatik zurück zum reinen Programm |

```yaml
action: climate.set_preset_mode
target:
  entity_id: climate.ht_bad
data:
  preset_mode: boost
```

Ohne bekannte Komfort- bzw. Eco-Temperatur meldet `comfort`/`eco` „Ungültiger Wert“; dann
einmal die Werte unter [Gerätekonfiguration](konfiguration.md) setzen.

### `climate.turn_on` und `climate.turn_off`

`turn_off` ist `hvac_mode: off`, `turn_on` ist `hvac_mode: heat` (siehe oben).

### `eq3_max.set_away`

Feste Temperatur bis zu einem Zeitpunkt, danach kehrt das Thermostat **von selbst** in seinen
vorherigen Modus zurück – auch wenn Home Assistant dann nicht läuft. Gut für Urlaub.

| Feld | Pflicht | Werte |
|---|---|---|
| Ziel | ja | eine oder mehrere `climate`-Entitäten von eq3_max |
| `until` | ja | Datum und Uhrzeit; wird auf die nächste volle oder halbe Stunde **aufgerundet** und muss danach in der Zukunft liegen |
| `temperature` | nein | 4,5 bis 30,5 °C; ohne Angabe die Abwesend-Temperatur aus den Optionen |

```yaml
action: eq3_max.set_away
target:
  entity_id:
    - climate.ht_wohnzimmer
    - climate.ht_kueche
data:
  temperature: 16
  until: "2026-12-27 18:00:00"
```

Das Attribut `bis` des Thermostats zeigt die Endzeit, sobald das Gerät sie meldet. Vorzeitig
beenden: `climate.set_preset_mode` mit `none` oder `climate.set_hvac_mode` mit `heat`/`auto`.

## Wochenprogramm und Uhr

### `eq3_max.set_week_profile`

Schreibt ganze Tage des Wochenprogramms auf ein oder mehrere Thermostate. Das Gerät folgt dem
Programm im Modus **Automatik**.

| Feld | Pflicht | Werte |
|---|---|---|
| `device_id` | ja | ein oder mehrere Thermostate (Heizkörper, Wand, virtuelles Wandthermostat) |
| `weekday` | ja | ein oder mehrere Tage: `Samstag` … `Freitag` oder englisch `saturday` … `friday`, oder `alle`/`all`; Groß- und Kleinschreibung egal |
| `profile` | ja | 1 bis 13 Punkte `{temperature, until}`; jeder gilt **bis** zu seiner Uhrzeit |
| `force` | nein | `true`: auch Tage schreiben, die das Gerät schon genau so hat |

Regeln für `profile`:

- `until` im Format `hh:mm`, in 5-Minuten-Schritten, aufsteigend; beim letzten Punkt weglassen
  oder `24:00` (er gilt bis Mitternacht).
- `temperature` 4,5 bis 30,5 °C in 0,5-Schritten.
- Eine Uhrzeit ohne Anführungszeichen (`until: 06:00`) liest YAML als Zahl; das geht auch.

```yaml
action: eq3_max.set_week_profile
data:
  device_id: <Wandthermostat Wohnzimmer>
  weekday: [Montag, Dienstag, Mittwoch, Donnerstag, Freitag]
  profile:
    - {temperature: 17, until: "06:00"}
    - {temperature: 21, until: "08:30"}
    - {temperature: 18, until: "16:00"}
    - {temperature: 21, until: "22:30"}
    - {temperature: 17}
```

Gut zu wissen:

- **Der ganze Raum bekommt das Programm.** Ist das Thermostat über ein Wandthermostat
  verknüpft, schreibt die Integration dieselben Tage auch auf die übrigen Thermostate des
  Raums. Die Aktion wartet auf die genannten Geräte, die übrigen laufen daneben.
- **Unveränderte Tage gehen nicht noch einmal hinaus.** Hat ein Gerät einen Tag schon genau so
  quittiert, wird er ausgelassen. `force: true` schreibt trotzdem alles, etwa wenn das Programm
  am Gerät selbst geändert wurde.
- **Es kann dauern.** Je Tag ein oder zwei Telegramme (ab acht Punkten zwei). Am nanoCUL reicht
  die Sendezeit am Stück für wenige Tage; danach wartet jedes Telegramm rund zwei Minuten, eine
  ganze Woche dauert eine Viertelstunde und mehr. Das Schreiben läuft weiter, auch wenn die
  Automation nicht mehr wartet; den Stand zeigt die Seite „eQ-3 MAX!“ im Reiter
  „Wochenprogramm“ und das Attribut `wochenprogramm_schreibt`.
- **Solange ein Schreiben läuft**, wird ein zweites für dasselbe Thermostat abgelehnt
  („Wochenprogramm wird gerade geschrieben“).
- Ein Neustart von Home Assistant bricht ab; die fehlenden Tage dann noch einmal schreiben.

Mögliche Fehlermeldungen: „Wochenprogramm *Tag* abgelehnt“, „… nicht quittiert“,
„Wochenprogramm wird gerade geschrieben“, „Nur Thermostate haben ein Wochenprogramm“ sowie die
Meldungen zu ungültigen Punkten (Anzahl, Temperatur, Uhrzeit, Reihenfolge).

#### Programm „löschen“

Ein Thermostat hat immer ein Programm; löschen heißt ein neues schreiben. Werksprogramm:

```yaml
- action: eq3_max.set_week_profile
  data:
    device_id: <Thermostat>
    weekday: [Montag, Dienstag, Mittwoch, Donnerstag, Freitag]
    profile:
      - {temperature: 17, until: "06:00"}
      - {temperature: 21, until: "09:00"}
      - {temperature: 17, until: "17:00"}
      - {temperature: 21, until: "23:00"}
      - {temperature: 17}
- action: eq3_max.set_week_profile
  data:
    device_id: <Thermostat>
    weekday: [Samstag, Sonntag]
    profile:
      - {temperature: 17, until: "06:00"}
      - {temperature: 21, until: "22:00"}
      - {temperature: 17}
```

Feste Temperatur rund um die Uhr: `weekday: alle` und `profile: [{temperature: 17}]`. Auf der
Seite „eQ-3 MAX!“ gibt es dafür die Knöpfe „Werksprogramm schreiben“ und „Feste Temperatur
schreiben“.

### `eq3_max.copy_week_profile`

Schreibt das gespeicherte Programm eines Thermostats (seine zuletzt quittierten Tage) auf andere.

| Feld | Pflicht | Werte |
|---|---|---|
| `device_id` | ja | Quelle, ein Thermostat |
| `target_device_id` | ja | ein oder mehrere Ziele |

```yaml
action: eq3_max.copy_week_profile
data:
  device_id: <Thermostat Wohnzimmer>
  target_device_id:
    - <Thermostat Esszimmer>
    - <Thermostat Küche>
```

Die Geräte melden ihr Programm nicht; die Integration kennt nur, was sie selbst geschrieben hat.
Ein Programm, das nur im Gerät steht (am Gerät eingestellt, vom Cube oder aus Homegear), lässt
sich nicht kopieren („Für … ist kein Wochenprogramm gespeichert“). Wie bei `set_week_profile`
bekommt der ganze Raum eines Ziels das Programm, und unveränderte Tage werden ausgelassen.

### `eq3_max.set_time`

Stellt die Uhr von Thermostaten auf die Ortszeit von Home Assistant und wartet auf jede
Quittung.

| Feld | Pflicht | Werte |
|---|---|---|
| `device_id` | ja | ein oder mehrere Heizkörper- oder Wandthermostate |

```yaml
action: eq3_max.set_time
data:
  device_id:
    - <Thermostat>
```

Im Betrieb holen sich die Geräte die Zeit gelegentlich selbst, und eine abweichende Uhr eines
Wandthermostats korrigiert die Integration von selbst. Die Aktion ist für den Fall, dass eine
Uhr trotzdem falsch geht. Fensterkontakte und Eco-Taster haben keine Uhr.

## Verknüpfungen

Verknüpfte Geräte sprechen **direkt per Funk** miteinander, auch wenn Home Assistant nicht
läuft. Hintergrund und Zustände: [Verknüpfungen](verknuepfungen.md).

Die Aktionen stellen einen Auftrag ein und kehren sofort zurück. Den Fortschritt zeigt
`sensor.<gerät>_verknuepfungen` (Zustand: Zahl der fertigen Verknüpfungen; Attribute
`partner` und `ausstehend`). **Fensterkontakte und Eco-Taster schlafen**: Ein Auftrag an sie
wartet, bis sie sich melden – Fenster öffnen und schließen, Taster drücken oder kurz die
Anlerntaste.

### `eq3_max.link`

| Feld | Pflicht | Werte |
|---|---|---|
| `device_id` | ja | ein Gerät |
| `partner_device_id` | ja | das andere Gerät (am selben Funkmodul-Eintrag) |

```yaml
action: eq3_max.link
data:
  device_id: <Fensterkontakt Bad>
  partner_device_id: <Thermostat Bad>
```

Erlaubt sind:

| Gerät | lässt sich verknüpfen mit |
|---|---|
| Heizkörperthermostat | Heizkörperthermostat, Wandthermostat, Fensterkontakt, Eco-Taster |
| Wandthermostat | Heizkörperthermostat, Fensterkontakt, Eco-Taster |
| Fensterkontakt, Eco-Taster | Heizkörperthermostat, Wandthermostat |

Ein Heizkörperthermostat hat höchstens ein Wandthermostat. Fehler: „Diese Geräte lassen
sich nicht verknüpfen“, „bereits verknüpft“, „bereits beauftragt“, „Dieses Thermostat hat
bereits ein Wandthermostat“.

### `eq3_max.unlink`

| Feld | Pflicht | Werte |
|---|---|---|
| `device_id` | ja | ein Gerät |
| `partner_device_id` | ja | der Partner |
| `force` | nein | `true`: nur an `device_id` löschen, der Partner bekommt nichts; auch für Partner, die die Integration nicht als verknüpft kennt |

```yaml
action: eq3_max.unlink
data:
  device_id: <Thermostat>
  partner_device_id: <alter Fensterkontakt>
  force: true
```

`force` ist für Altlasten: ein Gerät trägt noch einen Partner, der getauscht wurde oder die
Verknüpfung nicht mehr kennt (Anzeichen: Funkfehler bei jeder Änderung, Kontakt wiederholt
minutenlang).

### `eq3_max.cancel_link`

Verwirft offene oder fehlgeschlagene Aufträge eines Geräts, **ohne etwas zu senden**.

| Feld | Pflicht | Werte |
|---|---|---|
| `device_id` | ja | das Gerät mit dem Auftrag |
| `partner` | nein | Seriennummer oder Geräte-ID des Partners; leer: alle Aufträge des Geräts |

```yaml
action: eq3_max.cancel_link
data:
  device_id: <Thermostat>
  partner: MEQ0000001
```

## Gerät zurücksetzen

### `eq3_max.factory_reset`

Setzt ein Gerät auf Werkseinstellungen zurück und entfernt es aus der Integration. Danach muss
es neu angelernt werden; seine Verknüpfungen lösen sich auch bei den Partnern.

| Feld | Pflicht | Werte |
|---|---|---|
| `device_id` | ja | ein MAX!-Gerät (nicht das Funkmodul) |

```yaml
action: eq3_max.factory_reset
data:
  device_id: <Gerät>
```

Die Aktion wartet auf die Quittung. „Werksreset nicht gesendet“: Funkmodul nicht verbunden oder
das Gerät hat sich nicht rechtzeitig gemeldet. „… nicht quittiert – eventuell trotzdem
zurückgesetzt“: am Gerät nachsehen (Anzeige „rES“ bzw. Anlernbereitschaft).

!!! danger "Nur bewusst verwenden"
    Ein Werksreset lässt sich nicht rückgängig machen. Gerät nur aus Home Assistant entfernen,
    ohne Funkbefehl: Geräteseite → „Gerät löschen“.

## Einstell-Entitäten

Die Gerätekonfiguration steht als `number`- und `select`-Entitäten am Gerät (Liste unter
[Gerätekonfiguration](konfiguration.md)). Aus Automationen setzt man sie mit den
Standard-Aktionen:

```yaml
action: number.set_value
target:
  entity_id: number.ht_wohnzimmer_eco
data:
  value: 17
```

```yaml
action: select.select_option
target:
  entity_id: select.ht_wohnzimmer_boost_dauer
data:
  option: "10 min"
```

| Entität | Werte |
|---|---|
| `number.…_komfort`, `_eco`, `_maximal`, `_minimal`, `_fenster_temperatur` | 4,5 bis 30,5 °C, Schritt 0,5 |
| `number.…_offset` | −3,5 bis +3,5 K, Schritt 0,5 |
| `number.…_fenster_dauer` | 0 bis 60 min, Schritt 5 (0 = eigene Fenster-Erkennung aus) |
| `number.…_boost_ventil` | 0 bis 100 %, Schritt 5 |
| `number.…_ventil_max`, `_ventil_offset` | 0 bis 100 %, Schritt 1 |
| `number.…_entkalkung_stunde` | 0 bis 23 |
| `select.…_boost_dauer` | `0 min`, `5 min` … `30 min`, `60 min` |
| `select.…_entkalkung_tag` | `saturday` … `friday` (angezeigt als Samstag … Freitag) |
| `select.…_anzeige` | `setpoint` (Soll) oder `actual` (Ist), nur Wandthermostat |
| `select.…_ist_abfragen` | `off`, `15`, `30`, `60`, `120`, `240` (Minuten), nur Heizkörper |

- Jede Änderung sendet den ganzen Satz des Geräts (alle Temperaturen bzw. alle Ventilwerte).
- **Raumwerte** (Komfort, Eco, Grenzen, Fenster, Boost, Entkalkung) übernimmt die Integration
  auch an den übrigen Thermostaten des Raums.
- Werte außerhalb des Rasters werden abgelehnt („Wert muss zwischen … in Schritten von …
  liegen“); 21,3 °C geht nicht.
- Die Geräte melden ihre Einstellungen nicht zurück: Die Entität zeigt den zuletzt quittierten
  Wert, das Attribut `quelle` woher er stammt.

### Funkmodul wechseln

Mit mehreren Funkmodulen hat jedes Gerät `select.<gerät>_funkmodul`. Die Option ist der Name
des Moduls; die Attribute `rssi_<modul>` zeigen, wie gut jedes Modul das Gerät hört.

```yaml
action: select.select_option
target:
  entity_id: select.ht_bad_oben_funkmodul
data:
  option: Obergeschoss
```

### Anlernen

`button.eq3_max_anlernen` öffnet das Anlernfenster für 60 Sekunden – wie der Knopf auf der Seite
„eQ-3 MAX!“.

```yaml
action: button.press
target:
  entity_id: button.eq3_max_anlernen
```

## Auslöser und Zustände

Was sich als Auslöser oder Bedingung eignet:

| Entität | Zustand / Ereignis | Typische Verwendung |
|---|---|---|
| `event.<taster>` | Ereignistyp `auto` oder `eco` | Eco-Taster schaltet etwas anderes, z. B. Licht |
| `binary_sensor.<fk>_state` | `on` = offen | Fenster lange offen → Benachrichtigung |
| `binary_sensor.<gerät>_lowbat` | `on` = Batterie schwach | Batteriewechsel erinnern |
| `binary_sensor.<gerät>_funkfehler` | `on` = Funkfehler oder Befehl nicht quittiert | Störung melden |
| `sensor.<gerät>_zuletzt_gemeldet` | Zeitpunkt | Gerät meldet sich nicht mehr |
| `sensor.<ht>_ventil` | Ventilöffnung in % | Wärmebedarf an den Kessel geben |
| `climate.<thermostat>` | Modus, Attribute `temperature`, `current_temperature`, `preset_mode` | Raumtemperatur, Sollwert |
| `binary_sensor.eq3_max_verbunden` | `off` = ein Funkmodul getrennt | Ausfall melden |
| `sensor.eq3_max_sendezeit_1h` | Sendezeit der letzten Stunde in s | Grenze 36 s überwachen |

**Attribute des Thermostats**, nützlich in Vorlagen:

| Attribut | Inhalt |
|---|---|
| `ausstehend`, `ausstehend_modus` | gesendeter, noch nicht quittierter Sollwert und Modus |
| `bis` | Endzeit von Abwesend |
| `valve` | Ventilöffnung (nur Heizkörper) |
| `id` | Seriennummer |
| `fenster` | verknüpfte Fensterkontakte des Geräts und seines Raums (Entitäts-IDs) |
| `raum` | die anderen Thermostate des Raums |
| `wochenprogramm` | das gespeicherte Programm je Wochentag |
| `wochenprogramm_schreibt`, `wochenprogramm_fehler` | Tage, die gerade geschrieben werden, und der Grund eines Abbruchs |

**Eco-Taster:** Jeder Tastendruck erzeugt genau ein Ereignis; Wiederholungen des Geräts werden
herausgefiltert. Der Taster schaltet seine verknüpften Thermostate trotzdem selbst um – die
Automation kommt zusätzlich dazu.

## Beispiele

### Urlaub für alle Räume

```yaml
alias: Heizung Urlaub
triggers:
  - trigger: state
    entity_id: input_boolean.urlaub
    to: "on"
actions:
  - action: eq3_max.set_away
    target:
      entity_id: all
    data:
      temperature: 15
      until: "{{ states('input_datetime.urlaub_ende') }}"
```

`entity_id: all` erfasst alle `climate`-Entitäten von eq3_max (die Aktion gehört der
Integration). Die Thermostate kehren zur Endzeit von selbst zurück.

### Eco-Taster schaltet zusätzlich das Licht

```yaml
alias: Eco-Taster Flur
triggers:
  - trigger: state
    entity_id: event.taster_flur
actions:
  - choose:
      - conditions: "{{ trigger.to_state.attributes.event_type == 'eco' }}"
        sequence:
          - action: light.turn_off
            target:
              area_id: flur
      - conditions: "{{ trigger.to_state.attributes.event_type == 'auto' }}"
        sequence:
          - action: light.turn_on
            target:
              area_id: flur
```

### Fenster seit 15 Minuten offen

```yaml
alias: Fenster offen erinnern
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.fk_bad_state
      - binary_sensor.fk_kueche_state
    to: "on"
    for: "00:15:00"
actions:
  - action: notify.notify
    data:
      message: "{{ trigger.to_state.name }} ist seit 15 Minuten offen."
```

Das Thermostat regelt bei offenem Fenster schon selbst herunter; die Automation ist nur die
Erinnerung.

### Winter- und Sommerprogramm

```yaml
alias: Sommerprogramm
triggers:
  - trigger: state
    entity_id: input_boolean.sommer
    to: "on"
actions:
  - action: eq3_max.set_week_profile
    data:
      device_id:
        - <Wandthermostat Wohnzimmer>
        - <Thermostat Bad>
      weekday: alle
      profile:
        - {temperature: 4.5}
```

`4.5` ist „aus“. Das Winterprogramm schreibt man umgekehrt zurück. Weil die Aktion auf die
Geräte wartet, läuft so eine Automation einige Minuten; Schritte danach kommen erst dann dran.

### Batterien schwach

```yaml
alias: MAX!-Batterie schwach
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.ht_wohnzimmer_lowbat
      - binary_sensor.fk_bad_lowbat
    to: "on"
actions:
  - action: notify.notify
    data:
      message: "Batterie schwach: {{ trigger.to_state.name }}"
```

## Wenn etwas nicht klappt

- **„Das dürfen nur Administratoren“ / „… dürfen nur Administratoren ändern (Option der
  Integration)“:** Ein Benutzer ohne Admin-Rechte hat die Aktion ausgelöst (auch per Knopf
  im Dashboard). Läuft die Automation durch ihren Auslöser, gilt das nicht.
- **„Funkmodul nicht verbunden“:** Das Modul des Geräts ist getrennt; die Seite „eQ-3 MAX!“ zeigt
  welches.
- **Wert kommt nicht an, `funkfehler` an:** Gerät außer Reichweite, Batterie, oder die
  Sendezeit ist aufgebraucht (Seite „eQ-3 MAX!“: „wartet auf Sendezeit“). Der Befehl wird
  wiederholt, sobald sich das Gerät meldet.
- **Die Automation hängt:** `set_week_profile`, `copy_week_profile`, `set_time` und
  `factory_reset` warten auf das Gerät. Bei knapper Sendezeit dauert das; mit
  `continue_on_error: true` läuft die Automation bei einem Fehler weiter.
