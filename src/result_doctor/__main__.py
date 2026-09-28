"""`python -m result_doctor` so the CLI is runnable before it is installed."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
