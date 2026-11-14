# AMB Bellinzona

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

Home Assistant integration for the dynamic electricity tariff ([Tariffa Dinamica](https://www.amb.ch/approfondimenti/tariffa-dinamica/)) of Azienda Multiservizi Bellinzona (AMB). It tells you whether the current tariff is high or low and when it changes next, so you can run boilers, heat pumps or EV chargers in the cheap slots.

Only the AMB "Tariffa Dinamica" product is supported. From 2027 AMB's standard tariff is a single rate, so there is nothing to schedule for it.

## Installation

### HACS (custom repository)

1. In Home Assistant open HACS, then the three-dot menu, then "Custom repositories".
2. Add `https://github.com/uschti/Hassio-AMB-Dynamic-Energy-Addons` with category "Integration".
3. Search for "AMB Bellinzona", download it and restart Home Assistant.

### Manual

Copy `custom_components/amb_bellinzona` into the `custom_components` directory of your Home Assistant configuration and restart.

## Configuration

Go to Settings → Devices & services → Add integration → "AMB Bellinzona". There are no fields to fill in; only one instance can be configured.

## Entities

All entities belong to the "AMB Bellinzona" device.

| Entity | Type | Description |
| --- | --- | --- |
| `sensor.amb_bellinzona_tariff` | enum | Current tariff: `high` or `low` |
| `sensor.amb_bellinzona_next_tariff_change` | timestamp | When the tariff changes next (the frontend shows it as a live countdown) |

## How data is fetched

Data comes from AMB's official public API through the [`amb-bellinzona`](https://pypi.org/project/amb-bellinzona/) library. AMB publishes tomorrow's schedule by 12:00, so the integration makes one call per day at a random minute between 12:30 and 13:30 local time and retries after 30 minutes on failure. The schedule is cached on disk, so restarts do not trigger new calls. If the very first setup cannot reach the API, Home Assistant retries the setup with its own backoff until it succeeds.

## Automation example

```yaml
triggers:
  - trigger: state
    entity_id: sensor.amb_bellinzona_tariff
    to: "low"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.boiler
```

## Migrating from `amb_dynamic_energy`

This integration replaces the old `amb_dynamic_energy` component, which used a third-party proxy. To migrate:

1. Update the repository through HACS (the old and the new integration ship in the same repository).
2. Delete the old "AMB Dynamic Energy" integration entry in Settings → Devices & services.
3. Delete the leftover `custom_components/amb_dynamic_energy` folder.
4. Restart Home Assistant.
5. Add "AMB Bellinzona" in Settings → Devices & services.

Entity IDs changed (the old three sensors, `last_calculated` and `chart_data` are gone), so update your automations and dashboards to the entities listed above.

## Removal

Delete the integration from Settings → Devices & services, then remove the files (HACS: remove the repository) and restart.

## License

MIT
