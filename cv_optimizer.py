"""Spray and Pray — CV optimization and job application tracking tool.

Entry point: `cv-opt` launches the interactive TUI dashboard.
"""

from cv_optimizer.tui.app import main as tui_main


def main() -> None:
    tui_main()


if __name__ == "__main__":
    main()
