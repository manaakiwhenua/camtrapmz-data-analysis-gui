# CamTrapNZ Data Analysis GUI

A Python-based GUI application for analyzing camera-trap detection data. Designed to support wildlife monitoring workflows in Aotearoa New Zealand using outputs from CamTrapNZ.

## 🧭 Overview

This application provides an easy-to-use graphical interface for processing camera-trap image detection data. It includes tools for summarising image dates, identifying independent detections, calculating detection rates with confidence intervals, and visualising the results — all within a local Python environment.

## 📂 Project Structure

All core functionality is implemented as reusable Python functions inside the [`app/`](./app) directory:

- `summarise_camera_dates` – Defines functions for extracting first and last photo dates per camera
- `identify_independent_detections` – Functions to identify independent detection events based on a user-defined time threshold
- `calculate_camera_trap_rates` – Functions to calculate detection rates and bootstrap confidence intervals
- `plot_trap_rates` – Functions to generate visualisations of detection rates with error bars
- `main.py` – Launches the GUI and connects all components

## 🖥️ GUI Features

- Upload detection data from Excel or CSV
- Specify parameters such as species column, and time threshold (bin size)
- Process data using modular analysis steps
- Visualise detection rates and export summaries
- Export results to Excel and PNG

## 🔽 Download

Go to [Releases](https://github.com/manaakiwhenua/camtrapmz-data-analysis-gui/releases) and download the latest executable:

- 🪟 `camtrapnz.exe` (Windows)
- 🍎 `camtrapnz` (macOS)
- 🐧 `camtrapnz` (Linux)

## 🚀 Usage

Double-click the executable to launch the Camera Trap Data Analysis GUI.

## 📊 Outputs

- Cleaned detection datasets
- Detection rates per species/site
- Summary plots and Excel exports

## 👥 Contributors

Maintained by the Digital Strategy Team at Manaaki Whenua – Landcare Research.

## 📄 License

[Specify your license here — MIT, Apache-2.0, etc.]

## 📬 Contact

For feature requests or bug reports, please use [GitHub Issues](https://github.com/manaakiwhenua/camtrapmz-data-analysis-gui/issues).