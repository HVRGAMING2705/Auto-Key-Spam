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
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.log), logging.StreamHandler()],
    )

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

    run_sequence(cfg, backend, ks, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
