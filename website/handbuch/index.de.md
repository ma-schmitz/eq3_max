# Handbuch

Bedienung und Betrieb der Integration „eQ-3 MAX!“ im Alltag.


eq3_max verbindet Home Assistant über einen CUL-Stick oder geflashten Cube direkt per Funk (868 MHz) mit
eQ-3 MAX!-Geräten — ohne Homegear und ohne Cube-Software.

```
Thermostate, Fensterkontakte, Taster  ⇄  Funk 868 MHz  ⇄  Funkmodul (USB/LAN)  ⇄  eq3_max in HA
```

Unterstützte Geräte:

| Gerät | Modell (Beispiel) | in HA |
|---|---|---|
| Heizkörperthermostat | BC-RT-TRX-CyN | Thermostat (`climate`) + Sensoren |
| Wandthermostat | BC-TC-C-WM-2 | Thermostat (`climate`) + Sensoren |
| Fensterkontakt | BC-SC-Rd-WM-2 | Fenster-Sensor (`binary_sensor`) |
| Eco-Taster | BC-PB-2-WM | Ereignis (`event`) |

Jedes Gerät erscheint als eigenes Gerät in HA (mit Logo, Seriennummer, Firmware und
Funkadresse als „Hardware-Version“) und hängt am Gerät **„eQ-3 MAX! Funkmodul“**.

## Entitäten

### Heizkörperthermostat (Beispiel `ht_wohnzimmer`)

| Entität | Bedeutung |
|---|---|
| `climate.ht_wohnzimmer` | Sollwert, Ist-Temperatur, Modus, Preset |
| `sensor.ht_wohnzimmer_ventil` | Ventilöffnung in % |
| `binary_sensor.ht_wohnzimmer_lowbat` | Batterie schwach |
| `sensor.ht_wohnzimmer_rssi` | Empfangsstärke in dBm (Diagnose) |
| `binary_sensor.ht_wohnzimmer_funkfehler` | Gerät meldet Funkfehler **oder** ein Befehl wurde nicht quittiert (Diagnose) |
| `binary_sensor.ht_wohnzimmer_gesperrt` | Bedienung am Gerät gesperrt (Diagnose) |
| `sensor.ht_wohnzimmer_zuletzt_gemeldet` | Zeitpunkt der letzten Meldung (Diagnose) |

**Attribute des Thermostats:**

| Attribut | Bedeutung |
|---|---|
| `valve` | Ventilöffnung (wie der Ventil-Sensor) |
| `id` | Seriennummer |
| `ausstehend` | gesendeter, noch nicht quittierter Sollwert |
| `ausstehend_modus` | Modus des ausstehenden Befehls |
| `bis` | Endzeit im Modus „Abwesend“ (vom Gerät gemeldet) |

### Wandthermostat

Wie der Heizkörperthermostat, aber ohne Ventil.

### Fensterkontakt

`binary_sensor.fk_…_state` (an = offen), dazu Batterie und RSSI. Verknüpfte Fensterkontakte
schalten ihren Thermostat **direkt per Funk** auf die Fenster-auf-Temperatur — das passiert
auch, wenn HA nicht läuft.

### Eco-Taster

`event.<taster>` mit den Ereignistypen `auto` und `eco`.
Jeder Tastendruck erzeugt genau ein Ereignis; vom Gerät wiederholte Telegramme werden
herausgefiltert.

### Funkmodul

| Entität | Bedeutung |
|---|---|
| `binary_sensor.eq3_max_verbunden` | Stick verbunden |
| `sensor.eq3_max_sendezeit_1h` | Sendezeit der letzten Stunde in s (gesetzlich erlaubt: 36 s = 1 %) |
| `sensor.eq3_max_warteschlange` | wartende Befehle |
| `button.eq3_max_anlernen` | öffnet das Anlernfenster für 60 s |
