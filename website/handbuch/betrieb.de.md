# Betrieb und Störungen


## Was man im Blick behalten sollte

- `binary_sensor.*_funkfehler` — einzelne kurze „Problem“-Phasen sind normal (Funkkollision),
  dauerhaft an deutet auf ein unerreichbares Gerät (Batterie, Reichweite).
- `sensor.eq3_max_sendezeit_1h` — normal deutlich unter 36 s.
- `binary_sensor.*_lowbat` — Batterien tauschen.

## Selbstheilung

| Situation | Reaktion der Integration |
|---|---|
| Stick abgezogen / Port weg / Netzwerk-CUL nicht erreichbar | Wiederverbindung alle 30 s; nach 15 min Reparaturmeldung „CUL nicht erreichbar“ |
| Stick empfängt nach dem Senden nichts mehr | Port wird **sofort** neu geöffnet (höchstens einmal je Funkstille), ausstehende Befehle gehen danach erneut raus |
| Ein einzelnes Gerät antwortet nicht, der Funk funktioniert aber (andere Geräte werden gehört) | Gerät gilt als **stumm**: kein weiteres Neuöffnen seinetwegen, Log-Warnung „antwortet nicht … Gerät prüfen“; sein Befehl geht mit seiner nächsten Meldung erneut raus |
| 10 min gesendet, aber nichts empfangen | Wächter öffnet den Port neu; beim zweiten Mal Reparaturmeldung „Stick empfängt nichts“ |
| HA-Neustart | alle Werte sofort wieder da; ausstehende Befehle werden erneut gesendet, abgelaufene „Abwesend“-Befehle verworfen |

Entitäten werden bei einem Ausfall **nicht** „nicht verfügbar“, sondern behalten ihren letzten
Wert — Automationen kippen dadurch nicht.

## Reparaturmeldungen

| Meldung | Bedeutung |
|---|---|
| CUL nicht erreichbar | seit 15 min keine Verbindung zum CUL (Pfad bzw. `host:port` steht in der Meldung) |
| CUL-Stick empfängt nichts | auch nach zwei Neustarts kein Empfang → anderer USB-Port; Netzwerk-CUL stromlos neu starten |
| Homematic-Integration noch aktiv | `homematic:` aus der YAML entfernen, neu starten |

## Diagnose

Geräteseite des Funkmoduls → „Diagnose herunterladen“: Verbindungsart und -ziel, Stick-Version, Verbindung, Sendezeit,
Warteschlange, alle Gerätezustände und die letzten Rohtelegramme je Gerät.

**Telegramm-Trace.** Der Logger `custom_components.eq3_max.trace` schreibt auf Stufe `info`
jede Zeile zum (`-> Zs…`) und vom Funkmodul (`<- Z…`) sowie das Sendefenster schlafender
Geräte ins `home-assistant.log`. Einschalten in der `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.eq3_max: debug
```

oder zur Laufzeit mit dem Dienst `logger.set_level`. Das ist das Log, das bei „Gerät reagiert
nicht“ weiterhilft (etwa ein Fensterkontakt, der seine Verknüpfung nicht annimmt). Bewusst
`info` statt `debug`: Home Assistant OS schreibt keine `debug`-Zeilen in die Logdatei.

## Grenzen

- Wochenprogramme lassen sich schreiben ([Dienste](dienste.md)), aber nicht aus den Geräten
  auslesen; die Integration kennt nur, was sie selbst geschrieben hat.
- Konfiguration wird nicht vom Gerät gelesen (die Geräte können das nicht).
- Ein Wandthermostat verlangt nach einem Batteriewechsel Datum und Uhrzeit am Gerät; in
  dieser Eingabe nimmt es keine Funkantwort an. Seine Funkfehler-Anzeige geht wieder aus,
  sobald es eine Meldung erfolgreich losgeworden ist.
- Beobachtet, Ursache offen: Nach einer neuen Ventilkonfiguration (Boost, Entkalkung,
  Ventilgrenzen) quittierten die Heizkörperthermostate eines Raums die Temperaturmeldungen
  ihres Wandthermostats etwa eine Viertelstunde lang nicht, das Wandthermostat setzte
  Funkfehler. Mit dem nächsten Sollwertwechsel am Wandthermostat lief es wieder.
