from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.infraglow.wled_client import WLEDClient


def test_base_url_property() -> None:
    client = WLEDClient("wled.local", 8080)
    assert client.base_url == "http://wled.local:8080"


def test_get_total_leds_from_cached_info() -> None:
    client = WLEDClient("wled.local")
    assert client.get_total_leds() == 0
    client._info = {"leds": {"count": 42}}  # noqa: SLF001 - test internal cache behavior
    assert client.get_total_leds() == 42


@pytest.mark.asyncio
async def test_set_segment_effect_builds_expected_payload() -> None:
    client = WLEDClient("wled.local")
    client._send_state = AsyncMock()  # noqa: SLF001 - intercept network send

    await client.set_segment_effect(
        1,
        fx=10,
        pal=3,
        sx=500,
        ix=-20,
        colors=[[1, 2, 3], [4, 5, 6], [7, 8, 9]],
        mirror=True,
        reverse=False,
    )

    client._send_state.assert_awaited_once_with(  # noqa: SLF001
        {
            "seg": [
                {
                    "id": 1,
                    "fx": 10,
                    "pal": 3,
                    "sx": 255,
                    "ix": 0,
                    "col": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                    "mi": True,
                    "rev": False,
                    "frz": False,
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_set_segment_colors_uses_hex_colors() -> None:
    client = WLEDClient("wled.local")
    client._send_state = AsyncMock()  # noqa: SLF001

    await client.set_segment_colors(2, [(255, 0, 16), (0, 15, 255)])
    client._send_state.assert_awaited_once_with({"seg": [{"id": 2, "i": ["FF0010", "000FFF"]}]})  # noqa: SLF001


@pytest.mark.asyncio
async def test_set_all_leds_expands_segment_zero() -> None:
    client = WLEDClient("wled.local")
    client._send_state = AsyncMock()  # noqa: SLF001
    client._info = {"leds": {"count": 5}}  # noqa: SLF001

    await client.set_all_leds([(1, 2, 3)] * 5)
    client._send_state.assert_awaited_once_with(  # noqa: SLF001
        {"seg": [{"id": 0, "start": 0, "stop": 5, "i": ["010203"] * 5}]}
    )


@pytest.mark.asyncio
async def test_get_info_with_http_mocking() -> None:
    client = WLEDClient("wled.local")
    payload = {"leds": {"count": 24}, "arch": "ESP32"}

    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value=payload)

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None

    mock_session = SimpleNamespace(get=lambda *args, **kwargs: mock_context)
    client._ensure_session = AsyncMock(return_value=mock_session)  # noqa: SLF001

    data = await client.get_info()
    assert data == payload
    assert client.get_total_leds() == 24
