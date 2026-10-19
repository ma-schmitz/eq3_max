# Umstieg von Homegear

Für Installationen mit **Homegear** und der legacy-Integration **`homematic`** in Home
Assistant. Kein Gerät muss neu angelernt werden, die Entity-IDs bleiben.
Überblick und Voraussetzungen: [Umstieg](index.md).

## Was übernommen wird

| Bisher | In eq3_max |
|---|---|
| Funkadresse der Zentrale | dieselbe Absenderadresse, kein Neuanlernen |
| Seriennummer, Funkadresse, Typ, Firmware | Gerät in HA; Name aus den Homegear-Metadaten, sonst von der alten Entität |
| `climate.<name>` | `climate.<name>`, Verlauf läuft weiter |
| `binary_sensor.<name>_state` (Fensterkontakt) | `binary_sensor.<name>_state` |
| `binary_sensor.<name>_lowbat` | `binary_sensor.<name>_lowbat` |
| Template-Sensor `sensor.<name>_ventil` | `sensor.<name>_ventil`, ersetzt den Template-Eintrag |
| Bereich, Anzeigename, Symbol, Aliase, Labels, „deaktiviert“, „ausgeblendet“ | bleiben erhalten |
| Konfiguration (Komfort, Eco, Maximal, Minimal, Offset, Fenster-auf-Temperatur, Boost, Entkalkung) | `number.*`/`select.*` mit Attribut `quelle: homegear` |
| Verknüpfungen | Verknüpfungen je Gerät, `sensor.<name>_verknuepfungen` |
| `homematic.keypress` der Eco-Taster | `event.<name>` — **Automationen umstellen** (Schritt 7) |

**Nicht übernommen**, weil Homegear sie nicht ausgibt: Fenster-auf-Dauer, Maximalventil,
Ventil-Offset. Sie stehen danach auf Werksvorgabe (`quelle: werksvorgabe`). Wer sie am
Gerät geändert hatte, stellt sie in eq3_max neu ein.

**Neu** sind `sensor.<name>_rssi`, bei Thermostaten `binary_sensor.<name>_funkfehler`,
`…_gesperrt` und `sensor.<name>_zuletzt_gemeldet`, dazu die Funkmodul-Entitäten
`*.eq3_max_*`.

## 1. Vorbereiten (Betrieb läuft weiter) { #vorbereiten }

1. **Zentralen-Adresse ermitteln.** Sie steht als Absender in jedem Telegramm, das Homegear
   sendet. Im Homegear-Log nach `Sending (My-MAX-CUL` suchen (Interfacename aus
   `families/max.conf`):

   ```
   0B 4E 05 40 C0FFEE A1B004 01 66
   Länge Zähler Flags Typ  Quelle  Ziel  Gruppe Nutzlast
   ```

   Hier ist die Adresse also `C0FFEE`.

2. **Geräte exportieren**, solange Homegear läuft:

   ```bash
   python3 tools/homegear_export.py --host <homegear-host> --port 2001 --out eq3_max_export.json
   ```

   Kontrolle: Stimmt die Zahl der Geräte? Haben Wandthermostat und verknüpfte Thermostate
   einen Eintrag `links`?

   Alternativ fragt der Einrichtungsdialog Homegear direkt ab (Quelle „Homegear“). Das geht
   nur, solange Homegear läuft. Die Datei ist der sichere Weg und bleibt für einen zweiten
   Anlauf liegen.

3. **Registry-Trockenlauf.** Jede Seriennummer muss in der Entity-Registry als
   homematic-Eintrag vorkommen (`<SERIAL>` für climate, `<SERIAL>_LOWBAT`, `<SERIAL>_STATE`).
   Fehlende Einträge bekommen später neue IDs.

4. **Namen prüfen.** Liefert Homegear keine Namen, übernimmt eq3_max die Anzeigenamen der
   alten Entitäten. Andere Namen setzt man als `name` in der Exportdatei.

5. **Gruppen** in der Exportdatei auf `0` lassen. eq3_max stellt ohne Gruppe, das klappt auch
   bei Geräten, die Homegear mit Gruppe angesprochen hat.

## 2. Sichern

- HA-Vollsicherung (Einstellungen → System → Sicherungen).
- `/config/.storage/core.entity_registry` kopieren.
- Homegear-Verzeichnis auf dem Host sichern.

