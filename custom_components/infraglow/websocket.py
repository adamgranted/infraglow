"""WebSocket API for InfraGlow card."""

from __future__ import annotations

from types import MappingProxyType

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import voluptuous as vol

from .config_flow import MODE_LABELS, _build_subentry_data
from .const import DOMAIN, SUBENTRY_TYPE_VISUALIZATION


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register InfraGlow websocket commands."""
    websocket_api.async_register_command(hass, handle_get_config)
    websocket_api.async_register_command(hass, handle_create_viz)
    websocket_api.async_register_command(hass, handle_delete_viz)
    websocket_api.async_register_command(hass, handle_update_viz)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "infraglow/get_config",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def handle_get_config(hass, connection, msg):
    """Return visualization config for the card: subentry data + entity mapping."""
    entry_id = msg["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    ent_reg = er.async_get(hass)
    all_entities = er.async_entries_for_config_entry(ent_reg, entry_id)

    visualizations = []
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VISUALIZATION:
            continue

        entity_map = {}
        prefix = entry_id + "_" + subentry_id + "_"
        for ent in all_entities:
            if not ent.unique_id:
                continue
            if ent.unique_id.startswith(prefix):
                key = ent.unique_id[len(prefix):]
                entity_map[key] = ent.entity_id

        viz_data = dict(subentry.data)
        viz_data["subentry_id"] = subentry_id
        viz_data["title"] = subentry.title
        viz_data["entity_map"] = entity_map
        visualizations.append(viz_data)

    connection.send_result(msg["id"], {"visualizations": visualizations})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "infraglow/create_viz",
        vol.Required("entry_id"): str,
        vol.Required("mode"): str,
        vol.Required("params"): dict,
    }
)
@websocket_api.async_response
async def handle_create_viz(hass, connection, msg):
    """Create a new visualization subentry from the Lovelace card."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    data = _build_subentry_data(msg["params"], msg["mode"])
    title = msg["params"].get("name") or MODE_LABELS.get(msg["mode"], msg["mode"])

    subentry = ConfigSubentry(
        data=MappingProxyType(data),
        subentry_type=SUBENTRY_TYPE_VISUALIZATION,
        title=title,
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    connection.send_result(msg["id"], {"success": True, "subentry_id": subentry.subentry_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "infraglow/delete_viz",
        vol.Required("entry_id"): str,
        vol.Required("subentry_id"): str,
    }
)
@websocket_api.async_response
async def handle_delete_viz(hass, connection, msg):
    """Remove a visualization subentry."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    if msg["subentry_id"] not in entry.subentries:
        connection.send_error(msg["id"], "not_found", "Subentry not found")
        return

    hass.config_entries.async_remove_subentry(entry, msg["subentry_id"])
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "infraglow/update_viz",
        vol.Required("entry_id"): str,
        vol.Required("slot_id"): str,
        vol.Required("param"): str,
        vol.Required("value"): vol.Any(int, float, bool, str, list),
    }
)
@websocket_api.async_response
async def handle_update_viz(hass, connection, msg):
    """Handle live parameter updates from the Lovelace card."""
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    value = msg["value"]
    param = msg["param"]

    if param in ("color_low", "color_high", "color_mid", "flash_color"):
        value = [int(c) for c in value]

    coordinator.update_slot_param(msg["slot_id"], param, value)
    connection.send_result(msg["id"], {"success": True})
