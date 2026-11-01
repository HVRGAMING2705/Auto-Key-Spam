"""KeyForge — legitimate desktop automation utility.

Structured automation with safety rails: strict sequence validation,
dry-run mode, kill-switch, per-window targeting (aborts by default if
the target window is missing), action logging, and randomized
human-like intervals.

Backends are abstracted so everything except actual key injection is
testable headless via DryRunBackend.

Schema (see sequences/example.json):
    {
      "name": "example",                       # optional string
      "window": "Untitled - Notepad",           # optional target window title
      "countdown": 3,                           # optional int seconds >= 0
      "steps": [
        {"keys": ["a", "b"], "interval": [0.1, 0.3], "repeats": 5},
        {"type": "text", "text": "hello", "interval": 0.5},
        {"hotkey": ["ctrl", "s"], "interval": [1.0, 2.0]}
      ]
    }
Each step must carry exactly ONE action (keys, text, or hotkey).
``interval`` is a fixed number >= 0 or a [min, max] range with
0 <= min <= max. ``repeats`` is an integer in 1..10000.
"""
import json
import logging
import random
import time

log = logging.getLogger("keyforge")

MAX_REPEATS = 10000


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
        # pyautogui.write is the current API; typewrite is its old alias.
        writer = getattr(self.pg, "write", None) or self.pg.typewrite
        writer(text)

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


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_interval(spec, step_index):
    if _is_number(spec):
        if spec < 0:
            raise ValueError(f"step {step_index}: interval must be >= 0")
    elif isinstance(spec, list) and len(spec) == 2 and all(_is_number(v) for v in spec):
        if not (0 <= spec[0] <= spec[1]):
            raise ValueError(
                f"step {step_index}: interval range must satisfy 0 <= min <= max")
    else:
        raise ValueError(
            f"step {step_index}: interval must be a number or [min, max]")


def _validate_key_list(value, step_index, field):
    if (not isinstance(value, list) or not value
            or any(not isinstance(k, str) or not k for k in value)):
        raise ValueError(
            f"step {step_index}: '{field}' must be a non-empty list of key names")


def validate_sequence(cfg):
    """Validate a parsed sequence dict. Raises ValueError on any problem."""
    if not isinstance(cfg, dict):
        raise ValueError("sequence must be a JSON object")
    if "name" in cfg and not isinstance(cfg["name"], str):
        raise ValueError("'name' must be a string")
    if "window" in cfg and not isinstance(cfg["window"], str):
        raise ValueError("'window' must be a string")
    countdown = cfg.get("countdown", 3)
    if (not isinstance(countdown, int) or isinstance(countdown, bool)
            or countdown < 0):
        raise ValueError("'countdown' must be an integer >= 0")
    steps = cfg.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("sequence needs a non-empty 'steps' list")
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"step {i}: must be an object")
        actions = [k for k in ("keys", "type", "hotkey") if k in step]
        if len(actions) != 1:
            raise ValueError(
                f"step {i}: needs exactly one of 'keys', 'type', or 'hotkey'")
        if "keys" in step:
            _validate_key_list(step["keys"], i, "keys")
        elif "hotkey" in step:
            _validate_key_list(step["hotkey"], i, "hotkey")
        else:  # type step: only "text" is a real action
            if step["type"] != "text":
                raise ValueError(
                    f"step {i}: unknown type {step['type']!r}; only 'text' is supported")
            if not isinstance(step.get("text"), str) or not step["text"]:
                raise ValueError(f"step {i}: text steps need a non-empty 'text'")
        _validate_interval(step.get("interval", 0.2), i)
        repeats = step.get("repeats", 1)
        if (not isinstance(repeats, int) or isinstance(repeats, bool)
                or not (1 <= repeats <= MAX_REPEATS)):
            raise ValueError(
                f"step {i}: 'repeats' must be an integer in 1..{MAX_REPEATS}")
    return cfg


def load_sequence(path):
    """Load and validate a key-sequence JSON file."""
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    return validate_sequence(cfg)


def pick_interval(spec):
    """Resolve an interval spec to a concrete delay (randomized if range)."""
    if _is_number(spec):
        if spec < 0:
            raise ValueError("interval must be >= 0")
        return float(spec)
    if isinstance(spec, list) and len(spec) == 2 and all(_is_number(v) for v in spec):
        if not (0 <= spec[0] <= spec[1]):
            raise ValueError("interval range must satisfy 0 <= min <= max")
        return random.uniform(spec[0], spec[1])
    raise ValueError("interval must be a number or [min, max]")


def _interval_stats(spec):
    """(min, expected, max) seconds for one interval spec."""
    if _is_number(spec):
        return float(spec), float(spec), float(spec)
    return float(spec[0]), (spec[0] + spec[1]) / 2.0, float(spec[1])


def estimate_duration(cfg):
    """Timing estimate for a validated sequence.

    Returns {"actions": int, "min": float, "expected": float, "max": float}
    in seconds, counting only inter-step intervals (not the countdown).
    Mirrors the web simulator's math so both agree.
    """
    validate_sequence(cfg)
    actions = 0
    lo = exp = hi = 0.0
    for step in cfg["steps"]:
        repeats = step.get("repeats", 1)
        actions += repeats
        s_lo, s_exp, s_hi = _interval_stats(step.get("interval", 0.2))
        lo += repeats * s_lo
        exp += repeats * s_exp
        hi += repeats * s_hi
    return {"actions": actions, "min": lo, "expected": exp, "max": hi}


def run_sequence(cfg, backend, killswitch=None, dry_run=False,
                 require_window=True):
    """Execute a validated sequence. Returns number of actions performed.

    Safety: if ``window`` is set and the target window cannot be found,
    the run aborts (RuntimeError) unless ``require_window`` is False.
    In dry-run mode no window exists to check, so the target is logged
    as a would-be check instead of silently passing.
    """
    validate_sequence(cfg)
    ks = killswitch
    if cfg.get("window"):
        if dry_run:
            log.info("dry-run: live run would target window %r", cfg["window"])
        elif not backend.activate_window(cfg["window"]):
            if require_window:
                raise RuntimeError(
                    f"target window {cfg['window']!r} not found; aborting "
                    "rather than sending keys to the wrong window "
                    "(pass --allow-missing-window to override)")
            log.warning("window %r not found; continuing anyway", cfg["window"])
        else:
            log.info("targeting window %r", cfg["window"])

    countdown = cfg.get("countdown", 3)
    if countdown and not dry_run:
        for i in range(countdown, 0, -1):
            if ks and ks.stopped:
                log.info("stopped during countdown")
                return 0
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
            if ks and ks.stopped:
                log.info("stopped by kill-switch after %d actions", actions)
                return actions
            _do_step(step, backend, dry_run)
            actions += 1
            if not dry_run and not (ks and ks.stopped):
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
    else:
        raise ValueError(f"unsupported step: {step!r}")
    if dry_run:
        log.info("dry-run step: %s", {k: v for k, v in step.items() if k != "interval"})
