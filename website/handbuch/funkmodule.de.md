# Mehrere Funkmodule


Reicht ein Funkmodul nicht durchs ganze Haus, kommen weitere dazu, z. B. einer pro Etage.
USB-Sticks und geflashte Cubes (Netzwerk) lassen sich mischen.

!!! abstract "So funktioniert es – wie die Interfaces bei Homegear"

    - Alle Module arbeiten mit **derselben Zentralen-Adresse**. Für die Geräte gibt es weiter
      nur eine Zentrale, keines wird neu angelernt.
    - Jedes Gerät hat **ein zugeordnetes Modul**. Darüber gehen alle Befehle an das Gerät:
      Sollwerte, Konfiguration, Verknüpfungen, Werksreset, Antworten auf Zeitanfragen.
    - **Empfangen wird über alle Module.** Hören zwei Module dasselbe Telegramm, wird es nur
      einmal ausgewertet. Die Empfangsstärke merkt sich die Integration je Modul.
    - **Umstellen ist eine reine Einstellung.** Es geht nichts an das Gerät, wartende Befehle
      wechseln mit auf das neue Modul.
    - Jedes Modul hat **sein eigenes Funkbudget** (1 % = 36 s pro Stunde). Wartet ein Modul
      auf Sendezeit, steht das an seiner Kachel.

**Modul hinzufügen:** Konfigurieren → „Funkmodule“ → „USB-Stick hinzufügen“, „Im Netzwerk
suchen und hinzufügen“ (ab 0.7.0, listet die culfw-Module im eigenen Netz) oder
„Netzwerk-CUL hinzufügen“, mit einem Namen (z. B. „Obergeschoss“). Einen geflashten Cube,
den Home Assistant selbst entdeckt hat, kann man auch direkt aus „Entdeckt“ als weiteres
Funkmodul hinzufügen. Das Modul wird mit `V`
geprüft, danach lädt die Integration neu. Das erste Modul heißt „Hauptmodul“, es ist die
Verbindung aus der Einrichtung.

**Modul umbenennen** (ab 0.7.0): auf der Seite „eQ-3 MAX!“ den Stift an der Kachel des Moduls
anklicken, Namen eingeben und mit Enter oder dem Haken bestätigen. Oder Konfigurieren →
„Funkmodule“ → „Funkmodul umbenennen“, Modul wählen, neuen Namen eingeben. Das geht auch beim Hauptmodul, etwa „EG“ statt
„Hauptmodul“. Nur der angezeigte Name ändert sich (Geräteseite, Auswahl `select.*_funkmodul`,
Seite „eQ-3 MAX!“); Entity-IDs, die Attribute `rssi_<modul>` und die Zuordnung der Geräte
bleiben.

**Gerät einem Modul zuordnen**, auf einem von zwei Wegen:

- Seite „eQ-3 MAX!“ → Gerät anklicken → Reiter **Funkmodul**. Dort steht für jedes Modul,
  wie gut es das Gerät zuletzt gehört hat; das beste ist markiert. „Zuordnen“ stellt um.
- Entität `select.<gerät>_funkmodul` (auch aus Automationen). Ihre Attribute
  `rssi_<modul>` zeigen die Empfangsstärke je Modul.

Neu angelernte Geräte bleiben auf dem Modul, das ihre Anmeldung zuerst gehört hat. Wer es
festlegen will, wählt beim Anlernen auf der Seite „eQ-3 MAX!“ das Modul aus (siehe
[Geräte anlernen](anlernen.md)).

**Modul entfernen:** Konfigurieren → „Funkmodule“ → „Funkmodul entfernen“. Seine Geräte
senden danach wieder über das Hauptmodul. Bleibt nur das Hauptmodul übrig, verschwinden die
`select.*_funkmodul`-Entitäten.

**Was man sieht:**

- In HA ist jedes Zusatzmodul ein eigenes Gerät („eQ-3 MAX! Funkmodul Obergeschoss“), die
  MAX!-Geräte hängen unter ihrem Modul.
- `binary_sensor.eq3_max_verbunden` ist nur an, wenn **alle** Module verbunden sind. Das
  Attribut `funkmodule` zeigt jedes einzeln. `sensor.eq3_max_sendezeit_1h` zeigt das
  meistbelastete Modul, das Attribut `funkmodule` alle.
- Fällt ein Zusatzmodul aus, gibt es eine eigene Reparaturmeldung „CUL nicht erreichbar“
  mit seinem Ziel. Geräte auf anderen Modulen arbeiten weiter. Anlernen geht, solange
  irgendein Modul verbunden ist.

!!! note "Quittungen an die Geräte: genau eine je Meldung"
    Fensterkontakte, Taster und Wandthermostate erwarten auf ihre Meldung an die Zentrale
    eine Quittung. Bis 0.6.x gab sie jede culfw selbst (`Za`). Hören zwei Module dasselbe
    Gerät, senden dann beide im selben Augenblick und stören sich: Das Gerät bekommt keine
    Quittung, wiederholt und meldet Funkfehler (im Funkbetrieb mit einem Wandthermostat
    beobachtet). Ab 0.7.0 antwortet nur noch eine Stelle:

    - **Hauptmodul am USB:** Die Integration quittiert selbst, über das Modul, das die
      Meldung zuerst geliefert hat; die Auto-Quittung der Firmware ist bei allen Modulen
      aus (`Za000000`). So bekommt auch ein Gerät seine Quittung, das nur ein Zusatzmodul
      hört. Die Antwort geht hinaus, bevor Home Assistant die Meldung weiterverarbeitet.
    - **Hauptmodul im Netzwerk (Cube, CUN):** Dessen Firmware quittiert weiter selbst,
      20 ms nach der Meldung. Der Weg über das Netzwerk und Home Assistant dauert 80 bis
      160 ms, und ein Fensterkontakt hört nur wenige zehn Millisekunden zu. Zusatzmodule
      quittieren nicht; ein Gerät, das nur ein Zusatzmodul hört, bekommt dann auf seine
      eigenen Meldungen keine Quittung. Das Hauptmodul sollte die Kontakte, Taster und
      Wandthermostate also erreichen.

    Eine feste Laufzeit kann Software nicht zusichern: Ist Home Assistant in dem Moment
    mit anderem beschäftigt (Start, träge Hardware, blockierende Integration), kommt die
    Quittung später. Das Gerät wiederholt dann seine Meldung nach einigen Sekunden.
