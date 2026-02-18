"""Switch entities for InfraGlow visualization toggles."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    SUBENTRY_TYPE_VISUALIZATION,
    RENDERER_EFFECT,
    RENDERER_ALERT,
    CONF_VIZ_INCLUDE_BLACK,
)
from .coordinator import VisualizationCoordinator


@dataclass(frozen=True, kw_only=True)
class InfraGlowSwitchDescription(SwitchEntityDescription):
    """Describes an InfraGlow switch entity."""

    config_key: str = ""
    renderer_types: tuple[str, ...] = (RENDERER_EFFECT,)


SWITCH_DESCRIPTIONS: tuple[InfraGlowSwitchDescription, ...] = (
    InfraGlowSwitchDescription(
        key="enabled",
        translation_key="enabled",
        config_key="enabled",
        entity_category=EntityCategory.CONFIG,
        renderer_types=(RENDERER_EFFECT, RENDERER_ALERT),
    ),
    InfraGlowSwitchDescription(
        key="mirror",
        translation_key="mirror",
        config_key="mirror",
        entity_category=EntityCategory.CONFIG,
        renderer_types=(RENDERER_EFFECT,),
    ),
    InfraGlowSwitchDescription(
        key="include_black",
        translation_key="include_black",
        config_key=CONF_VIZ_INCLUDE_BLACK,
        entity_category=EntityCategory.CONFIG,
        renderer_types=(RENDERER_EFFECT,),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InfraGlow switch entities from subentries."""
    coordinator: VisualizationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VISUALIZATION:
            continue

        renderer_type = subentry.data.get("renderer_type", RENDERER_EFFECT)

        for desc in SWITCH_DESCRIPTIONS:
            if renderer_type not in desc.renderer_types:
                continue
            entities.append(
                InfraGlowSwitch(
                    coordinator, entry, subentry_id, subentry.title, subentry.data, desc,
                )
            )

    async_add_entities(entities)


class InfraGlowSwitch(SwitchEntity):
    """A toggle for a visualization parameter."""

    _attr_has_entity_name = True
    entity_description: InfraGlowSwitchDescription

    def __init__(
        self,
        coordinator: VisualizationCoordinator,
        entry: ConfigEntry,
        subentry_id: str,
        viz_name: str,
        data: dict,
        description: InfraGlowSwitchDescription,
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
        self._attr_is_on = bool(data.get(description.config_key, True if description.key == "enabled" else False))

    @property
    def name(self) -> str:
        label = (self.entity_description.translation_key or self.entity_description.key).replace("_", " ").title()
        return f"{self._viz_name} {label}"

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self._coordinator.update_slot_param(
            self._subentry_id, self.entity_description.config_key, True,
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self._coordinator.update_slot_param(
            self._subentry_id, self.entity_description.config_key, False,
        )
        self.async_write_ha_state()
