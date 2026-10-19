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

??? question "Warum sendet eq3_max keine eigenen Quittungen?"
    Was Geräte an die Zentrale schicken (Fensterkontakt 0x30, Stellbefehl vom
    Wandthermostat 0x40, Taster 0x50), quittiert die culfw selbst per `Za<Adresse>` – schneller
    als jede Software. 0x60/0x70 sind Rundsendungen und werden nicht quittiert; FHEM macht es
    genauso.

??? question "Geht das auch mit einem geflashten MAX! Cube?"
    Ja. Mit a-culfw geflasht ist der Cube neben dem nanoCUL das zweite mögliche Funkmodul,
    per Netzwerk (Port 2323) oder per USB. Am echten Cube noch nicht getestet. Ein Cube mit
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
