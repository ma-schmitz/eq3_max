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
    - Jedes Modul hat **sein eigenes Funkbudget** (1 % = 36 s pro Stunde).

**Modul hinzufügen:** Konfigurieren → „Funkmodule“ → „USB-Stick hinzufügen“ oder
„Netzwerk-CUL hinzufügen“, mit einem Namen (z. B. „Obergeschoss“). Das Modul wird mit `V`
geprüft, danach lädt die Integration neu. Das erste Modul heißt „Hauptmodul“, es ist die
Verbindung aus der Einrichtung.

**Gerät einem Modul zuordnen**, auf einem von zwei Wegen:

- Seite „eQ-3 MAX!“ → Gerät anklicken → Reiter **Funkmodul**. Dort steht für jedes Modul,
  wie gut es das Gerät zuletzt gehört hat; das beste ist markiert. „Zuordnen“ stellt um.
- Entität `select.<gerät>_funkmodul` (auch aus Automationen). Ihre Attribute
  `rssi_<modul>` zeigen die Empfangsstärke je Modul.

Neu angelernte Geräte bleiben auf dem Modul, das ihre Anmeldung zuerst gehört hat.

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

!!! warning "Noch nicht im echten Funkbetrieb erprobt"
    Jede culfw quittiert Telegramme an die Zentrale selbst (`Za`). Hören zwei Module ein
    Gerät gleich gut, quittieren beide fast gleichzeitig. Das schadet in der Regel nicht,
    eine Quittung kommt an. Am besten stehen die Module so, dass sich ihre Bereiche nur
    wenig überschneiden, etwa eins pro Etage.
