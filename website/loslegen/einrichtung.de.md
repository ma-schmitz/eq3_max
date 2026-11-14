# Einrichtung

Einstellungen → Geräte & Dienste → **Integration hinzufügen** → „eQ-3 MAX!“. Der Dialog
fragt der Reihe nach:

## 1. Verbindung

=== "USB-Stick"

    Den Stick unter `/dev/serial/by-path/…` wählen. **Nie `by-id`**: viele CUL-Sticks
    haben keine Seriennummer, zwei gleiche Sticks wären darüber nicht zu unterscheiden.

=== "Im Netzwerk suchen (ab 0.7.0)"

    Fragt alle Adressen im Netz von Home Assistant auf Port **2323** ab (höchstens 254,
    wenige Sekunden) und listet, was als culfw antwortet, mit Adresse und Firmware-Kennung,
    etwa `192.0.2.60 – V 1.26.08 a-culfw … CUBe`. Auswählen, weiter. Bereits eingerichtete
    Module fehlen in der Liste. Nicht gefunden wird ein Modul in einem anderen Netz (VLAN)
    oder mit geändertem Port; dafür gibt es die Eingabe von Hand.

    Einen **geflashten MAX! Cube meldet Home Assistant auch von selbst** unter
    Einstellungen → Geräte & Dienste → „Entdeckt“ (er ist an seiner Netzwerkadresse
    `00:80:41:…` zu erkennen). Gibt es schon einen Eintrag eQ-3 MAX!, lässt sich der Cube
    dort gleich als weiteres Funkmodul hinzufügen.

=== "Netzwerk: Adresse eingeben"

    Host (nur Name oder IP, kein `http://`) und Port, Standard **2323**. Bevor es
    weitergeht, sendet der Dialog `V`; antwortet binnen 5 s keine culfw, erscheint
    „Dort antwortet keine culfw“.

## 2. Zentralen-Adresse

Sechs Hexziffern, Standard `C0FFEE`. MAX!-Geräte merken sich die Adresse ihrer Zentrale.

!!! important "Beim Umzug die bisherige Adresse übernehmen"
    Wer von Homegear oder FHEM kommt, trägt **dieselbe Adresse** ein wie bisher. Dann muss
    kein Gerät neu angelernt werden. Wie man sie findet, steht unter
    [Von Homegear](../umstieg/homegear.md#vorbereiten).

## 3. Geräte übernehmen

| Quelle | Wann |
|---|---|
| **JSON** | Exportdatei aus Homegear oder einer früheren Installation (empfohlen beim Umzug) |
| **Homegear** | Homegear direkt abfragen, solange es noch läuft |
| **keine** | Neuinstallation, Geräte werden danach [angelernt](../handbuch/anlernen.md) |

Die Entity-IDs der bisherigen `homematic`-Integration bleiben dabei erhalten.

## Optionen

Später unter **Konfigurieren**:

| Menüpunkt | Inhalt |
|---|---|
| Einstellungen | Sendezeit-Bremse (36 s pro Stunde und Modul, bei neuen Einträgen an), Abwesend-Temperatur (18,0 °C) und -Dauer (24 h), ab 0.8.0 die Freigaben für Benutzer ohne Admin-Rechte |
| Verbindung ändern | USB ↔ Netzwerk oder anderer Port/Host, ohne die Integration neu anzulegen |
| Funkmodule | weitere Sticks oder Cubes hinzufügen und entfernen, siehe [Mehrere Funkmodule](../handbuch/funkmodule.md) |

Eine geänderte Verbindung wird wie bei der Einrichtung mit `V` geprüft und lädt die
Integration neu; die Einstellungen wirken ohne Neustart.
