# Was ist neu

Die wichtigsten Neuerungen der letzten Versionen – alle Details im [Changelog](changelog.md).

## 0.11 – Thermostatkarte inklusive

![Thermostatkarte](assets/karte/card-kompakt-de-light.png#only-light)
![Thermostatkarte](assets/karte/card-kompakt-de-dark.png#only-dark)

| Neu | Wozu | Mehr |
|---|---|---|
| **Thermostatkarte wird mitgeliefert** | nichts mehr getrennt installieren; die Integration trägt die Karte selbst als Dashboard-Ressource ein, immer in der passenden Version | [Thermostatkarte](handbuch/karte.md) |
| **Symbole aus Home Assistant** | ein eigenes Symbol (etwa für die Fußbodenheizung) und „Anzeigen als“ Tür oder Garagentor erscheinen auf der Seite und in der Karte | [Seite](handbuch/seite.md) |
| **Bereiche einklappen und anordnen** | die Seite „eQ-3 MAX!“ nach dem eigenen Haus sortieren, am Handy nur die Räume offen, die man braucht | [Seite](handbuch/seite.md) |
| **„Funkmodul wartet auf Sendezeit“** | zeigt, ob die Integration bremst oder das Funkmodul selbst ablehnt | [Seite](handbuch/seite.md) |

!!! info "Karte bisher über HACS installiert?"
    Dort entfernen und die Integration neu laden – an den Dashboards ändert sich nichts.
    Bis dahin bleibt die alte Karte in Gebrauch, und unter Reparaturen steht ein Hinweis.

## 0.10 – Virtuelle Geräte und weniger Sendezeit

| Neu | Wozu | Mehr |
|---|---|---|
| **Virtueller Fensterkontakt** | ein beliebiger Kontakt aus Home Assistant (z. B. Zigbee) meldet „offen“ direkt an die Thermostate | [Virtuelle Geräte](handbuch/virtuelle-geraete.md) |
| **Virtuelles Wandthermostat** | ein beliebiger Temperatursensor regelt einen Raum wie ein echtes Wandthermostat | [Virtuelle Geräte](handbuch/virtuelle-geraete.md) |
| **Auto und Manuell wie am Gerät** | ein Sollwert in Automatik gilt bis zum nächsten Schaltpunkt, in Manuell dauerhaft | [Bedienung](handbuch/bedienung.md) |
| **Weniger Sendezeit** (0.10.1) | unveränderte Tage des Wochenprogramms werden nicht noch einmal gesendet; die Sendezeit übersteht einen Neustart | [Dienste](handbuch/dienste.md) |
| **Installation über die HACS-Suche** | eq3_max steht im Standardkatalog von HACS | [Installation](loslegen/installation.md) |

## 0.9 – Mehr Überblick auf der Seite

| Neu | Wozu |
|---|---|
| **Warteschlange ansehen** | welcher Befehl gerade gesendet wird und was noch wartet |
| **Warnung beim Anlernen** | ein Gerät, das noch an einer anderen Zentrale hängt, wird erkannt |
| **Verknüpfungsaufträge abbrechen** | ein hängender Auftrag lässt sich zurücknehmen |
| **„On“/„Off“ statt 30,5/4,5 °C** | wahlweise wie auf dem Display der Geräte |
| **Übernahme erst nach Bestätigung** | Entitäten von Homegear oder max_cul werden erst nach einer Reparatur-Bestätigung übernommen |

## 0.8 – Räume wie beim Cube

| Neu | Wozu | Mehr |
|---|---|---|
| **Presets Komfort und Eco** | ein Klick auf die eingestellte Komfort- bzw. Eco-Temperatur, wie die Tasten am Gerät | [Bedienung](handbuch/bedienung.md#presets) |
| **Gruppen-ID** | ein Sollwert an den Wandthermostat erreicht den ganzen Raum aus einem Telegramm | [Verknüpfungen](handbuch/verknuepfungen.md#gruppen-id-ab-080) |
| **Raumwerte** | Komfort, Eco, Fenster und Boost gelten für alle Thermostate eines Raums | [Gerätekonfiguration](handbuch/konfiguration.md) |
| **Anzeige Soll/Ist am Wandthermostat** | das Display zeigt die Ist-Temperatur | [Gerätekonfiguration](handbuch/konfiguration.md) |
| **Ist-Temperatur abfragen** | Heizkörper melden ihre Temperatur regelmäßig – für Verlaufskurven | [Gerätekonfiguration](handbuch/konfiguration.md#ist-temperatur-abfragen-ab-080) |
| **Freigaben** | Geräteeinstellungen und Wochenprogramme für Benutzer ohne Admin-Rechte sperrbar | [Wer darf was](handbuch/dienste.md#wer-darf-was-ab-080) |
| **Eigene Thermostatkarte** | Ventil, Batterie, Funk und Fenster auf einen Blick, Einstellungen und Wochenprogramm im Pop-up | [Thermostatkarte](handbuch/karte.md) |
