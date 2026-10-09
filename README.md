# KeyForge Automation

The original repo pressed one key on a fixed loop. KeyForge is a real
desktop-automation utility: configurable key sequences, human-like
randomized timing, per-window targeting, a global kill-switch, action
logging, and a dry-run mode that never touches your keyboard.

## Legitimate uses

- **Accessibility**: automating repetitive input for users with limited
  mobility
- **UI testing**: scripted input sequences for QA of desktop apps
- **Productivity**: boilerplate typing, form filling on your own machine
- **Gaming**: only where the game's terms explicitly allow automation

## Responsible use

Do not use KeyForge to spam chats, evade rate limits, cheat in games
where automation is prohibited, or interact with systems you do not own
or have permission to automate. You are responsible for complying with
the terms of service of every application you target. The kill-switch
(Esc by default) and pyautogui failsafe (mouse to screen corner) exist
so you can always stop a runaway sequence instantly.

## Features

- JSON key-sequence files (`sequences/example.json`): keys, text typing,
  hotkeys, per-step intervals (fixed or randomized `[min, max]`), repeats
- Per-window targeting: activate a window by title before running
- Global hotkeys: F9 pause/resume, Esc emergency stop (`keyboard` lib)
- Action log with timestamps (`keyforge.log`)
- `--dry-run`: validate a sequence end-to-end with zero key injection
- Countdown before live runs

## How to run

```bash
pip install -r requirements.txt   # pyautogui, keyboard (live runs only)
python cli.py sequences/example.json --dry-run   # safe: presses nothing
python cli.py sequences/example.json             # live run
python test_keyforge.py                          # headless test suite
```

## Sequence format

```json
{
  "name": "demo",
  "window": "Untitled - Notepad",
  "countdown": 3,
  "steps": [
    {"keys": ["h", "e", "l", "l", "o"], "interval": [0.05, 0.15], "repeats": 3},
    {"type": "text", "text": "hello", "interval": 0.5},
    {"hotkey": ["ctrl", "s"], "interval": [1.0, 2.0]}
  ]
}
```

## Requirements

Live runs need a display plus `pyautogui` and `keyboard`
(`keyboard` needs admin/root on Linux for global hotkeys).
Tests and `--dry-run` need nothing but the standard library.
