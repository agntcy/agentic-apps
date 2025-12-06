#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Guide Agent Entry Point for Container Deployment

The guide agent connects to the scheduler to offer tour services.
"""

import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from agents.guide_agent import main

if __name__ == "__main__":
    main()
