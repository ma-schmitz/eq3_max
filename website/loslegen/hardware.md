# Hardware

eq3_max braucht ein **Funkmodul mit culfw** (868 MHz, MAX!-Unterstützung). Zwei Wege:

| | nanoCUL | MAX! Cube mit a-culfw |
|---|---|---|
| Anschluss | USB an der HA-Box | Netzwerk (LAN) oder USB |
| Firmware | culfw (z. B. `1.66 nanoCUL868`) | a-culfw für den Cube |
| Einrichtung | Verbindung „USB-Stick“, Port aus `/dev/serial/by-path/` | Verbindung „Netzwerk“, Host und Port 2323 |
| Funkbudget (1 %) | eq3_max bremst auf 36 s pro Stunde (Standard); culfw mit Budgetprüfung lehnt zusätzlich selbst ab (`LOVF`) | a-culfw hält es selbst ein (`LOVF`) |
| Stand | im Dauerbetrieb erprobt | in zwei weiteren Installationen mit geflashten Cubes im Einsatz |

!!! info "Beide sind austauschbar – und mischbar"
    Die Geräte merken sich nicht das Funkmodul, sondern die **Zentralen-Adresse**, und die
    setzt eq3_max beim Start (`Za<Adresse>`). Wechsel nanoCUL ↔ Cube: Optionen →
    „Verbindung ändern“, nichts neu anlernen. Mehrere gleichzeitig, z. B. eins pro Etage:
    siehe [Mehrere Funkmodule](../handbuch/funkmodule.md).

## nanoCUL (USB)

- Viele nanoCULs haben einen CH341-Wandler (USB-ID `1a86:7523`) **ohne Seriennummer**.
  Deshalb immer `/dev/serial/by-path/…` wählen, nie `by-id`.
- 38400 Baud, Init-Folge `V`, `X21`, `Zr`, `Za<Adresse>`. Gesendet wird mit `Zs`.

!!! note "Funkbudget: höchstens 1 % Sendezeit"
    Im 868-MHz-Band darf jeder Sender höchstens 1 % der Zeit senden, also 36 s pro Stunde.
    eq3_max misst das (`sensor.eq3_max_sendezeit_1h`) und hält es mit der **Bremse** ein,
    die bei neuen Einträgen eingeschaltet ist. Manche culfw-Builds (`nocredits`) prüfen das
    Budget nicht selbst – dann sorgt allein die Bremse dafür; sie sollte an bleiben.

    Die Firmware rechnet strenger als die Bremse: a-culfw hält höchstens **9 s Sendezeit
    auf Vorrat** (nach einem Neustart des Moduls 4,5 s) und füllt 10 ms je Sekunde nach.
    Ist der Vorrat leer, lehnt sie das Senden ab (`LOVF`). eq3_max wartet dann und versucht
    es alle 10 s wieder; ein Telegramm mit Weckpräambel (rund 1,1 s) geht nach knapp zwei
    Minuten hinaus. Verloren geht nichts, es dauert nur: Ein ganzes
    [Wochenprogramm](../handbuch/dienste.md) (7 bis 14 Telegramme) braucht so eine
    Viertelstunde und mehr. Auf der Seite „eQ-3 MAX!“ steht am Funkmodul solange
    „wartet auf Sendezeit“, im Log einmal je Befehl `culfw refused to send … (LOVF)`.

!!! warning "Empfängt nach dem Senden nichts mehr? Erst den USB-Port wechseln."
    Wirkt der Stick taub – die Firmware antwortet, Senden geht, aber der Empfang bricht
    nach dem ersten Senden weg –, liegt das oft nicht am Stick, sondern am USB-Port: Seine
    Spannung bricht unter dem Sendestrom ein. Anderer Port, kurzes Verlängerungskabel oder
    aktiver Hub. Danach den neuen `by-path`-Pfad in den Optionen wählen.

## MAX! Cube mit a-culfw (Netzwerk)

Der MAX! Cube hat denselben Funkchip wie ein CUL. Mit **a-culfw** geflasht spricht er das
gleiche Textprotokoll wie der nanoCUL, nur über TCP. Vorteil: Er kann per Netzwerkkabel
dort stehen, wo der Funk gut ist.

1. **Flashen** nach der Anleitung des a-culfw-Projekts (Abschnitt MAX! Cube). Die
   eQ-3-Firmware geht dabei verloren, `maxcube` und die eQ-3-Software funktionieren danach
   nicht mehr.
2. **Ins LAN** hängen, IP-Adresse im Router nachsehen und fest vergeben.
3. **Prüfen:** `nc <cube-ip> 2323`, dann `V` eingeben – Antwort etwa `V 1.26.08 a-culfw CUBE`.
4. **In eq3_max:** Verbindung „Netzwerk (CUN, geflashter Cube)“, Host = IP, Port 2323.
5. Die Option **„Sendezeit auf 36 s pro Stunde begrenzen“** eingeschaltet lassen (Standard
   bei neuen Einträgen). a-culfw prüft das Budget zusätzlich selbst und lässt höchstens 9 s
   am Stück zu; bei mehr Funkverkehr verweigert sie das Senden (`LOVF`), eq3_max wartet dann
   und sendet, sobald wieder Zeit frei ist (siehe Hinweis oben).

Fällt die Verbindung weg, merkt eq3_max das nach etwa 90 s und verbindet neu; nach 15
Minuten erscheint die Reparaturmeldung „CUL nicht erreichbar“. Empfängt der Cube nichts
mehr, hilft nur ein Neustart des Cubes – ein Neuverbinden setzt sein Funkmodul nicht zurück.

Ein Cube mit **Original-Firmware** geht nicht; er spricht ein eigenes Protokoll, dafür gibt
es die HA-Integration `maxcube`.
