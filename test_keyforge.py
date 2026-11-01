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

    # --- v2.0 validation holes (previously silently accepted) ---
    def rejects(label, cfg):
        p = write_cfg(cfg)
        try:
            load_sequence(p)
            check(label, False)
        except ValueError:
            check(label, True)
        finally:
            os.unlink(p)

    rejects("rejects bogus type", {"steps": [{"type": "bogus"}]})
    rejects("rejects text step without text", {"steps": [{"type": "text"}]})
    rejects("rejects keys as string", {"steps": [{"keys": "abc"}]})
    rejects("rejects empty keys", {"steps": [{"keys": []}]})
    rejects("rejects empty hotkey", {"steps": [{"hotkey": []}]})
    rejects("rejects repeats 0", {"steps": [{"keys": ["a"], "repeats": 0}]})
    rejects("rejects negative repeats", {"steps": [{"keys": ["a"], "repeats": -3}]})
    rejects("rejects repeats over cap", {"steps": [{"keys": ["a"], "repeats": 10001}]})
    rejects("rejects two actions in one step",
            {"steps": [{"keys": ["a"], "hotkey": ["ctrl", "s"]}]})
    rejects("rejects string countdown", {"steps": [{"keys": ["a"]}], "countdown": "soon"})
    rejects("rejects negative countdown", {"steps": [{"keys": ["a"]}], "countdown": -1})
    rejects("rejects non-object config", [1, 2, 3])
    rejects("rejects negative interval", {"steps": [{"keys": ["a"], "interval": -0.5}]})
    try:
        pick_interval([0.5])
        check("pick_interval rejects bad range", False)
    except ValueError:
        check("pick_interval rejects bad range", True)

    # bogus step must not silently count as an action
    b2 = DryRunBackend()
    try:
        run_sequence({"name": "x", "steps": [{"type": "bogus"}]}, b2, dry_run=True)
        check("bogus step raises in run", False)
    except ValueError:
        check("bogus step raises in run", True)

    # window targeting: missing window aborts by default, runs with override
    class MissBackend(DryRunBackend):
        def activate_window(self, title):
            return False
    try:
        run_sequence({"name": "x", "window": "No Such App", "steps": [{"keys": ["a"]}]},
                     MissBackend(), dry_run=False)
        check("missing window aborts by default", False)
    except RuntimeError:
        check("missing window aborts by default", True)
    n3 = run_sequence({"name": "x", "window": "No Such App", "steps": [{"keys": ["a"]}]},
                      MissBackend(), dry_run=False, require_window=False)
    check("missing window runs with override", n3 == 1)

    # pause/resume state machine: paused run makes no progress until resumed
    import threading
    ks2 = KillSwitch.__new__(KillSwitch)
    ks2.paused, ks2.stopped = True, False
    b3 = DryRunBackend()
    done = []
    t = threading.Thread(target=lambda: done.append(
        run_sequence({"name": "x", "steps": [{"keys": ["a"], "repeats": 2}]},
                     b3, ks2, dry_run=True)))
    t.start()
    import time as _time
    _time.sleep(0.35)
    check("paused run makes no progress", len(b3.actions) == 0 and t.is_alive())
    ks2.toggle()  # resume
    t.join(timeout=5)
    check("resumed run completes", done == [2] and not t.is_alive())

    # timing estimate math matches the schema (fixed + range, repeats)
    est = __import__("keyforge").estimate_duration(
        {"name": "x", "steps": [
            {"keys": ["a"], "interval": 0.5, "repeats": 2},
            {"keys": ["b"], "interval": [0.1, 0.3]},
        ]})
    check("estimate actions", est["actions"] == 3)
    check("estimate min/expected/max",
          est["min"] == 1.1 and est["expected"] == 1.2 and est["max"] == 1.3)

    # the shipped example loads, validates, and dry-runs cleanly
    ex = load_sequence(os.path.join(os.path.dirname(__file__), "sequences", "example.json"))
    check("shipped example.json loads", ex["name"] == "notepad typing demo")
    b4 = DryRunBackend()
    n4 = run_sequence(ex, b4, dry_run=True)
    check("shipped example dry-runs", n4 == 6)  # 1 + 1 + 3 repeats + 1

    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
