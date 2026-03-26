"""YouRip – entry point."""

import sys


def main() -> None:
    try:
        from gui import YouRipApp
    except ImportError as exc:
        print(f"Failed to import GUI: {exc}", file=sys.stderr)
        print("Run: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    app = YouRipApp()
    app.mainloop()


if __name__ == "__main__":
    main()
