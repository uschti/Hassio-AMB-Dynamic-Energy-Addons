# Azienda Multiservizi Bellinzona (AMB) Dynamic Energy Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://hacs.xyz/)

This Home Assistant integration provides energy price forecasting (Low / High) for the Dynamic Energy Rate ([Tariffa dinamica](https://www.amb.ch/approfondimenti/tariffa-dinamica/)) of Azienda Multiservizi Bellinzona (AMB).

## Features

- Current electricity price sensor (Low / High)
- Remaining duration of the current price slot sensor
- Full schedule sensor with forecast data for charts
- Compatible with [ApexCharts Card](https://github.com/RomRider/apexcharts-card) for visualization
- Efficient polling with caching and retry logic

## Installation

### Via HACS (Custom Repository)

Currently, this integration is not yet included in the official HACS default store.

To install it via HACS, add this repository manually as a custom repository:

1. Go to Home Assistant → HACS → Integrations
2. Click the three-dot menu and select "Custom repositories"
3. Enter the URL of this repository (`https://github.com/uschti/Hassio-AMB-Dynamic-Energy-Addons`)
4. Choose "Integration" as category and confirm
5. Search for "AMB Dynamic Energy" in HACS and install
6. Restart Home Assistant
7. Add the integration from the UI

### Manual Installation

1. Download or clone this repository
2. Copy the `custom_components/amb_dynamic_energy` folder into your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Configure via UI

## Configuration

- None

## Important Notice

This integration is **not officially approved or endorsed by Azienda Multiservizi Bellinzona (AMB)**.

The provided API endpoint is public but unofficially integrated; use at your own discretion.

## License

This project is licensed under the **MIT License**.

Please note this license permits use **for personal, educational, and open-source projects only**.

If you plan to distribute or commercialize this integration or part of its code in a paid product or service, please contact the author for licensing terms.

## Development & Support

For bugs or feature requests, please open an issue on the [GitHub repository](https://github.com/uschti/Hassio-AMB-Dynamic-Energy-Addons).

Contributions are welcome!

---

Made with ❤️ by Andrea Pellegrini ([@uschti](https://github.com/uschti))

---

![Powered for AMB customers](https://raw.githubusercontent.com/uschti/Hassio-AMB-Dynamic-Energy-Addons/refs/heads/main/custom_components/amb_dynamic_energy/amb_dynamic_energy.png)
