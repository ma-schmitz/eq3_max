# Umstieg auf eq3_max

So zieht eine bestehende MAX!-Installation auf die Integration **eq3_max** („eQ-3 MAX!“) um.
Erprobt ist der Weg von Homegear an einer Installation mit 24 Geräten.

## Welche Anleitung passt?

| Bisher | Anleitung | Neu anlernen? | Entity-IDs |
|---|---|---|---|
| Homegear + legacy `homematic`-Integration | [Von Homegear](homegear.md) | nein | automatisch übernommen |
| nichts, Neuinstallation | [Einrichtung](../loslegen/einrichtung.md) | – | – |

## Das Prinzip

!!! abstract "Drei Regeln"

    - **MAX!-Geräte merken sich die Funkadresse ihrer Zentrale.** Sendet eq3_max mit derselben
      Adresse und kennt es die Geräteliste, muss kein Gerät neu angelernt werden.
    - **Entity-IDs bleiben**, damit Automationen, Dashboards und der Verlauf weiterlaufen.
    - **Nie zwei Zentralen gleichzeitig.** Die alte Lösung wird abgeschaltet, bevor eq3_max
      startet. Solange `homematic` in HA geladen ist, verweigert eq3_max die
      Einrichtung.

## Voraussetzungen

- Home Assistant **2026.8 oder neuer** (Logo im UI ab 2026.9).
- Ein Funkmodul mit culfw, eins von beiden (Details unter [Hardware](../loslegen/hardware.md)):
  - **nanoCUL** per USB an der HA-Box (erprobt), oder
  - **MAX! Cube mit a-culfw** im Netzwerk (Port 2323) oder per USB (in weiteren
    Installationen im Einsatz).

  Für den Umstieg ist es gleich, welches: Entscheidend ist die Zentralen-Adresse, nicht
  das Modul.
- Zugriff auf `/config` der HA-Box (SSH-Add-on oder Samba).
- Etwa eine Stunde, am besten tagsüber bei wenig Heizbedarf. Die Thermostate regeln während
  der Umstellung selbstständig weiter, nur Befehle aus HA kommen nicht an.

## Häufige Stolperstellen

| Symptom | Ursache und Abhilfe |
|---|---|
| Einrichtung bricht mit „Homematic-Integration noch aktiv“ ab | `homematic:` steht noch in der YAML, oder HA wurde nicht neu gestartet |
| Neue Entitäten heißen `…_2` | Der Vorgänger-Eintrag gehört einer fremden Integration oder fehlte im Trockenlauf |
| Geräte heißen wie ihre Seriennummer | Export ohne Namen und kein Vorgänger mit Namen → `name` in der Exportdatei setzen |
| Konfiguration steht überall auf `werksvorgabe` | Export ohne Werte → Export bei laufendem Homegear wiederholen oder Werte in eq3_max setzen |
| Verknüpfungen fehlen | Export ohne `links` → auf der Seite „eQ-3 MAX!“ oder mit `eq3_max.link` nachtragen |
| Befehle bleiben „ausstehend“, Funkfehler | Stick wird nach dem Senden taub (USB-Port). Die Integration öffnet den Port dann selbst neu. Dauerhafte Abhilfe: anderer Port, kurzes Verlängerungskabel oder aktiver Hub |
| Befehle verzögert, im Log `LOVF`, am Funkmodul „wartet auf Sendezeit“ | Der Sendezeit-Vorrat der Firmware ist leer (nanoCUL/CUL 9 s, Cube 36 s am Stück, 10 ms je Sekunde kommen nach). eq3_max wartet und sendet von selbst weiter; nichts tun. Viele Befehle hintereinander (Wochenprogramme, Konfiguration vieler Geräte) brauchen dann entsprechend lange |
| Geflashter Cube: Funkmodul wird immer wieder rot, Befehle bleiben unquittiert | Der Cube startet neu, weil er am LAN hängt und seinen Strom aus einem USB-Anschluss von Router/NAS/Rechner bezieht (Fehler in a-culfw) → an ein USB-Netzteil hängen |
| Neuer Code wirkt nicht | Neuladen der Integration lädt keinen neuen Python-Code → HA neu starten |
