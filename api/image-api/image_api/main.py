"""Main entry point for Image API."""

import argparse
import signal
import sys

from image_api.cmd import setup_start_cmd, setup_version_cmd


def handle_signal(sig, frame):
    """Handle termination signals."""
    sys.exit(0)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Image API - Text-to-Image and Image-to-Image Server",
        conflict_handler="resolve",
        add_help=True,
        formatter_class=lambda prog: argparse.HelpFormatter(
            prog, max_help_position=55, indent_increment=2, width=200
        ),
    )
    subparsers = parser.add_subparsers(help="Available commands")

    setup_start_cmd(subparsers)
    setup_version_cmd(subparsers)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
