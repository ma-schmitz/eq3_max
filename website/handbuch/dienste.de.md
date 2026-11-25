# Optionen und Rechte

Alle Aktionen (früher „Dienste“) mit Feldern und Beispielen stehen jetzt unter
[Aktionen und Automationen](aktionen.md).

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
| Benutzer ohne Admin-Rechte dürfen Geräteeinstellungen ändern | an | Komfort/Eco, Offset, Fenster, Boost, Ventil, Anzeige (Entitäten, Thermostatkarte); ab 0.8.0 |
| Benutzer ohne Admin-Rechte dürfen Wochenprogramme ändern | an | `set_week_profile`, `copy_week_profile`, Thermostatkarte; ab 0.8.0 |

## Wer darf was (ab 0.8.0)

Home Assistant kennt keine Rechte je Entität: Jeder Benutzer darf jeden Dienst aufrufen.
eq3_max prüft deshalb selbst, wer aufruft:

- **Nur Administratoren:** `factory_reset`, `link`, `unlink`, die Auswahl des Funkmoduls und der
  Anlern-Knopf (ab 0.8.2).
- **Nach Option** (siehe oben, Vorgabe frei): Geräteeinstellungen und Wochenprogramme.
- **Immer frei:** Temperatur, Modus, Presets, `set_away`, `set_time`.

Automationen, die durch ihren Auslöser laufen, haben keinen Benutzer und dürfen alles.
Startet ein Benutzer ein Skript oder eine Automation von Hand (Dashboard-Knopf, „Ausführen“),
gilt der Aufruf als dieser Benutzer und wird wie er geprüft. Ein abgelehnter Aufruf
meldet „Das dürfen nur Administratoren“ bzw. den Hinweis auf die Option.
