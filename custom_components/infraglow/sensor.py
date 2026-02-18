"""Diagnostic sensor entities for InfraGlow visualizations."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, SUBENTRY_TYPE_VISUALIZATION, RENDERER_ALERT
from .coordinator import VisualizationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InfraGlow diagnostic sensors from subentries."""
    coordinator: VisualizationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VISUALIZATION:
            continue
        if subentry.data.get("renderer_type") == RENDERER_ALERT:
            continue

        entities.append(InfraGlowValueSensor(coordinator, entry, subentry_id, subentry.title))
        entities.append(InfraGlowNormalizedSensor(coordinator, entry, subentry_id, subentry.title))

    async_add_entities(entities)


class InfraGlowValueSensor(SensorEntity):
    """Shows the raw sensor value being visualized."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "current_value"

    def __init__(
        self,
        coordinator: VisualizationCoordinator,
        entry: ConfigEntry,
        subentry_id: str,
        viz_name: str,
    ) -> None:
        self._coordinator = coordinator
        self._subentry_id = subentry_id
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_value"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._viz_name = viz_name

    @property
    def name(self) -> str:
        return f"{self._viz_name} Value"

    @property
    def native_value(self) -> float | None:
        slot = self._coordinator.get_slot(self._subentry_id)
        if slot is None:
            return None
        return round(slot.current_value, 2)


class InfraGlowNormalizedSensor(SensorEntity):
    """Shows the normalized 0-100% value being visualized."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "normalized_value"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: VisualizationCoordinator,
        entry: ConfigEntry,
        subentry_id: str,
        viz_name: str,
    ) -> None:
        self._coordinator = coordinator
        self._subentry_id = subentry_id
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_normalized"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._viz_name = viz_name

    @property
    def name(self) -> str:
        return f"{self._viz_name} Level"

    @property
    def native_value(self) -> float | None:
        slot = self._coordinator.get_slot(self._subentry_id)
        if slot is None:
            return None
        return round(slot.normalized_value() * 100, 1)
