# Umstieg von max_cul

`max_cul` ist der frühere Name dieser Integration (bis 09.10.2026). eq3_max übernimmt die
Entitäten mit gleicher ID, Bereich und Namen. Überblick: [Umstieg](index.md).

## Ablauf

1. **Aktuellen Zustand exportieren.** Aus dem Speicher der laufenden Installation
   (`/config/.storage/max_cul.devices.<entry_id>`) eine Exportdatei erzeugen. Die Werte
   gehören unter `values` als `SET_TEMPERATURE`, `ACTUAL_TEMPERATURE`, `VALVE_STATE`,
   `CONTROL_MODE`, `LOWBAT`, `STATE`. Ohne diesen Schritt startet eq3_max mit älteren Werten.
2. **`/config/custom_components/max_cul` aus `custom_components` heraus verschieben.**
   Umbenennen innerhalb des Ordners reicht nicht, jeder Ordner dort wird als Integration
   geladen.
3. `custom_components/eq3_max` einspielen, HA neu starten. Der alte Eintrag „MAX! CUL“
   meldet dann „Integration nicht gefunden“, das ist erwartet.
4. „eQ-3 MAX!“ einrichten (Verbindung, Adresse, Quelle JSON).
5. **Vor dem Löschen kontrollieren:** In der Entity-Registry dürfen bei Plattform `max_cul`
   nur noch die vier Funkmodul-Entitäten `*.max_cul_*` stehen. Alles andere ginge beim
   Löschen verloren.
6. Alten Eintrag „MAX! CUL“ löschen.
7. Automationen und Dashboards von `*.max_cul_*` auf die neuen Funkmodul-Entitäten
   umstellen. Deren Verlauf wird nicht übernommen.

| Alt | Neu |
|---|---|
| `binary_sensor.max_cul_verbunden` | `binary_sensor.eq3_max_verbunden` |
| `sensor.max_cul_sendezeit_1h` | `sensor.eq3_max_sendezeit_1h` |
| `sensor.max_cul_warteschlange` | `sensor.eq3_max_warteschlange` |
| `button.max_cul_anlernen` | `button.eq3_max_anlernen` |

Solange `max_cul` noch geladen ist, verweigert eq3_max die Einrichtung (Reparaturmeldung
„max_cul noch aktiv“). Zwei Integrationen am selben Stick würden sich stören.
