"""Number entities for InfraGlow visualization tuning."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, SUBENTRY_TYPE_VISUALIZATION, RENDERER_EFFECT
from .coordinator import VisualizationCoordinator


@dataclass(frozen=True, kw_only=True)
class InfraGlowNumberDescription(NumberEntityDescription):
    """Describes an InfraGlow number entity."""

    config_key: str = ""


EFFECT_NUMBERS: tuple[InfraGlowNumberDescription, ...] = (
    InfraGlowNumberDescription(
        key="floor",
        translation_key="floor",
        config_key="floor",
        native_min_value=-1000,
        native_max_value=10000,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    InfraGlowNumberDescription(
        key="ceiling",
        translation_key="ceiling",
        config_key="ceiling",
        native_min_value=-1000,
        native_max_value=10000,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    InfraGlowNumberDescription(
        key="speed_min",
        translation_key="speed_min",
        config_key="speed_min",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    InfraGlowNumberDescription(
        key="speed_max",
        translation_key="speed_max",
        config_key="speed_max",
        native_min_value=0,
        native_max_value=255,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InfraGlow number entities from subentries."""
    coordinator: VisualizationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VISUALIZATION:
            continue
        if subentry.data.get("renderer_type") != RENDERER_EFFECT:
            continue

        for desc in EFFECT_NUMBERS:
            entities.append(
                InfraGlowNumber(
                    coordinator, entry, subentry_id, subentry.title, subentry.data, desc,
                )
            )

    async_add_entities(entities)


class InfraGlowNumber(NumberEntity):
    """A tunable numeric parameter for a visualization."""

    _attr_has_entity_name = True
    entity_description: InfraGlowNumberDescription

    def __init__(
        self,
        coordinator: VisualizationCoordinator,
        entry: ConfigEntry,
        subentry_id: str,
        viz_name: str,
        data: dict,
        description: InfraGlowNumberDescription,
    ) -> None:
        self.entity_description = description
        self._coordinator = coordinator
        self._entry = entry
        self._subentry_id = subentry_id
        self._viz_name = viz_name
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._attr_native_value = float(data.get(description.config_key, 0))

    @property
    def name(self) -> str:
        label = (self.entity_description.translation_key or self.entity_description.key).replace("_", " ").title()
        return f"{self._viz_name} {label}"

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        key = self.entity_description.config_key
        cast_value: int | float = int(value) if key.startswith("speed") else value
        self._coordinator.update_slot_param(self._subentry_id, key, cast_value)
        self.async_write_ha_state()
