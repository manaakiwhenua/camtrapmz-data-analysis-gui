# CamTrapNZ Data Analysis GUI

A lightweight PyQt5 app for analyzing camera‑trap detection data and exporting results to Excel with confidence‑interval charts.

## Overview

The app streamlines a common workflow:
- Summarise first/last photo dates by camera.
- Identify independent detections (30‑minute rule).
- Compute trap rates per 100 camera‑days with 95% CIs (Wilson method).
- Visualise rates with error bars and export tidy tables to Excel.

## Requirements

- Python 3.13 (as set in `pyproject.toml`).
- Poetry for local development, or a Windows machine to build a one‑file EXE.

## Install (dev)

- `poetry install`
- Run the GUI: `poetry run camtrapnzanalyzer` (entry point → `app.src.gui:launch_gui`).

## Using the GUI

- Browse to an Excel file. The app will:
  - Use sheet "Sheet1" if present; if the workbook has only one sheet, it uses that; otherwise it auto‑detects a sheet containing `Burst_class` or prompts you to choose.
- Select species (or use Select All) and optionally set a bin size (days) for detection histories.
- Click Run Analysis, then Export Results to write an Excel workbook.

## Expected Input Columns

- `Label` (camera name, e.g., Cam01)
- `Burst_class` (species)
- `Date_taken` (photo timestamp)
- Optional: `Count`

## Excel Output

The export writes `<prefix>_output.xlsx` with:
- `CameraDateSummary` — camera, first/last dates, number of days.
- `CameraTrapRates` — columns: `Species`, `Rate_per100CamDays`, `Lower95CI`, `Upper95CI`, `MinusBar`, `PlusBar`.
- `IndependentDetections` — 30‑minute de‑duplicated records.
- Per‑species sheets with detection histories.

The chart on `CameraTrapRates` shows bars at `Rate_per100CamDays` with error bars that end at `Lower95CI` and `Upper95CI` (implemented via `MinusBar = Rate − Lower95CI` and `PlusBar = Upper95CI − Rate`).

## Download for Windows (End Users)

- A ready‑to‑run Windows app will be published under Releases.
- Download `CamTrapNZAnalyzer.exe` and place it anywhere (e.g., Desktop or Documents).
- Double‑click to open the app.

System requirements
- Windows 10 or 11.
- No admin rights required. No Python installation required.

First‑run notes
- SmartScreen may warn about an unknown publisher:
  - Click “More info” → “Run anyway”. The app runs fully offline.

Uninstall / Update
- To uninstall: delete the `CamTrapNZAnalyzer.exe` file and any exported results.
- To update: download the new `CamTrapNZAnalyzer.exe` from Releases and replace the old one.

Where to get it
- Releases page: will be shared with each version. If you need an advance copy, contact the maintainer.

## Troubleshooting

- No species shown after selecting a file: ensure the chosen sheet has a `Burst_class` column.
- Error bars look off: check `MinusBar`/`PlusBar` values in `CameraTrapRates` — the chart reads those columns directly.
- macOS/Linux users: run via Poetry; packaging instructions above are Windows‑only.

## Build a Windows EXE (For Developers)

Builds must be made on Windows (PyInstaller can’t cross‑compile from macOS/Linux).

1) Prepare environment
- Install Python 3.13, Git, and PowerShell.
- `py -3.13 -m venv .venv && .venv\Scripts\activate`
- `pip install -U pip poetry`
- `poetry install --with dev`

2) Build
- One‑file, windowed GUI:
  - `poetry run pyinstaller -F -w --name CamTrapNZAnalyzer --gui-script camtrapnzanalyzer --collect-all PyQt5 --collect-all matplotlib --collect-all pandas --collect-submodules openpyxl --collect-submodules xlsxwriter`
- Output: `dist\CamTrapNZ.exe`

Notes
- Use `--onedir` instead of `-F` for faster startup while testing.
- Add resources with `--add-data "from\path;to"` if you later include non‑code assets.

## Project Structure

- `app/src/analysis.py` — parsing/cleaning, independent detections, rate + CI computation.
- `app/src/main.py` — pipeline orchestration and Excel export.
- `app/src/plotter.py` — builds the Excel chart with error bars.
- `app/src/gui.py` — PyQt5 GUI.

## Support

For feature requests or bug reports, please open an issue in this repository.
