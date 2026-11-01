"""CLI entry point for KeyForge."""
import argparse
import logging
import sys

from keyforge import (
    DryRunBackend, PyAutoGUIBackend, KillSwitch,
    load_sequence, run_sequence,
)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="KeyForge — configurable desktop automation with safety rails.")
    ap.add_argument("sequence", help="JSON sequence file (see sequences/example.json)")
    ap.add_argument("--dry-run", action="store_true",
                    help="log actions without touching the keyboard")
    ap.add_argument("--log", default="keyforge.log", help="action log file")
    ap.add_argument("--toggle-key", default="f9", help="global pause/resume hotkey")
    ap.add_argument("--stop-key", default="esc", help="global kill-switch hotkey")
    ap.add_argument("--allow-missing-window", action="store_true",
                    help="continue even if the target window is not found "
                         "(default: abort — keys must never go to the wrong window)")
    args = ap.parse_args(argv)

    try:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.FileHandler(args.log), logging.StreamHandler()],
        )
    except OSError as exc:
        print(f"cannot open log file: {exc}", file=sys.stderr)
        return 2

    try:
        cfg = load_sequence(args.sequence)
    except (OSError, ValueError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        backend, ks = DryRunBackend(), None
        print("DRY RUN — no keys will be pressed.")
    else:
        try:
            backend = PyAutoGUIBackend()
        except Exception as exc:  # noqa: BLE001
            print(f"cannot start live backend: {exc}", file=sys.stderr)
            return 3
        ks = KillSwitch(args.toggle_key, args.stop_key)

    try:
        run_sequence(cfg, backend, ks, dry_run=args.dry_run,
                     require_window=not args.allow_missing_window)
    except RuntimeError as exc:
        print(f"aborted: {exc}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
