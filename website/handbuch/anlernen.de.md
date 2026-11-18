# Geräte anlernen


1. `button.eq3_max_anlernen` drücken (oder auf der Seite „eQ-3 MAX!“ **Anlernen (60 s)**) — 60 s
   Anlernfenster.
2. Am Gerät die Kopplung auslösen (Thermostat: Boost-Taste lang drücken, bis „Pair“ erscheint;
   Fensterkontakt/Taster: Anlerntaste laut Gerätebeschreibung).
3. Das Gerät erscheint automatisch, die Integration lädt sich dafür einmal neu.

**Mit mehreren Funkmodulen** (ab 0.7.0) steht auf der Seite „eQ-3 MAX!“ neben dem Knopf eine
Auswahl „Funkmodul fürs Anlernen“. Mit „alle Funkmodule“ (Vorgabe) bekommt das Gerät das
Modul, das seine Anmeldung zuerst gehört hat. Wählt man ein Modul, antwortet nur dieses, und
das Gerät wird ihm zugeordnet; Anmeldungen, die nur die anderen Module hören, bleiben
unbeantwortet. Praktisch, wenn das Gerät neben einem Modul liegt, später aber über ein
anderes laufen soll – oder umgekehrt. Der Knopf `button.eq3_max_anlernen` lernt immer über
alle Module an.

**Es passiert nichts, obwohl das Gerät seine Anlernanfrage sendet?** Dann ist es vermutlich
noch an einer anderen Zentrale angelernt (gebraucht gekauft, aus einem anderen MAX!-System)
und schickt die Anfrage an diese; die Integration beantwortet sie nie. Bei offenem
Anlernfenster zeigt die Seite einen Hinweis unter dem Knopf und das Log eine Warnung („… wants
to pair but is still paired to the central …“). Gerät auf Werkseinstellungen zurücksetzen
(Thermostat: Batterien raus, alle Tasten gedrückt halten, Batterien einlegen, bis „rES“
erscheint) und neu anlernen.

Nach einem **Batteriewechsel** meldet sich ein bekanntes Gerät von selbst neu an und behält
seine Werte. Steht ein Thermostat danach auf „InS“, Boost-Taste drücken (siehe [FAQ](../faq.md)).

**Zwischenstecker (BC-TS-Sw-Pl, ab 0.8.0):** wird angelernt und erscheint, aber nur mit RSSI
und „zuletzt gemeldet“; steuern lässt er sich noch nicht. Seine Telegramme stehen im Log
(„plug adapter, not supported yet“). Wer einen hat, hilft mit einem Mitschnitt als Issue.
