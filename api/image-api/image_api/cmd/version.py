"""Version command for Image API."""

import argparse

from image_api import __version__


def setup_version_cmd(subparsers: argparse._SubParsersAction):
    """Setup the version command parser."""
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "version",
        help="Show version information.",
        description="Show Image API version information.",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace):
    """Print version information."""
    print(f"Image API version: {__version__}")
