
import json
from datetime import datetime, timedelta
import pytest
from pydantic import ValidationError
from src.core.messages import (
    Window,
    TouristRequest,
    GuideOffer,
    Assignment,
    ScheduleProposal,
)

class TestWindow:
    def test_valid_window(self):
        start = datetime.now()
        end = start + timedelta(hours=1)
        window = Window(start=start, end=end)
        assert window.start == start
        assert window.end == end

    def test_invalid_window_end_before_start(self):
        start = datetime.now()
        end = start - timedelta(hours=1)
        with pytest.raises(ValidationError):
            Window(start=start, end=end)

    def test_invalid_window_end_equal_start(self):
        start = datetime.now()
        with pytest.raises(ValidationError):
            Window(start=start, end=start)

    def test_serialization(self):
        start = datetime(2023, 1, 1, 10, 0, 0)
        end = datetime(2023, 1, 1, 11, 0, 0)
        window = Window(start=start, end=end)

        # to_dict
        d = window.to_dict()
        assert d["start"] == start.isoformat()
        assert d["end"] == end.isoformat()

        # from_dict
        window2 = Window.from_dict(d)
        assert window2.start == start
        assert window2.end == end

        # to_json
        s = window.to_json()
        assert isinstance(s, str)

        # from_json
        window3 = Window.from_json(s)
        assert window3.start == start
        assert window3.end == end


class TestTouristRequest:
    def test_serialization(self):
        start = datetime(2023, 1, 1, 10, 0, 0)
        end = datetime(2023, 1, 1, 11, 0, 0)
        window = Window(start=start, end=end)

        req = TouristRequest(
            tourist_id="tourist1",
            availability=[window],
            budget=100.0,
            preferences=["art", "history"]
        )

        d = req.to_dict()
        assert d["type"] == "TouristRequest"
        assert d["tourist_id"] == "tourist1"
        assert len(d["availability"]) == 1

        req2 = TouristRequest.from_dict(d)
        assert req2.tourist_id == "tourist1"
        assert len(req2.availability) == 1
        assert req2.availability[0].start == start

        s = req.to_json()
        req3 = TouristRequest.from_json(s)
        assert req3.tourist_id == "tourist1"


class TestGuideOffer:
    def test_serialization(self):
        start = datetime(2023, 1, 1, 10, 0, 0)
        end = datetime(2023, 1, 1, 11, 0, 0)
        window = Window(start=start, end=end)

        offer = GuideOffer(
            guide_id="guide1",
            categories=["art"],
            available_window=window,
            hourly_rate=50.0,
            max_group_size=5
        )

        d = offer.to_dict()
        assert d["type"] == "GuideOffer"
        assert d["guide_id"] == "guide1"
        assert d["available_window"]["start"] == start.isoformat()

        offer2 = GuideOffer.from_dict(d)
        assert offer2.guide_id == "guide1"
        assert offer2.available_window.start == start

        s = offer.to_json()
        offer3 = GuideOffer.from_json(s)
        assert offer3.guide_id == "guide1"


class TestScheduleProposal:
    def test_serialization(self):
        start = datetime(2023, 1, 1, 10, 0, 0)
        end = datetime(2023, 1, 1, 11, 0, 0)
        window = Window(start=start, end=end)

        assignment = Assignment(
            tourist_id="tourist1",
            guide_id="guide1",
            time_window=window,
            categories=["art"],
            total_cost=50.0
        )

        proposal = ScheduleProposal(
            proposal_id="prop1",
            assignments=[assignment]
        )

        d = proposal.to_dict()
        assert d["type"] == "ScheduleProposal"
        assert d["proposal_id"] == "prop1"
        assert len(d["assignments"]) == 1

        proposal2 = ScheduleProposal.from_dict(d)
        assert proposal2.proposal_id == "prop1"
        assert len(proposal2.assignments) == 1
        assert proposal2.assignments[0].tourist_id == "tourist1"

        s = proposal.to_json()
        proposal3 = ScheduleProposal.from_json(s)
        assert proposal3.proposal_id == "prop1"
