#!/usr/bin/env python3
"""GuardDOG entry point. Real CLI lives in cli.py — this stays thin so both
`python main.py <target>` and `guarddog <target>` (installed) work."""

import sys

from cli import main

if __name__ == "__main__":
    sys.exit(main())
