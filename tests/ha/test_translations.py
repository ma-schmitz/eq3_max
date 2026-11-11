"""Translations: Home Assistant drops a localized string whose placeholders differ from the
English one (and shows English instead), so every language must use the same set."""

import json
import string
from pathlib import Path

from custom_components.eq3_max.errors import translated
from custom_components.eq3_max.protocol.messages import FrameError

COMPONENT = Path(__file__).parents[2] / "custom_components" / "eq3_max"


def _strings(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}" if path else key)
    elif isinstance(node, str):
        yield path, node


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def _load(name: str) -> dict[str, str]:
    return dict(_strings(json.loads((COMPONENT / name).read_text(encoding="utf-8"))))


def test_same_placeholders_in_every_language():
    source = _load("strings.json")
    for name in ("translations/en.json", "translations/de.json"):
        texts = _load(name)
        assert texts.keys() == source.keys(), name
        wrong = {k: (_placeholders(v), _placeholders(source[k])) for k, v in texts.items()
                 if _placeholders(v) != _placeholders(source[k])}
        assert not wrong, (name, wrong)


def test_weekday_follows_the_language():
    err = FrameError("Monday: bad", key="week_profile_day_invalid", detail="bad", day="Monday",
                     day_en="Monday", day_de="Montag")
    assert translated(err, language="de").translation_placeholders["day"] == "Montag"
    assert translated(err, language="en").translation_placeholders["day"] == "Monday"
    assert translated(err).translation_placeholders["day"] == "Monday"


def test_selector_option_keys_are_valid_for_hassfest():
    """hassfest: translation keys only [a-z0-9-_], not starting/ending with - or _."""
    import re

    data = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for selector in data.get("selector", {}).values():
        for key in selector["options"]:
            assert re.fullmatch(r"[a-z0-9]([a-z0-9_-]*[a-z0-9])?", key), key
