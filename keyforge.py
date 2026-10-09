"""KeyForge — legitimate desktop automation utility.

Reframed from a raw key-spammer into a structured automation tool with
safety rails: dry-run mode, kill-switch, per-window targeting, action
logging, and randomized human-like intervals.

Backends are abstracted so everything except actual key injection is
testable headless via DryRunBackend.
"""
import json
import logging
import random
import time

log = logging.getLogger("keyforge")


class DryRunBackend:
    """Records actions instead of performing them. No display needed."""

    def __init__(self):
        self.actions = []

    def press(self, key):
        self.actions.append(("press", key))

    def hotkey(self, *keys):
        self.actions.append(("hotkey", keys))

    def type_text(self, text):
        self.actions.append(("type", text))

    def activate_window(self, title):
        self.actions.append(("activate_window", title))
        return True


class PyAutoGUIBackend:
    """Real backend using pyautogui. Requires a display."""

    def __init__(self):
        import pyautogui  # deferred: only needed for live runs
        self.pg = pyautogui
        self.pg.FAILSAFE = True  # slam mouse to a corner to abort

    def press(self, key):
        self.pg.press(key)

    def hotkey(self, *keys):
        self.pg.hotkey(*keys)

    def type_text(self, text):
        self.pg.typewrite(text)

    def activate_window(self, title):
        wins = self.pg.getWindowsWithTitle(title)
        if not wins:
            return False
        wins[0].activate()
        time.sleep(0.5)
        return True


class KillSwitch:
    """Global hotkey handling: toggle pause / emergency stop.

    Uses the `keyboard` package when available; otherwise a no-op stub
    so dry-run and tests work anywhere.
    """

    def __init__(self, toggle_key="f9", stop_key="esc"):
        self.toggle_key = toggle_key
        self.stop_key = stop_key
        self.paused = False
        self.stopped = False
        try:
            import keyboard
            keyboard.add_hotkey(toggle_key, self.toggle)
            keyboard.add_hotkey(stop_key, self.stop)
            log.info("hotkeys armed: %s=pause/resume, %s=stop",
                     toggle_key, stop_key)
        except Exception as exc:  # noqa: BLE001 — optional dependency
            log.warning("keyboard hooks unavailable (%s); hotkeys disabled", exc)

    def toggle(self):
        self.paused = not self.paused
        log.info("paused" if self.paused else "resumed")

    def stop(self):
        self.stopped = True
        log.info("kill-switch engaged — stopping")


def load_sequence(path):
    """Load and validate a key-sequence JSON file. Schema:

    {
      "name": "example",
      "window": "Untitled - Notepad",      # optional: target window title
      "countdown": 3,                      # optional seconds before start
      "steps": [
        {"keys": ["a", "b"], "interval": [0.1, 0.3], "repeats": 5},
        {"type": "text", "text": "hello", "interval": 0.5},
        {"hotkey": ["ctrl", "s"], "interval": [1.0, 2.0]}
      ]
    }
    """
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if not isinstance(cfg.get("steps"), list) or not cfg["steps"]:
        raise ValueError("sequence needs a non-empty 'steps' list")
    for i, step in enumerate(cfg["steps"]):
        if not any(k in step for k in ("keys", "type", "hotkey")):
            raise ValueError(f"step {i}: needs 'keys', 'type', or 'hotkey'")
        iv = step.get("interval", 0.2)
        if isinstance(iv, (int, float)):
            if iv < 0:
                raise ValueError(f"step {i}: interval must be >= 0")
        elif isinstance(iv, list) and len(iv) == 2:
            if not (0 <= iv[0] <= iv[1]):
                raise ValueError(f"step {i}: interval range must satisfy 0 <= min <= max")
        else:
            raise ValueError(f"step {i}: interval must be a number or [min, max]")
    return cfg


def pick_interval(spec):
    """Resolve an interval spec to a concrete delay (randomized if range)."""
    if isinstance(spec, (int, float)):
        return float(spec)
    return random.uniform(spec[0], spec[1])


def run_sequence(cfg, backend, killswitch=None, dry_run=False):
    """Execute a loaded sequence. Returns number of actions performed."""
    ks = killswitch
    if cfg.get("window") and not dry_run:
        if not backend.activate_window(cfg["window"]):
            log.warning("window %r not found; continuing anyway", cfg["window"])
        else:
            log.info("targeting window %r", cfg["window"])

    countdown = cfg.get("countdown", 3)
    if countdown and not dry_run:
        for i in range(countdown, 0, -1):
            log.info("starting in %d...", i)
            time.sleep(1)

    actions = 0
    for step in cfg["steps"]:
        repeats = step.get("repeats", 1)
        for _ in range(repeats):
            if ks and ks.stopped:
                log.info("stopped by kill-switch after %d actions", actions)
                return actions
            while ks and ks.paused and not ks.stopped:
                time.sleep(0.1)
            _do_step(step, backend, dry_run)
            actions += 1
            if not dry_run:
                time.sleep(pick_interval(step.get("interval", 0.2)))
    log.info("sequence %r complete: %d actions", cfg.get("name", "?"), actions)
    return actions


def _do_step(step, backend, dry_run):
    if "keys" in step:
        for key in step["keys"]:
            backend.press(key)
    elif step.get("type") == "text":
        backend.type_text(step["text"])
    elif "hotkey" in step:
        backend.hotkey(*step["hotkey"])
    if dry_run:
        log.info("dry-run step: %s", {k: v for k, v in step.items() if k != "interval"})
