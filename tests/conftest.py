from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def effect_config() -> dict[str, Any]:
    return {
        "mode": "grafana",
        "floor": 0,
        "ceiling": 100,
        "color_low": [0, 255, 0],
        "color_high": [255, 0, 0],
        "wled_fx": 2,
        "wled_pal": 3,
        "speed_min": 10,
        "speed_max": 100,
        "intensity_min": 20,
        "intensity_max": 120,
        "mirror": False,
        "reverse": False,
    }


@pytest.fixture
def mock_send_state() -> AsyncMock:
    return AsyncMock()
