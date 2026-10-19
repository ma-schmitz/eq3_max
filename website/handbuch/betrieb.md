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
| max_cul noch aktiv | alte Integration entfernen, neu starten |

## Diagnose

Geräteseite des Funkmoduls → „Diagnose herunterladen“: Verbindungsart und -ziel, Stick-Version, Verbindung, Sendezeit,
Warteschlange, alle Gerätezustände und die letzten Rohtelegramme je Gerät.

## Grenzen

- Wochenprogramme der Geräte werden nicht bearbeitet (Planung macht HA).
- Konfiguration wird nicht vom Gerät gelesen (die Geräte können das nicht).
- CUL über Netzwerk (CUN, geflashter Cube per LAN) ist noch nicht offiziell unterstützt.
