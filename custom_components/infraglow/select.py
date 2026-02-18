"""WLED effect select entity for InfraGlow visualizations."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    SUBENTRY_TYPE_VISUALIZATION,
    RENDERER_EFFECT,
    EFFECT_OPTIONS,
)
from .coordinator import VisualizationCoordinator

_EFFECT_ID_TO_NAME = {str(k): v for k, v in EFFECT_OPTIONS.items()}
_EFFECT_NAME_TO_ID = {v: k for k, v in EFFECT_OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InfraGlow effect select entities from subentries."""
    coordinator: VisualizationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VISUALIZATION:
            continue
        if subentry.data.get("renderer_type") != RENDERER_EFFECT:
            continue

        entities.append(InfraGlowEffectSelect(coordinator, entry, subentry_id, subentry.title, subentry.data))

    async_add_entities(entities)


class InfraGlowEffectSelect(SelectEntity):
    """Dropdown to pick the active WLED effect for a visualization."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "wled_effect"

    def __init__(
        self,
        coordinator: VisualizationCoordinator,
        entry: ConfigEntry,
        subentry_id: str,
        viz_name: str,
        data: dict,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._subentry_id = subentry_id
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_effect"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._attr_options = list(EFFECT_OPTIONS.values())
        self._viz_name = viz_name

        fx_id = str(data.get("wled_fx", 0))
        self._attr_current_option = _EFFECT_ID_TO_NAME.get(fx_id, "Solid")

    @property
    def name(self) -> str:
        return f"{self._viz_name} Effect"

    async def async_select_option(self, option: str) -> None:
        fx_id = _EFFECT_NAME_TO_ID.get(option)
        if fx_id is None:
            return
        self._attr_current_option = option
        self._coordinator.update_slot_param(self._subentry_id, "wled_fx", fx_id)
        self.async_write_ha_state()
