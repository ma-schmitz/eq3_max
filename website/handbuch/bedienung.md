# Thermostat bedienen


## Modi

| Modus in HA | Gerät | Wirkung |
|---|---|---|
| **Heizbetrieb** (`heat`) | manuell | hält den eingestellten Sollwert |
| **Automatik** (`auto`) | Wochenprogramm des Geräts | Gerät folgt seinem eigenen Programm |
| **Aus** (`off`) | manuell 4,5 °C | Frostschutz |

Anzeige „Heizbetrieb (Heizbetrieb)“ bzw. „Heizbetrieb (Leerlauf)“: vor der Klammer der
Modus, in der Klammer die aktuelle Aktion — Heizbetrieb bei offenem Ventil, Leerlauf bei
0 %. Die Ventilstellung kommt nur, wenn sich das Ventil bewegt; nach einem Wechsel ggf. die
Seite neu laden.

## Presets

| Preset | Wirkung |
|---|---|
| **keins** | normaler Betrieb |
| **Boost** | Ventil kurz weit auf (Dauer und Öffnung siehe Gerätekonfiguration), danach zurück |
| **Abwesend** | feste Temperatur bis zu einer Endzeit (Modus „temporär“) |

**Abwesend** aus dem Thermostat-Dialog nutzt die Optionen der Integration:
Abwesend-Temperatur (Standard **18,0 °C**) und Dauer (Standard **24 h**). Die Endzeit wird
auf die nächste volle oder halbe Stunde **aufgerundet** (die Geräte kennen nur :00 und :30).
Nach Ablauf kehrt das Gerät selbst in seinen vorherigen Modus zurück.

**Zurück aus Abwesend oder Boost:** Modus „Heizbetrieb“ wählen oder Preset „keins“ → es gilt
wieder der zuletzt eingestellte Komfortwert (egal ob in HA oder am Rad gesetzt; die
Fenster-auf-Temperatur zählt nicht als Komfortwert).

## Befehle und Quittungen

Jeder Befehl braucht etwa 1 s Weckpräambel; das Gerät quittiert ihn. Bis zur Quittung steht
der Wert unter `ausstehend`, angezeigt wird weiterhin der zuletzt **gemeldete** Wert. Kommt
keine Quittung, wird bis zu dreimal wiederholt (je 3 s Wartezeit), also können bis zu ~13 s
vergehen. Bleibt es unquittiert, geht `funkfehler` an und der Befehl wird bei der nächsten
Meldung des Geräts automatisch erneut gesendet. Mehrere schnelle Änderungen am selben Gerät:
nur die letzte wird gesendet.
