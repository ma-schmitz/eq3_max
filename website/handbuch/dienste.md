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
