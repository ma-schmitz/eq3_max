# FAQ

??? question "Das Ventil bleibt bei 0 %, obwohl es kalt ist"
    Der Thermostat steckt nach einem Neustart (etwa einem Batterie-Wackler) im
    Installationsmodus und zeigt „InS“. Am Thermostat die **Boost-Taste** drücken.
    Erkennen lässt sich das in HA so: Ventil 0 %, Ist-Temperatur bewegt sich nicht, keine
    Funkfehler.

??? question "Der Stick empfängt nichts mehr"
    Die Integration öffnet den Port selbst neu und legt bei Dauerproblemen eine
    Reparaturmeldung an. Zuerst den **USB-Port wechseln**: oft bricht die Port-Spannung beim
    Senden ein (siehe [Hardware](loslegen/hardware.md)). Danach den neuen `by-path`-Pfad in
    den Optionen wählen.

??? question "Wer quittiert die Meldungen der Geräte an die Zentrale?"
    Was Geräte an die Zentrale schicken (Fensterkontakt 0x30, Stellbefehl vom
    Wandthermostat 0x40, Taster 0x50), braucht eine Quittung. Bis 0.6.x gab sie die culfw
    selbst (`Za<Adresse>`). Seit 0.7.0 quittiert mit einem USB-Hauptmodul die Integration,
    genau einmal und über das Modul, das die Meldung zuerst geliefert hat; mit einem
    Netzwerk-Hauptmodul weiter dessen Firmware. Warum: siehe
    [Mehrere Funkmodule](handbuch/funkmodule.md). 0x60/0x70 sind Rundsendungen und werden
    nicht quittiert.

??? question "Ein Thermostat steht plötzlich auf 12 °C"
    Meist ist es die **Fenster-auf-Erkennung des Thermostats selbst**: Fällt die gemessene
    Temperatur schnell, nimmt es ein offenes Fenster an und geht für die Fenster-auf-Dauer auf
    die Fenster-auf-Temperatur (ab Werk 12 °C, 15 min), auch ohne Fensterkontakt. Abschalten
    lässt sie sich mit `fenster_dauer` 0 (siehe [Gerätekonfiguration](handbuch/konfiguration.md)).
    Bleiben die 12 °C nach dem Schließen eines Fensters stehen, lohnt ein Blick in die eigenen
    Automationen: Eine Heizungssteuerung, die beim Öffnen einen Schnappschuss nimmt und beim
    Schließen zurückspielt, kann dabei die Fenster-auf-Temperatur wiederherstellen. Beim
    Blueprint „Advanced Heating Control“ hilft dagegen die Option *Legacy restore*.

??? question "Geht das auch mit einem geflashten MAX! Cube?"
    Ja. Mit a-culfw geflasht ist der Cube neben dem nanoCUL das zweite mögliche Funkmodul,
    per Netzwerk (Port 2323) oder per USB; geflashte Cubes laufen in zwei weiteren
    Installationen. Ein Cube mit
    Original-Firmware geht nicht, dafür gibt es `maxcube`. Details:
    [Hardware](loslegen/hardware.md).

??? question "Warum dauert ein Stellbefehl manchmal bis zu 10 Sekunden?"
    Jedes Telegramm braucht 1 s Weckpräambel. Kommt die Quittung nicht innerhalb von 3 s,
    wird bis zu dreimal wiederholt. Bei gleichzeitiger Bedienung am Gerät (Wandthermostat,
    Taster) können sich Funktelegramme überlagern.

??? question "Kann ich mehrere Sticks oder Cubes gleichzeitig nutzen?"
    Ja, alle mit derselben Zentralen-Adresse. Jedes Gerät sendet über das Modul, dem es
    zugeordnet ist; umstellen geht ohne Neuanlernen. Siehe
    [Mehrere Funkmodule](handbuch/funkmodule.md).
