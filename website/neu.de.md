# Neu in 0.8.0

Das bisher größte Update: eine eigene Thermostatkarte, mehr Bedienung direkt am Thermostat, und
Funktionen, die bisher nur der MAX! Cube konnte.

![Thermostatkarte](assets/karte/card-kompakt-de-light.png#only-light)
![Thermostatkarte](assets/karte/card-kompakt-de-dark.png#only-dark)

## Thermostatkarte

Eigene Dashboard-Karte in drei Layouts (kompakt, Ring zum Ziehen, Kachel) mit Ventil, Batterie,
Funk und Fenster auf einen Blick – und **Einstellungen samt Wochenprogramm im Pop-up**, ohne das
Dashboard zu verlassen. → [Thermostatkarte](handbuch/karte.md)

## Am Thermostat

| Neu | Wozu | Mehr |
|---|---|---|
| **Presets Komfort und Eco** | ein Klick auf die eingestellte Komfort- bzw. Eco-Temperatur, wie die Tasten am Gerät | [Bedienung](handbuch/bedienung.md#presets) |
| **Anzeige Soll/Ist am Wandthermostat** | das Display zeigt die Ist-Temperatur – am Gerät ist das Menü gesperrt, solange es an einer Zentrale hängt | [Gerätekonfiguration](handbuch/konfiguration.md) |
| **Ist-Temperatur abfragen** | Heizkörper melden ihre Temperatur sonst nur bei Änderungen; eq3_max stößt sie auf Wunsch regelmäßig an – für Verlaufskurven | [Gerätekonfiguration](handbuch/konfiguration.md#ist-temperatur-abfragen-ab-080) |

## Räume

| Neu | Wozu | Mehr |
|---|---|---|
| **Gruppen-ID** | ein Sollwert an den Wandthermostat erreicht den ganzen Raum aus einem Telegramm (gemessen 1–2 min statt 2–5 min) | [Verknüpfungen](handbuch/verknuepfungen.md#gruppen-id-ab-080) |
| **Raumwerte** | Komfort, Eco, Fenster und Boost gelten für alle Thermostate eines Raums | [Gerätekonfiguration](handbuch/konfiguration.md) |

## Sicherheit und Zuverlässigkeit

| Neu | Wozu |
|---|---|
| **Freigaben** | Geräteeinstellungen und Wochenprogramme für Benutzer ohne Admin-Rechte sperrbar; Werksreset, Verknüpfen und Funkmodul nur noch für Admins ([Wer darf was](handbuch/dienste.md#wer-darf-was-ab-080)) |
| **Mehrere Funkmodule senden nicht mehr gleichzeitig** | raumweite Änderungen über zwei Module überlagerten sich und endeten als Funkfehler |
| **Eco-Taster** | eine späte Wiederholung schaltet ein Licht nicht mehr zurück |
| **Erklärtexte** | jeder Einstellwert auf der Seite „eQ-3 MAX!“ und in der Karte hat einen Mouseover-Text und ein ⓘ |

## Erkannt, aber noch nicht gesteuert

- **Zwischenstecker** (BC-TS-Sw-Pl) wird angelernt und angezeigt; Mitschnitte helfen, ihn einzubauen.

Alle Details: [Changelog](changelog.md).
