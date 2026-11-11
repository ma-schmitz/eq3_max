# Pairing devices


1. Press `button.eq3_max_anlernen` (or **"Pair (60 s)"** on the "eQ-3 MAX!" panel) — 60 s
   pairing window.
2. Trigger pairing on the device (thermostat: hold the boost button until "Pair" appears;
   window contact/button: pairing button as described in the device manual).
3. The device appears automatically; the integration reloads once for it.

**With several radio modules** (from 0.7.0) the "eQ-3 MAX!" panel shows a selection
"Radio module for pairing" next to the button. With "all radio modules" (default) the device
gets the module that heard its pairing request first. If you choose a module, only that one
answers and the device is assigned to it; pairing requests heard only by the other modules
stay unanswered. Handy when the device lies next to one module but is meant to run through
another later – or the other way round. The button `button.eq3_max_anlernen` always pairs
through all modules.

After a **battery change** a known device re-registers by itself and keeps its values. If a
thermostat then shows "InS", press the boost button (see [FAQ](../faq.md)).
