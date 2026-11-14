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
| `select.…_anzeige` | Display zeigt Soll- oder Ist-Temperatur | – | ✓ (ab 0.8.0) |
| `select.…_ist_abfragen` | Ist-Temperatur regelmäßig abfragen (aus, 15 min … 4 h) | ✓ (ab 0.8.0) | – |

**Wichtig zu wissen:**

- Die Geräte kennen nur **Komplettsätze** (alle Temperaturen bzw. alle Ventilwerte). Ändert man
  einen Wert, sendet die Integration den ganzen Satz mit den gespeicherten übrigen Werten.
- Die Geräte melden ihre Konfiguration **nicht** zurück. Angezeigt wird der zuletzt
  **quittierte** Stand; ein gesendeter, noch nicht quittierter Wert steht unter `ausstehend`.
  **Ausnahme Anzeige:** Der Wandthermostat meldet selbst, ob er Soll- oder Ist-Temperatur
  zeigt. Bis zur ersten Meldung ist `select.…_anzeige` unbekannt (keine angenommene
  Werksvorgabe). Am Gerät lässt sich das nicht umstellen: Das Menü (Punkt „S-A“) ist
  gesperrt, solange der Wandthermostat an einer Zentrale angelernt ist.
- Attribut **`quelle`**: `homegear` (aus der Übernahme), `werksvorgabe` (angenommen, nie
  bestätigt), `gesetzt` (vom Gerät quittiert) oder `gemeldet` (vom Gerät selbst gemeldet,
  nur die Anzeige). Werden Werksvorgaben mitgesendet, steht im
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

## Ist-Temperatur abfragen (ab 0.8.0)

Ein Heizkörperthermostat meldet seine gemessene Temperatur nur in seiner Statusmeldung, und
die schickt er nur, wenn sich bei ihm etwas ändert (Ventil, Sollwert, Modus). In einem Raum
ohne Wandthermostat steht die Ist-Temperatur deshalb oft stundenlang still.

Mit `select.…_ist_abfragen` stößt eq3_max das Gerät in einem festen Abstand an, aber nur,
wenn in dieser Zeit keine Meldung von selbst kam: Sollwert um 0,5 °C hoch (an der oberen
Grenze runter), warten, bis das Gerät seinen Status mit der Ist-Temperatur schickt (gemessen
20 s bis gut 3 min, je nach Gerät; nach 5 min gibt eq3_max auf), dann zurück. Im Automatikbetrieb geht es danach zurück auf Automatik. Home
Assistant zeigt während des Anstoßes weiter den echten Sollwert; ein eigener Befehl in der
Zeit hat Vorrang.

- **Kosten:** zwei Telegramme je Anstoß (Funkbudget, Batterie); der Ventilmotor bewegt sich
  dabei in der Regel nicht. Ausgelassen wird bei Abwesend, Boost, offenem Fenster, einem
  ausstehenden Befehl oder knappem Funkbudget.
- Wandthermostate brauchen das nicht, sie melden ihre Temperatur alle paar Minuten.
- Ein schnelles Hin und Her (Sollwert oder Modus nach einer Sekunde zurück) löst **keine**
  Meldung aus; das Gerät muss den geänderten Sollwert etwa eine Minute behalten.
