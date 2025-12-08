#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Tourist Agent Entry Point for Container Deployment

The tourist agent connects to the scheduler to request tour services.
"""

import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from agents.tourist_agent import main

if __name__ == "__main__":
    main()
