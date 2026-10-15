#!/usr/bin/env python3
"""Launch the BC-FL-SRV Research & Testing Platform web interface.

Usage:
    python scripts/run_ui.py [--port 8000] [--host 127.0.0.1] [--no-browser]
"""

import argparse
import sys
import webbrowser
from pathlib import Path

# Add src to python path
root = Path(__file__).resolve().parents[1]
if str(root / "src") not in sys.path:
    sys.path.insert(0, str(root / "src"))

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="BC-FL-SRV Research Platform UI")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("\n" + "═" * 65)
    print("  BC-FL-SRV Research & Testing Platform")
    print(f"  Access the platform at: {url}")
    print("═" * 65 + "\n")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run("bcflsrv.ui.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
