# Gerätekonfiguration


Auf der Geräteseite jedes Thermostats unter **Konfiguration**:

| Entität (Beispiel `ht_wohnzimmer`) | Wert | Heizkörper | Wand |
|---|---|---|---|
| `number.…_komfort` / `_eco` | Komfort-/Eco-Temperatur (4,5–30,5 °C) | ✓ | ✓ |
| `number.…_maximal` / `_minimal` | Grenzen für die Bedienung am Gerät | ✓ | ✓ |
| `number.…_offset` | Korrektur der gemessenen Temperatur (−3,5…+3,5 K) | ✓ | ✓ |
| `number.…_fenster_temperatur` / `_fenster_dauer` | Temperatur und Dauer bei offenem Fenster | ✓ | ✓ |
| `select.…_boost_dauer` | Boost-Dauer | ✓ | ✓ (ab 0.7.0) |
| `number.…_boost_ventil` | Ventilöffnung im Boost | ✓ | – |
| `select.…_entkalkung_tag`, `number.…_entkalkung_stunde` | wöchentliche Ventil-Entkalkung | ✓ | – |
| `number.…_ventil_max` / `_ventil_offset` | maximale Öffnung, Ventil-Offset (%) | ✓ | – |

**Wichtig zu wissen:**

- Die Geräte kennen nur **Komplettsätze** (alle Temperaturen bzw. alle Ventilwerte). Ändert man
  einen Wert, sendet die Integration den ganzen Satz mit den gespeicherten übrigen Werten.
- Die Geräte melden ihre Konfiguration **nicht** zurück. Angezeigt wird der zuletzt
  **quittierte** Stand; ein gesendeter, noch nicht quittierter Wert steht unter `ausstehend`.
- Attribut **`quelle`**: `homegear` (aus der Übernahme), `werksvorgabe` (angenommen, nie
  bestätigt) oder `gesetzt` (vom Gerät quittiert). Werden Werksvorgaben mitgesendet, steht im
  Log „Sende angenommene Werksvorgaben mit: …“; nach der Quittung sind sie `gesetzt`.
- Werte müssen auf dem Raster liegen (0,5 °C bzw. 5 min/5 %); 21,3 °C wird abgelehnt.
- Jede Änderung kostet ein Funktelegramm; mehrere schnelle Änderungen → nur der letzte Stand.
- Eine Konfigurationsänderung lässt das Wochenprogramm des Geräts unberührt.
- **Raumwerte gelten für den ganzen Raum (ab 0.7.0).** Jedes Gerät speichert seine
  Einstellungen für sich, und die Geräte gleichen sie untereinander nicht ab: Das
  Wandthermostat zählt den Boost nach seiner Dauer herunter, jeder Heizkörper nach der
  seinen. Ohne Zentrale stellt man diese Werte im Menü des Wandthermostats für den Raum ein;
  an einer Zentrale angelernt ist das Menü gesperrt, dann ist das Sache der Zentrale. Ändert
  man einen Raumwert an einem Thermostat, stellt die Integration ihn deshalb auch an den
  übrigen Thermostaten ein, die über ein Wandthermostat mit ihm verknüpft sind (das
  Wandthermostat selbst und seine Heizkörper):

    | Raumwert (wird geteilt) | bleibt je Gerät |
    |---|---|
    | Komfort- und Eco-Temperatur | Temperatur-Offset |
    | Minimal- und Maximaltemperatur | maximale Ventilöffnung, Ventil-Offset |
    | Fenster-auf-Temperatur und -Dauer | |
    | Boost-Dauer und Boost-Ventilöffnung | |
    | Entkalkung (Tag, Stunde) | |
    | Wochenprogramm ([Dienste](dienste.md)) | |

    Je betroffenem Gerät kostet das ein Telegramm je Satz. Geräte, deren Werte heute schon
    voneinander abweichen, bleiben so, bis der Wert einmal geändert wird. Thermostate ohne
    Wandthermostat bleiben für sich.
