#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Scheduler Agent Entry Point for Container Deployment

This is the main entry point for the scheduler agent when deployed as a container.
It follows the ADK GKE deployment pattern.

Usage:
    python main.py --host 0.0.0.0 --port 10000 --mode a2a
    python main.py --mode console  # For local testing
"""

import os
import sys

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Import and run the scheduler agent main function
from agents.scheduler_agent import main

if __name__ == "__main__":
    main()
