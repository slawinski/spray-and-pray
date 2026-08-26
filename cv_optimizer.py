"""Spray and Pray — CV optimization and job application tracking tool.

Entry points:
  `cv-opt`                     → interactive TUI dashboard
  `cv-opt discover [flags]`    → standalone automated job discovery
"""

import sys

from cv_optimizer.tui.app import main as tui_main


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "discover":
        from cv_optimizer.discovery.cli import run_discovery

        sys.exit(run_discovery(sys.argv[2:]))
    tui_main()


if __name__ == "__main__":
    main()
