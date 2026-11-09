# Dienste


## `eq3_max.set_away`

Thermostat bis zu einem Zeitpunkt auf eine feste Temperatur stellen (z. B. Urlaub).

```yaml
action: eq3_max.set_away
target:
  entity_id: climate.ht_wohnzimmer
data:
  temperature: 16
  until: "2026-10-20 18:00:00"
```

`temperature` ist optional (sonst die Abwesend-Temperatur aus den Optionen). `until` muss in
der Zukunft liegen und wird auf :00/:30 aufgerundet.

## `eq3_max.factory_reset`

Setzt ein Gerät auf Werkseinstellungen zurück und entfernt es aus der Integration.

!!! danger "Nur bewusst verwenden"
    Danach muss das Gerät neu angelernt werden.

```yaml
action: eq3_max.factory_reset
data:
  device_id: <Geräte-ID aus der Geräteseite>
```

Antworten: Erfolg → Gerät entfernt. „Werksreset nicht gesendet“ → Stick nicht verbunden oder
30-s-Fenster verstrichen. „nicht quittiert – eventuell trotzdem zurückgesetzt“ → am Gerät
prüfen.

## `eq3_max.set_week_profile`

Schreibt ganze Tage des Wochenprogramms auf ein oder mehrere Thermostate (Heizkörper- oder
Wandthermostat). Das Gerät folgt dem Programm im Modus **Automatik**.

```yaml
action: eq3_max.set_week_profile
data:
  device_id:
    - <Geräte-ID Thermostat>
  weekday:
    - Montag
    - Dienstag
  profile:
    - temperature: 17
      until: "06:00"
    - temperature: 21
      until: "22:00"
    - temperature: 17
```

- `weekday`: ein oder mehrere Wochentage (`Samstag` … `Freitag`) oder `alle`.
- `profile`: bis zu 13 Punkte je Tag, jeder gilt **bis** zu seiner Uhrzeit (5-Minuten-Schritte,
  aufsteigend). Beim letzten Punkt darf `until` fehlen, er gilt bis 24:00. Temperaturen
  4,5 bis 30,5 °C in 0,5-Schritten (4,5 = aus, 30,5 = an).
- Der Dienst wartet auf die Quittungen des Geräts und meldet einen Fehler, wenn es ablehnt
  oder nicht antwortet; die restlichen Tage gehen dann nicht mehr raus. Je Tag sind das ein
  oder zwei Telegramme (ab acht Punkten zwei), eine ganze Woche also 7 bis 14 Telegramme à
  rund 1,2 s Sendezeit. Mit eingeschalteter Sendezeit-Bremse kann das dauern.
- Auslesen kann die Integration das Programm nicht (die Geräte melden es nicht). Sie merkt
  sich die zuletzt quittierten Tage je Gerät; sie stehen in der Diagnose und in der
  Seite „eQ-3 MAX!“ (Datenbasis `week_profile`).

!!! tip "Unquotierte Uhrzeiten"
    YAML liest `until: 06:00` ohne Anführungszeichen als Zahl (360 Minuten). Der Dienst
    nimmt beides.

## `eq3_max.copy_week_profile`

Schreibt das für ein Thermostat gespeicherte Wochenprogramm (seine zuletzt quittierten
Tage) auf andere Thermostate.

```yaml
action: eq3_max.copy_week_profile
data:
  device_id: <Geräte-ID Quelle>
  target_device_id:
    - <Geräte-ID Ziel 1>
    - <Geräte-ID Ziel 2>
```

Die Quelle muss vorher mit `set_week_profile` beschrieben worden sein; ein Programm, das
nur im Gerät steht (Cube, Homegear, am Gerät eingestellt), kennt die Integration nicht.

### Programm „löschen“

Ein Thermostat hat immer ein Programm. Löschen heißt deshalb ein neues schreiben – auf der Seite
„eQ-3 MAX!“ mit den Knöpfen **Werksprogramm schreiben** und **Feste Temperatur schreiben**, per
Dienst so:

```yaml
# Werksprogramm (wie ab Werk): zwei Aufrufe
action: eq3_max.set_week_profile
data:
  device_id: <Geräte-ID>
  weekday: [Montag, Dienstag, Mittwoch, Donnerstag, Freitag]
  profile:
    - {temperature: 17, until: "06:00"}
    - {temperature: 21, until: "09:00"}
    - {temperature: 17, until: "17:00"}
    - {temperature: 21, until: "23:00"}
    - {temperature: 17}
---
action: eq3_max.set_week_profile
data:
  device_id: <Geräte-ID>
  weekday: [Samstag, Sonntag]
  profile:
    - {temperature: 17, until: "06:00"}
    - {temperature: 21, until: "22:00"}
    - {temperature: 17}
```

```yaml
# feste Temperatur den ganzen Tag, jeden Tag
action: eq3_max.set_week_profile
data:
  device_id: <Geräte-ID>
  weekday: alle
  profile:
    - {temperature: 17}
```

## Gerät löschen

Auf der Geräteseite „Gerät löschen“ entfernt ein Gerät nur aus HA (kein Funkbefehl). Sinnvoll
für Geräte, die physisch nicht mehr existieren.

## Optionen

Einstellungen → Geräte & Dienste → eQ-3 MAX! → Konfigurieren. Das Menü bietet
„Einstellungen“ (Tabelle unten), „Verbindung ändern“: USB-Stick oder Netzwerk (CUN,
geflashter Cube, Host und Port, Standard 2323), und „Funkmodule“ (weitere Module, siehe
[Mehrere Funkmodule](funkmodule.md)). Die neue Verbindung wird mit `V` geprüft; eine geänderte Verbindung startet die
Integration neu, die Einstellungen nicht.

| Option | Standard | Bedeutung |
|---|---|---|
| Sendezeit begrenzen | an (neue Einträge) | hält die gesetzliche Grenze von 36 s pro Stunde (1 %) ein; Befehle warten dann ggf. |
| Abwesend-Temperatur | 18,0 °C | für das Preset „Abwesend“ |
| Abwesend-Dauer | 24 h | für das Preset „Abwesend“ |
