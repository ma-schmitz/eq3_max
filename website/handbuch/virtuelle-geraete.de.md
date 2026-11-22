# Virtuelle Geräte


Ein virtuelles Gerät gibt es nur in Home Assistant, nicht als Hardware. eq3_max tritt damit
gegenüber Ihren echten Heizkörperthermostaten als MAX!-Gerät auf und füttert es aus einer
Entität, die Home Assistant ohnehin kennt.

| Art | Quelle | Wirkung |
|---|---|---|
| Virtueller **Fensterkontakt** | ein `binary_sensor` (z. B. ein Zigbee-Fensterkontakt) | die verknüpften Thermostate bekommen „offen“ bzw. „geschlossen“ und senken auf die Fenster-auf-Temperatur |
| Virtuelles **Wandthermostat** | ein Temperatur-`sensor` (°F und K werden umgerechnet) | die Thermostate eines Raums regeln nach dieser Temperatur statt nach ihrem eigenen Fühler, und ein Sollwert gilt für den ganzen Raum |

**Wofür?** Ein Heizkörperthermostat misst direkt am Heizkörper, also dort, wo es am wärmsten
ist. Ein Raumfühler, den Sie schon haben (Zigbee, ESPHome, …), misst besser. Ebenso kann ein
Fensterkontakt, den Sie schon verbaut haben, die Thermostate direkt per Funk absenken lassen,
ohne dass ein zweiter MAX!-Kontakt am Fenster hängt.

## Anlegen

Auf der Seite „eQ-3 MAX!“ **„Virtuelles Gerät anlegen“** wählen (nur für Administratoren) und
angeben:

1. die **Art** (Fensterkontakt oder Wandthermostat),
2. einen **Namen**,
3. die **Quelle**: für den Kontakt ein `binary_sensor`, für das Wandthermostat ein
   Temperatur-`sensor` (Geräteklasse Temperatur oder Einheit °C, °F oder K).