## 3. HA-Konfiguration bereinigen

Vorher jeweils eine `.bak`-Kopie anlegen.

- `homematic:`-Block aus `configuration.yaml` entfernen.
- Hilfskonstrukte rund um Homegear entfernen (REST-Sensor „Homematic up“,
  Reconnect-Automationen).
- Template-Sensoren, die Werte aus homematic-Attributen nachbauen (`sensor.<name>_ventil`),
  stilllegen. eq3_max liefert sie mit denselben IDs.
- `check_config` muss fehlerfrei sein.

## 4. Integration einspielen

- `custom_components/eq3_max` nach `/config/custom_components/` kopieren.
- Exportdatei nach `/config/eq3_max_export.json` kopieren.

## 5. Umschalten

1. **Homegear stoppen.** Nur stoppen, nicht löschen (Rückweg), Autostart aus.
2. **Funkmodul anschließen** (siehe [Hardware](../loslegen/hardware.md)):
   - **nanoCUL:** Den Stick von Homegear an die HA-Box umstecken und den Pfad ermitteln:
     `ls -l /dev/serial/by-path/`. Immer `by-path` nehmen, nie `by-id`.
   - **MAX! Cube mit a-culfw:** Cube ins LAN, mit `nc <cube-ip> 2323` und `V` prüfen.
     Homegear kann den Cube nicht nutzen, er ersetzt also den Stick.
3. **HA neu starten.** `homematic` darf danach nicht mehr geladen sein.
4. **Integration hinzufügen:** Einstellungen → Geräte & Dienste → „eQ-3 MAX!“
   - Verbindung: „USB-Stick“ mit dem `by-path`-Eintrag oder „Netzwerk“ mit Cube-IP und
     Port 2323
   - Zentralen-Adresse: die bisherige (z. B. `C0FFEE`), auch beim Cube
   - Quelle: JSON, `/config/eq3_max_export.json`
   - Geräteliste bestätigen

## 6. Abnahme

Der Reihe nach prüfen und notieren:

1. Alle Geräte da, alle Thermostate mit Werten, **keine `_2`-IDs**.
2. Sollwert an einem Thermostat ändern → `ausstehend` ist nach einigen Sekunden leer.
3. Ein Gerät, das Homegear mit Gruppe angesprochen hat, gezielt stellen → nur dieses ändert sich.
4. Fensterkontakt auf/zu → Entität folgt.
5. Eco-Taster drücken → `event.<name>` zeigt `auto` bzw. `eco`.
6. Wandthermostat verstellen → er und die verknüpften Thermostate folgen.
7. Seite **„eQ-3 MAX!“** öffnen → Verknüpfungen wie unter Homegear, Konfiguration mit
   Quelle `homegear`.

## 7. Taster-Automationen umstellen

Aus `homematic.keypress` werden Event-Entitäten:

```yaml
triggers:
  - trigger: state
    entity_id: event.taster
    not_from: unavailable
    not_to: unavailable
```

`not_to: unavailable` verhindert ein Auslösen beim Neuladen der Integration. Die Taste
unterscheidet `trigger.to_state.attributes.event_type` (`auto` oder `eco`).

## 8. Beobachten und aufräumen

- 48 Stunden beobachten: `binary_sensor.*_funkfehler`, `sensor.eq3_max_sendezeit_1h`,
  Log-Warnungen „no ack“.
- Danach den Homegear-Container bzw. -Dienst entfernen.

Die Sendezeit-Bremse (36 s pro Stunde) ist bei neuen Einträgen eingeschaltet; so bleibt es auch bei einer culfw ohne eigene Budgetprüfung bei 1 %.

## Rückweg

!!! tip "Unter 15 Minuten zurück"
    Solange Homegear nur gestoppt und nicht gelöscht ist, geht es so zurück:


    1. Integration „eQ-3 MAX!“ löschen.
    2. Stick zurück an den Homegear-Host, Homegear starten (wer auf den Cube umgestiegen ist,
       braucht dafür den alten Stick). Bei Docker danach einmal neu
       starten, damit der Container das Gerät neu greift.
    3. `.bak`-Dateien zurückspielen, HA neu starten.
    4. Fehlen Bereiche oder Namen: HA stoppen, gesicherte `core.entity_registry` zurückkopieren.

