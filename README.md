# Macro Recorder

The original repo pressed one key on a loop. This is a full macro
system: **record** keyboard/mouse input with timing, save it as editable
JSON, then **replay** it with loop counts and speed control.

## Legitimate uses

- **UI testing**: replay exact input sequences against your own apps
- **Accessibility**: one-key replay of complex input chains
- **Productivity**: automate repetitive form-filling on your own machine
- **Demos**: scripted walkthroughs with precise timing

## Responsible use

Only record and replay input on machines and applications you own or
have explicit permission to automate. Do not use macros to spam,
cheat in games where automation is prohibited, or evade rate limits.
Playback can always be stopped instantly with Esc.

## Features

- `recorder.py` — captures key down/up, mouse moves (throttled),
  clicks with timestamps; Esc stops recording
- `macro.py` — `Macro` model: JSON save/load, `filter_type`,
  `trim`, `drop_mouse_moves`, `with_speed` editing
- `player.py` — faithful-timing replay; `--loops`, `--speed`,
  `--drop-moves`; Esc aborts mid-playback; `DryRunPlayer` for
  headless simulation
- `cli.py` — `record`, `play`, `info` subcommands
- `test_macro.py` — headless test suite (model, editing,
  serialization, playback)

## How to run

```bash
pip install -r requirements.txt   # pynput (record/live-play only)
python cli.py record --out demo.json
python cli.py info demo.json
python cli.py play demo.json --loops 2 --speed 1.5
python cli.py play demo.json --dry-run      # simulate, touch nothing
python test_macro.py                       # headless tests
```

## Macro file format

```json
{
  "name": "demo",
  "events": [
    {"type": "key_down", "t": 0.0, "key": "a"},
    {"type": "key_up", "t": 0.1, "key": "a"},
    {"type": "mouse_move", "t": 0.2, "x": 100, "y": 200}
  ]
}
```

Events are plain JSON — hand-edit timings, delete steps, or generate
macros programmatically.

## Requirements

Recording and live playback need a display and `pynput`.
Tests, `--dry-run`, and macro editing need only the standard library.
