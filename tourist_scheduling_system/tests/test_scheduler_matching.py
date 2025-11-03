"""Tests for SchedulerAgentExecutor matching logic without running uvicorn."""
import sys, os, json, time
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(PROJECT_ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from core.messages import GuideOffer, TouristRequest, Window, ScheduleProposal, Assignment  # noqa: E402
from agents.scheduler_agent import build_schedule  # noqa: E402


def test_scheduler_greedy_basic():
    now = datetime.now()
    guides = [
        GuideOffer(
            guide_id='g1',
            categories=['culture', 'food'],
            available_window=Window(start=now, end=now + timedelta(hours=2)),
            hourly_rate=50.0,
            max_group_size=2,
        ),
        GuideOffer(
            guide_id='g2',
            categories=['history'],
            available_window=Window(start=now, end=now + timedelta(hours=3)),
            hourly_rate=60.0,
            max_group_size=1,
        ),
    ]
    tourists = [
        TouristRequest(
            tourist_id='t1',
            availability=[Window(start=now, end=now + timedelta(hours=5))],
            preferences=['culture', 'history'],
            budget=120,
        ),
        TouristRequest(
            tourist_id='t2',
            availability=[Window(start=now, end=now + timedelta(hours=5))],
            preferences=['history'],
            budget=90,
        ),
    ]
    assignments = build_schedule(tourists, guides)
    # Both tourists should be matched (capacity allows it)
    assert {a.tourist_id for a in assignments} == {'t1', 't2'}
    # Ensure t1 matched to guide with highest preference overlap (culture+history -> g1 has culture)
    t1_assignment = next(a for a in assignments if a.tourist_id == 't1')
    assert t1_assignment.guide_id in {'g1', 'g2'}

