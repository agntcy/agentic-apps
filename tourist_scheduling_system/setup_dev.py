#!/usr/bin/env python3
"""
Quick setup script for the reorganized A2A Summit Demo
"""
import os
import sys

def setup_python_path():
    """Add src directory to Python path for development"""
    repo_root = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(repo_root, 'src')

    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    return src_path

# Automatically setup path when imported
setup_python_path()

# Re-export key components for easier imports
try:
    from a2a_summit_demo.core.messages import (
        Assignment,
        GuideOffer,
        ScheduleProposal,
        TouristRequest,
        Window
    )

    from a2a_summit_demo.agents.scheduler_agent import SchedulerAgentExecutor
    from a2a_summit_demo.agents.ui_agent import UIAgentExecutor

    __all__ = [
        'Assignment',
        'GuideOffer',
        'ScheduleProposal',
        'TouristRequest',
        'Window',
        'SchedulerAgentExecutor',
        'UIAgentExecutor'
    ]

except ImportError as e:
    print(f"Warning: Could not import all components: {e}")
    __all__ = []

if __name__ == "__main__":
    print(f"A2A Summit Demo development setup complete!")
    print(f"Src path: {setup_python_path()}")
    print(f"Available components: {__all__}")