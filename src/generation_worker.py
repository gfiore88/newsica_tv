#!/usr/bin/env python3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from newsica.generation.worker import main


if __name__ == "__main__":
    main()
