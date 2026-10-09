"""Headless tests for KeyForge: config validation, interval logic, and
dry-run execution. No display or key injection required.
"""
import json
import tempfile
import os

from keyforge import (
    DryRunBackend, KillSwitch, load_sequence, pick_interval, run_sequence,
)

PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


def write_cfg(cfg):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(cfg, fh)
    return path


def main():
    global PASS, FAIL

    good = {"name": "t", "steps": [
        {"keys": ["a", "enter"], "interval": 0.1, "repeats": 2},
        {"type": "text", "text": "hi", "interval": [0.1, 0.2]},
        {"hotkey": ["ctrl", "s"]},
    ]}
    p = write_cfg(good)
    cfg = load_sequence(p)
    check("loads valid config", cfg["name"] == "t")
    os.unlink(p)

    bad_steps = {"name": "t", "steps": [{"interval": 0.1}]}
    p = write_cfg(bad_steps)
    try:
        load_sequence(p)
        check("rejects step without action", False)
    except ValueError:
        check("rejects step without action", True)
    os.unlink(p)

    bad_iv = {"name": "t", "steps": [{"keys": ["a"], "interval": [0.5, 0.1]}]}
    p = write_cfg(bad_iv)
    try:
        load_sequence(p)
        check("rejects inverted range", False)
    except ValueError:
        check("rejects inverted range", True)
    os.unlink(p)

    check("fixed interval passthrough", pick_interval(0.25) == 0.25)
    for _ in range(50):
        v = pick_interval([0.1, 0.3])
        assert 0.1 <= v <= 0.3
    check("randomized interval within range", True)

    # dry-run execution records actions, presses nothing
    backend = DryRunBackend()
    n = run_sequence(good, backend, dry_run=True)
    kinds = [a[0] for a in backend.actions]
    check("dry-run executes all steps", n == 4)  # repeats: 2 + 1 + 1
    check("dry-run recorded presses", ("press", "a") in backend.actions)
    check("dry-run recorded text", ("type", "hi") in backend.actions)
    check("dry-run recorded hotkey", ("hotkey", ("ctrl", "s")) in backend.actions)
    check("repeats expanded", kinds.count("press") == 2 + 2)  # 2 keys x 2 repeats

    # kill-switch stops mid-run
    ks = KillSwitch.__new__(KillSwitch)  # no hotkey registration headless
    ks.paused, ks.stopped = False, False
    big = {"name": "t", "steps": [{"keys": ["a"], "repeats": 100}]}
    orig_do = __import__("keyforge")._do_step
    calls = []
    __import__("keyforge")._do_step = lambda s, b, d: (calls.append(1), backend.press("a"))
    ks.stop()
    n2 = run_sequence(big, backend, ks, dry_run=True)
    __import__("keyforge")._do_step = orig_do
    check("kill-switch halts execution", n2 == 0 and not calls)

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
