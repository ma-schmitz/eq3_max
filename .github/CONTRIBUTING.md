# Contributing to eq3_max

Thanks for your interest! Bug reports, protocol knowledge, translations and code are all welcome.
English or German – both are fine (Deutsch ist willkommen).

## Questions, bugs, ideas

- **Questions** and hardware experiences: [Discussions](https://github.com/ma-schmitz/eq3_max/discussions).
- **Bugs**: open an issue with the bug report form. Diagnostics and a debug log save a lot of back and forth.
- **Security issues**: privately, see [SECURITY.md](SECURITY.md).

## Development setup

Python 3.14 and [uv](https://docs.astral.sh/uv/):

    uv venv -p 3.14 .venv && uv pip install -p .venv -r requirements_test.txt
    .venv/bin/pytest

The protocol layer (`custom_components/eq3_max/protocol/`) has no Home Assistant dependency and
is tested on its own (`tests/protocol/`); the Home Assistant parts are tested in `tests/ha/`.

Before a pull request, also run hassfest locally (the same check as the CI):

    docker run --rm -v "$PWD":/github/workspace ghcr.io/home-assistant/hassfest

## Rules that keep things working

- **Radio budget.** In the 868 MHz band a transmitter may send at most 1 % of the time.
  Every new telegram counts. Acknowledgements and answers go out with `Zf` (no wake-up preamble),
  only commands to sleeping devices need `Zs`. Changes that send more must say so.
- **Translations.** User-facing texts live in `strings.json` and in both `translations/en.json` and
  `translations/de.json`, panel texts in the `t()` dictionary of the panel. The placeholders must be
  identical in all languages – Home Assistant silently drops a translation whose placeholders differ
  (`tests/ha/test_translations.py` checks this).
- **Selector option keys** in `services.yaml` are lowercase (hassfest).
- **No real data.** No real device addresses, serial numbers or IP addresses in tests, docs or logs
  you paste. Use made-up values (e.g. `123456`, `MEQ0000001`) or the documentation range `192.0.2.x`.
- **Changelog.** Add an entry under "Unreleased" in `CHANGELOG.md` and `CHANGELOG.de.md`.
- **Documentation.** If behaviour changes, update `README.md`/`README.de.md` and the website in
  `website/` (English `*.md`, German `*.de.md`).

## Testing with real devices

Many problems only show up on air. If you can, say in the pull request which radio module
(nanoCUL, Cube with a-culfw, …) and which devices you tested with. A debug log
(`custom_components.eq3_max: debug`) of the relevant moment is the best evidence.

## License

By contributing you agree that your contribution is published under the [MIT license](../LICENSE).

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
