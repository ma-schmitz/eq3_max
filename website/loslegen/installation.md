# Installation

## Voraussetzungen

- **Home Assistant 2026.8** oder neuer (das eigene Logo erscheint ab 2026.9).
- Ein **Funkmodul mit culfw** und MAX!-Unterstützung, siehe [Hardware](hardware.md):
  ein nanoCUL per USB oder ein mit a-culfw geflashter MAX! Cube im Netzwerk.
- Wer von Homegear oder einer älteren Installation kommt: vorher [Umstieg](../umstieg/index.md) lesen.

## Installieren

=== "Über HACS"

    1. HACS öffnen → Menü oben rechts → **Benutzerdefinierte Repositories**.
    2. Die Adresse dieses Repositorys eintragen, Kategorie **Integration**.
    3. **eQ-3 MAX!** suchen und herunterladen.
    4. Home Assistant neu starten.

=== "Von Hand"

    1. Den Ordner `custom_components/eq3_max` aus dem Repository nach
       `/config/custom_components/` auf der HA-Box kopieren (SSH-Add-on oder Samba).
    2. Home Assistant neu starten.

Danach unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach
„eQ-3 MAX!“ suchen und der [Einrichtung](einrichtung.md) folgen.

!!! tip "Updates"
    Ein Neuladen der Integration lädt keinen neuen Python-Code. Nach jedem Update
    Home Assistant **neu starten**.