Ein Funkmodul wählen Sie nicht: Ein virtuelles Gerät sendet über das Funkmodul des jeweiligen
Thermostats und antwortet über das Modul, das ein Telegramm zuerst gehört hat. Die
Thermostate eines virtuellen Wandthermostats müssen an einem per **USB oder seriell**
angeschlossenen Funkmodul hängen (siehe [Grenzen](#grenzen-in-0100)); das prüft eq3_max
beim Verknüpfen.

!!! tip "Welche Quelle?"

    Nehmen Sie einen Sensor eines Geräts, das regelmäßig meldet (Zigbee, ESPHome, …).
    Sensoren, die nur bei einer Änderung einen neuen Zustand schreiben (Template- oder
    Hilfssensoren), gelten nach **3 Stunden** ohne Meldung als nicht verfügbar, auch wenn
    sich die Temperatur einfach nicht geändert hat.

Das virtuelle Gerät erscheint wie ein gekauftes: als Gerät in Home Assistant, mit
`binary_sensor` (Kontakt) bzw. `climate` (Wandthermostat). Es hat keine Batterie-, Signalstärke-
und Funkfehler-Entität.

## Verknüpfen

Danach **verknüpfen** Sie es mit den Thermostaten, genau wie ein gekauftes Gerät
([Verknüpfungen](verknuepfungen.md)): auf der Seite „eQ-3 MAX!“ im Reiter Verknüpfungen oder
mit dem Dienst `eq3_max.link`.

!!! info "Das erste Thermostat bestimmt den Raum"

    Das erste verknüpfte Thermostat gibt Sollwert, Modus, Wochenprogramm und die
    Einstellungen für Komfort, Eco und Fenster an das virtuelle Wandthermostat ab, aber nur,
    solange das virtuelle Wandthermostat noch keinen eigenen Sollwert hat. Was Sie dort schon
    eingetragen haben (Wochenprogramm einzelner Tage, gespeicherte Einstellungen), bleibt
    stehen. Steht das Thermostat gerade auf der Fenster-auf-Temperatur oder auf Boost, wird
    das nicht zum Sollwert des Raums; dann gilt sein letzter Komfortwert. Steht es auf
    Automatik, ohne dass ein vollständiges Wochenprogramm bekannt ist, läuft der Raum manuell
    mit seinem aktuellen Sollwert, und das Thermostat wird ebenfalls auf manuell gestellt
    (siehe [Automatik](#was-das-virtuelle-wandthermostat-tut)).
    Später verknüpfte Thermostate bekommen Sollwert und Modus des Raums. Ihr
    **Wochenprogramm wird nicht ungefragt überschrieben**: Die Seite zeigt einen Hinweis und
    bietet an, das Programm des Raums zu kopieren.

!!! warning "Fenster auch mit dem Wandthermostat verknüpfen"

    Soll „Fenster auf“ im Raum wirken, verknüpfen Sie den Kontakt (echt oder virtuell)
    **auch mit dem virtuellen Wandthermostat**, nicht nur mit den Thermostaten. Fehlt das,
    zeigt die Seite einen Hinweis.

## Was das virtuelle Wandthermostat tut

**Temperatur.** Die Temperatur der Quelle geht **alle 5 Minuten** an die Thermostate, fest
und pünktlich, ob sie sich geändert hat oder nicht (ab 0.10.1 bei mehr als zwei Räumen je
Funkmodul seltener, siehe [Sendezeit](#sendezeit-wie-viele-raume-je-funkmodul)). Ein Thermostat wartet knapp
**10 Minuten** auf sein Wandthermostat; kommt so lange nichts, regelt es nach seinem eigenen
Fühler und zeigt einen Funkfehler, bis das nächste Telegramm eintrifft.

Haben alle Thermostate des Raums dieselbe Gruppe (eine gemeinsame Gruppen-ID aller Thermostate eines Raums, die eq3_max beim
Verknüpfen selbst vergibt) und dasselbe Funkmodul, genügt **ein Telegramm** (eine einzelne
Funknachricht) **für den ganzen Raum**. Sonst geht die Temperatur an jedes Thermostat
einzeln, eines nach dem anderen: Jedes Thermostat braucht dann sein eigenes Telegramm alle
5 Minuten, das kostet etwa **13 s je Stunde und Thermostat**. Bei mehr als einem Thermostat
kann die Sendezeit dafür knapp werden, und sie regeln zeitweise nach ihrem eigenen Fühler.
Geben Sie dem Raum deshalb eine gemeinsame Gruppe: Die Seite zeigt beim virtuellen
Wandthermostat einen Hinweis und bietet **„Für den Raum vergeben“** an. Hängen die
Thermostate an verschiedenen Funkmodulen, hilft eine Gruppe nicht; das sagt der Hinweis dann
auch.

Verlässt ein Thermostat den virtuellen Raum (Verknüpfung gelöst oder virtuelles
Wandthermostat entfernt), nimmt eq3_max ihm die Gruppen-ID wieder, außer es gehört noch zu
einem anderen Wandthermostat.

Eine **fallende** Temperatur wird in Schritten von höchstens **1,0 °C** je Telegramm
weitergegeben. Ein plötzlicher Sprung nach unten würde sonst die eingebaute
Fenster-auf-Erkennung des Thermostats auslösen, und es senkt den Sollwert ab.

**Sollwert.** Ein Sollwert gilt für den ganzen Raum:

- Drehen Sie am Handrad eines Thermostats, erreicht die Änderung nach wenigen Sekunden das
  virtuelle Wandthermostat und von dort die anderen Thermostate des Raums.
- Ein in Home Assistant gesetzter Sollwert am virtuellen Wandthermostat oder an einem seiner
  Thermostate gilt ebenfalls für den ganzen Raum.

**Automatik und Abwesend.** Jedes Temperaturtelegramm gibt den Thermostaten auch den
Sollwert vor. Automatik geht deshalb nur, wenn das virtuelle Wandthermostat ein
**vollständiges Wochenprogramm** kennt, also eines, das für alle sieben Tage über eq3_max
geschrieben wurde (im Reiter Wochenprogramm oder mit `eq3_max.set_week_profile`). Ohne ein
solches läuft der Raum **manuell**: Home Assistant bietet keine Automatik an, die Seite zeigt
einen Hinweis mit **„Wochenprogramm festlegen“**, und drückt jemand am Thermostat die
Auto-Taste, stellt eq3_max es kurz danach wieder auf den Sollwert des Raums (während einer
Abwesenheit beendet die Auto-Taste die Abwesenheit für den ganzen Raum). Das Schreiben
des Programms ändert den Modus nicht; danach können Sie Automatik wählen.

In Automatik folgt der Raum dem Wochenprogramm. Eine Änderung am Handrad oder in Home
Assistant gilt bis zum **nächsten Schaltpunkt** des Programms, danach wieder das Programm,
wie bei einem echten Wandthermostat; ein neu geschriebenes Programm hebt sie auf. Eine
Abwesenheit („Abwesend“ mit Endzeit) geht auch ohne Programm. Sie endet von selbst zur
eingestellten Zeit; danach gilt wieder, was vorher galt: Automatik (mit Programm) oder der
manuelle Sollwert von vorher.

**Boost.** Ein Boost an einem Thermostat (Handrad oder Home Assistant) bleibt bei diesem
Thermostat, wie bei einem echten Wandthermostat; das virtuelle Wandthermostat zeigt dabei
weiter den Modus des Raums, nicht „Boost“. Ein Boost am virtuellen Wandthermostat schaltet
**alle** Thermostate des Raums auf Boost; er endet nach der Boost-Dauer der Thermostate,
spätestens nach einer Stunde.

**Fenster.** Siehe oben: den Kontakt auch mit dem virtuellen Wandthermostat verknüpfen.
Ein Fensterwechsel geht **sofort** an die Thermostate (bei „offen“ mit der
Fenster-auf-Temperatur), nicht erst mit dem nächsten 5-Minuten-Telegramm; ein weiterer
Wechsel innerhalb derselben Minute folgt am Ende dieser Minute. Höchstens **12** solcher
sofortigen Telegramme gehen je Stunde und Raum hinaus; darüber trägt das nächste reguläre
Telegramm den Fensterzustand.

**Virtueller Fensterkontakt.** Er sendet „offen“ bzw. „geschlossen“ mit Quittung (das Thermostat bestätigt den Empfang) an jedes
verknüpfte Thermostat. Quittiert eines nicht, wird der Zustand **alle 5 Minuten**
wiederholt, nach drei Fehlschlägen in Folge **alle 15 Minuten**, und einmal sofort, wenn das
Funkmodul nach einer Unterbrechung wieder da ist. Zwei Zustandswechsel an dasselbe
Thermostat liegen **mindestens eine Minute** auseinander: Ein Wechsel innerhalb dieser Minute
geht an ihrem Ende hinaus, und nur der dann aktuelle Zustand. Je Thermostat gehen höchstens
**12 Telegramme je Stunde** hinaus (Wiederholungen eingerechnet); darüber wartet der neueste
Zustand, bis wieder Platz ist. Periodisch wird nichts gesendet. Nach einem Neustart sendet eq3_max nur, wenn der Zustand vom zuletzt zugestellten
abweicht.

**Quelle nicht verfügbar.** Fällt die Quelle aus, ist die `climate`-Entität bzw. der Sensor
des virtuellen Geräts nicht verfügbar, und es wird nichts gesendet. Die Einstellungen bleiben
bedienbar. Die Thermostate fallen ohne Telegramme nach knapp 10 Minuten von selbst auf ihren
eigenen Fühler zurück. Eine Temperaturquelle, die sich **3 Stunden** lang nicht gemeldet hat,
gilt ebenfalls als nicht verfügbar (ein Sensor mit leerer Batterie zeigt oft einfach seinen
letzten Wert weiter). Ein virtueller Fensterkontakt ohne Quelle zählt für das virtuelle
Wandthermostat als geschlossen.

## Sendezeit: wie viele Räume je Funkmodul?

Funk im 868-MHz-Band darf je Gerät nur **1 % der Zeit** senden, das sind **36 Sekunden je
Stunde und Funkmodul**. Ein virtuelles Wandthermostat braucht mit seinem Telegramm alle
5 Minuten etwa **13 s je Stunde**. Ist die Option **„Sendezeit auf 36 s begrenzen“**
eingeschaltet, bleiben davon 10 s für Befehle frei, und ein Temperaturtelegramm, das in
diese Reserve fiele, entfällt; ohne die Option entscheidet das Funkmodul selbst.

**Ab 0.10.1 passt eq3_max den Takt an die Zahl der Räume an.** Bis zwei Räume je Funkmodul
bleibt es bei 5 Minuten. Mit mehr Räumen wird der Takt für alle Räume dieses Moduls im
gleichen Verhältnis länger, höchstens 8 Minuten:

| Räume je Funkmodul | Takt | Sendezeit je Stunde |
|---|---|---|
| 1 | 5 min | rund 13 s |
| 2 | 5 min | rund 27 s |
| 3 | 7,5 min | rund 27 s |
| 4 und mehr | 8 min | 33 s und mehr: passt nicht mehr |

Ein Raum ohne gemeinsame Gruppe (einzeln adressiert) zählt je Thermostat. Der längere Takt
hat einen Preis: Ein Thermostat wartet knapp 10 Minuten auf sein Wandthermostat. Geht bei
7,5 Minuten ein Telegramm verloren, regelt es bis zum nächsten nach dem eigenen Fühler.

**Richtwert: ein Funkmodul genügt für drei virtuelle Wandthermostate, bequem für zwei.**
Mehr Räume verteilen Sie auf mehrere Funkmodule ([Mehrere Funkmodule](funkmodule.md)).

!!! note "Lange Aufträge verdrängen die Temperatur"

    Ein langer Auftrag, etwa ein Wochenprogramm für drei Thermostate (braucht mehr als die
    36 s einer Stunde), kann einen Raum bis zu etwa **einer Stunde** ohne
    Temperaturtelegramme lassen. Die Thermostate regeln in dieser Zeit nach ihrem eigenen
    Fühler und kehren danach zum Raumfühler zurück.

## Grenzen in 0.10.0

- Die **Thermostate**, die Sie mit einem virtuellen Wandthermostat verknüpfen, müssen an
  einem per **USB oder seriell** angeschlossenen Funkmodul hängen, nicht an einem
  Netzwerkmodul (z. B. einem geflashten Cube); eq3_max lehnt das Verknüpfen sonst ab. Der
  virtuelle **Fensterkontakt** geht mit jedem Modul.
- Am virtuellen Wandthermostat gibt es **keinen Eco-Taster**.
- Ein Thermostat kann nur **ein** Wandthermostat haben (echt oder virtuell).

## Wenn Home Assistant nicht läuft

Läuft Home Assistant nicht, antwortet niemand für das virtuelle Wandthermostat. Das gilt
genauso, solange die Integration nicht geladen ist (Funkmodul fehlt, Integration
deaktiviert oder wird gerade neu geladen). Die Thermostate **heizen weiter**, nach knapp
10 Minuten mit ihrem eigenen Fühler. Eine Sollwertänderung am Handrad kostet das Thermostat
in dieser Zeit aber Sendezeit: Im ungünstigsten Fall (in den ersten knapp 10 Minuten des Ausfalls)
wiederholt es etwa **16 Minuten** lang und ist danach bis zu **einer Stunde** stumm. Es heizt
dabei weiter. Dagegen gibt es keine technische Abhilfe.

## Entfernen

- **„Entfernen“** löst zuerst die Verknüpfungen an den Thermostaten. Das virtuelle Gerät
  bleibt bis dahin als **„wird entfernt“** sichtbar und antwortet weiter, bis jedes
  verknüpfte Gerät quittiert hat.
- **„Trotzdem entfernen“** löscht es sofort. Ein Thermostat, das die Verknüpfung noch
  kennt, sendet dann ins Leere und kann bis zu **einer Stunde** verstummen.
- Dasselbe gilt, wenn Sie ein virtuelles Gerät löschen, während die Integration deaktiviert
  ist: Es wird sofort entfernt, mit derselben Folge.

!!! warning "Vor einem Wechsel auf eine ältere Version"

    Entfernen Sie alle virtuellen Geräte, bevor Sie auf eine Version vor 0.10.0
    zurückgehen. Eine ältere Version hält sie für echte Geräte an einer Adresse, unter der
    niemand antwortet.

!!! tip "Besser mit Geduld"

    Wählen Sie „Entfernen“ und warten Sie, bis das Gerät verschwindet. „Trotzdem entfernen“
    ist nur für den Fall gedacht, dass ein Thermostat dauerhaft nicht erreichbar ist
    (defekt, ausgebaut, ohne Batterie). Auch das Löschen bei deaktivierter Integration
    entfernt das Gerät sofort, mit derselben Folge.
