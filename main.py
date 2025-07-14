#!/usr/bin/env python3
"""
Main entry point for the Minecraft Server Scanner application.
This file simplifies running the application without dealing with import issues.
"""

import sys
import os
from src.__init__ import main

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    main()
