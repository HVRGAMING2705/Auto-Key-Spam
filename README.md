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

## v2.0 — production release

- **Strict validation**: each step must carry exactly one action; `keys`/`hotkey`
  must be non-empty key lists; text steps need non-empty text; intervals must
  be `>= 0` or a valid `[min, max]` range; `repeats` is capped at 10000.
  Invalid files are rejected with a clear error instead of silently doing
  nothing (previously a bogus `type` step counted as an action that pressed
  nothing, and `keys: "abc"` was silently split into single characters).
- **Window-target abort**: a live run now aborts if the target window is
  missing, instead of sending keys to whatever window happens to be active.
  Override only with `--allow-missing-window`.
- **Web sequence builder** (`index.html`): build, validate (same rules as the
  Python tool), dry-run with true sampled timing, save in localStorage, and
  export a runnable `.json`. The page itself never presses keys.
- Removed the legacy `Auto Key Spam.py` raw key-spammer (no kill-switch,
  infinite loop); it lives in git history if ever needed.
- The old page's example JSON used fields the tool never supported
  (`wait_after`, `jitter`); the page now shows the real `sequences/example.json`.

## Features

- JSON key-sequence files (`sequences/example.json`): keys, text typing,
  hotkeys, per-step intervals (fixed or randomized `[min, max]`), repeats
- Per-window targeting: activate a window by title before running; aborts if the window is missing unless `--allow-missing-window` is passed
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
