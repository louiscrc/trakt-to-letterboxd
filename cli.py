#!/usr/bin/env python3
"""
CLI script to run the Letterboxd-Trakt sync from the project root.

Usage:
    python cli.py
    python cli.py run          # Run sync once
    python cli.py scheduled    # Run on schedule
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from letterboxd_trakt.main import main, run

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "run":
            # Run once
            run()
        elif command == "scheduled":
            # Run on schedule
            import os
            os.environ["SCHEDULED"] = "true"
            main()
        elif command in ["-h", "--help", "help"]:
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
            sys.exit(1)
    else:
        # Default: run once
        run()
