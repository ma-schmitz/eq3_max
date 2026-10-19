"""MkDocs-Hook: Version auf der Startseite aus dem Manifest der Integration."""

import json
from pathlib import Path

MANIFEST = Path(__file__).parents[1] / "custom_components/eq3_max/manifest.json"


def on_config(config):
    config.extra["version"] = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    return config
