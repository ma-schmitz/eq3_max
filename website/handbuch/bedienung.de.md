# Thermostat bedienen


## Modi

| Modus in HA | Gerät | Wirkung |
|---|---|---|
| **Heizbetrieb** (`heat`) | manuell | hält den eingestellten Sollwert |
| **Automatik** (`auto`) | Wochenprogramm des Geräts | Gerät folgt seinem eigenen Programm |
| **Aus** (`off`) | manuell 4,5 °C | Frostschutz |

### Sollwert ändern

Was eine neue Temperatur bewirkt, hängt vom Modus ab, nicht davon, wo man sie einstellt — in
Home Assistant, auf der Thermostat-Karte oder am Handrad ist es dasselbe (ab 0.10.0):

| Modus | Eine neue Temperatur gilt … |
|---|---|
| **Automatik** | bis zum nächsten Schaltpunkt des Wochenprogramms; das Thermostat bleibt in Automatik und folgt danach wieder seinem Programm |
| **Heizbetrieb** (manuell) | dauerhaft, bis man sie wieder ändert |
| **Abwesend** | bis zur Endzeit; eine neue Temperatur beendet Abwesend und gilt dann dauerhaft (manuell) |

Für einen dauerhaften Wert aus der Automatik heraus zuerst „Heizbetrieb“ wählen, dann die
Temperatur einstellen. In Automationen geht das in einem Schritt mit `climate.set_temperature`
und `hvac_mode: heat`; `hvac_mode: auto` mit einer Temperatur kehrt zum Programm zurück und hält
die Temperatur bis zum nächsten Schaltpunkt. Bis 0.9.x schaltete jede Änderung aus Home
Assistant dauerhaft auf manuell.

Anzeige „Heizbetrieb (Heizbetrieb)“ bzw. „Heizbetrieb (Leerlauf)“: vor der Klammer der
Modus, in der Klammer die aktuelle Aktion — Heizbetrieb bei offenem Ventil, Leerlauf bei
0 %. Die Ventilstellung kommt nur, wenn sich das Ventil bewegt; nach einem Wechsel ggf. die
Seite neu laden.

## Presets

| Preset | Wirkung |
|---|---|
| **keins** | normaler Betrieb; in Automatik zurück zum Wochenprogramm (eine Änderung bis zum Schaltpunkt endet) |
| **Komfort** | Komforttemperatur aus der Gerätekonfiguration (ab 0.8.0); in Automatik bis zum nächsten Schaltpunkt, sonst Handbetrieb |
| **Eco** | Eco-Temperatur aus der Gerätekonfiguration (ab 0.8.0); in Automatik bis zum nächsten Schaltpunkt, sonst Handbetrieb |
| **Boost** | Ventil kurz weit auf (Dauer und Öffnung siehe Gerätekonfiguration), danach zurück |
| **Abwesend** | feste Temperatur bis zu einer Endzeit (Modus „temporär“) |

**Abwesend** aus dem Thermostat-Dialog nutzt die Optionen der Integration:
Abwesend-Temperatur (Standard **18,0 °C**) und Dauer (Standard **24 h**). Die Endzeit wird
auf die nächste volle oder halbe Stunde **aufgerundet** (die Geräte kennen nur :00 und :30).
Nach Ablauf kehrt das Gerät selbst in seinen vorherigen Modus zurück.

**Zurück aus Abwesend oder Boost:** Modus „Heizbetrieb“ wählen oder Preset „keins“ → es gilt
wieder der zuletzt eingestellte Komfortwert (egal ob in HA oder am Rad gesetzt; die
Fenster-auf-Temperatur zählt nicht als Komfortwert).

**Komfort und Eco** setzen den jeweiligen Wert, wie die Tasten am Gerät (Telegramm 0x40): im
Handbetrieb dauerhaft, in Automatik bis zum nächsten Schaltpunkt. HA zeigt das Preset auch, wenn der Sollwert auf anderem Weg dort landet,
im Handbetrieb wie in Automatik; bei offenem Fenster heißt es „keins“. Eco zählt nicht als
Komfortwert: Nach Abwesend oder Boost geht es zurück auf den letzten Komfortwert.

## Befehle und Quittungen

Jeder Befehl braucht etwa 1 s Weckpräambel; das Gerät quittiert ihn. Bis zur Quittung steht
der Wert unter `ausstehend`, angezeigt wird weiterhin der zuletzt **gemeldete** Wert. Kommt
keine Quittung, wird bis zu dreimal wiederholt (je 3 s Wartezeit), also können bis zu ~13 s
vergehen. Bleibt es unquittiert, geht `funkfehler` an und der Befehl wird bei der nächsten
Meldung des Geräts automatisch erneut gesendet. Mehrere schnelle Änderungen am selben Gerät:
nur die letzte wird gesendet.

Ausnahme: Eine Änderung in Automatik gilt nur bis zum nächsten Schaltpunkt. Ist sie bis dahin
nicht quittiert (kennt eq3_max das Wochenprogramm nicht: nach 15 Minuten), wird sie nicht mehr
gesendet; das Thermostat bekommt stattdessen die reine Automatik und folgt seinem Programm.
