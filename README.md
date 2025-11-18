# CamTrapNZ Data Analysis GUI

A lightweight **PyQt5 desktop app** for analyzing camera-trap detection data exported from CamTrapNZ.
It summarizes effort, identifies independent detections, computes trap rates, and exports formatted Excel reports with confidence-interval charts.

## 🧭 Overview

The app streamlines a standard analysis workflow for CamTrapNZ projects:
- Summarise first/last photo dates by camera.
- Identify **independent detections** (≥30‑minute rule).
- Compute **trap rates per 100 camera‑days** with **95% CIs (Wilson method)**.
- Visualise rates with error bars and export tidy Excel tables.

---

## 🧩 Input Data Requirements

### ✅ What the Analyzer needs

The Excel export fed into this tool must have a `Filename` column where each entry makes the camera ID or name obvious. As long as the identifier is present somewhere in that string, the Analyzer can infer the camera. Common ways this happens in CamTrapNZ exports:

1. **Camera IDs inside filenames** — your images already use names such as `Cam02_IMG_0001.JPG`, so the camera identifier is embedded in each filename.
2. **Camera-specific folders** — your images are organised into folders like `Cam01/IMG_0001.JPG`. When CamTrapNZ builds the Excel export, the folder name becomes part of the `Filename` path and therefore carries the camera identifier.

Example structure (folder-per-camera):

```text
images/
├── Cam01/
│ ├── IMG_0001.JPG
│ ├── IMG_0002.JPG
├── Cam02/
│ └── IMG_0500.JPG
```

Regardless of layout, the Excel export should show the camera identifier in each `Filename`, for example:
- `images/Cam01/IMG_0001.JPG` when folders are preserved
- `images/Hedgehog/Cam02_IMG_0001.JPG` when filenames carry the `Cam02` prefix

### 🧠 Priority for Camera ID detection

The Analyzer determines the “Camera” column automatically in this order:
1. Existing `Camera` column (if non-empty)  
2. `Label` column (verbatim)  
3. From `Filename` — camera folder (2nd segment) or any embedded prefix (e.g., `Cam02_IMG_0001.JPG`)  
4. Fallback regex (e.g., finds “cam12” elsewhere in the text)

If all methods fail, the Analyzer will **warn you before continuing**.

---

## 🪟 Download for Windows (End Users)

- Download **`CamTrapNZAnalyzer.exe`** from the project’s Releases page.
- Place it anywhere (Desktop or Documents).
- Double-click to open — **no installation required**.

### System Requirements
- Windows 10 or 11  
- No admin rights or Python installation needed

### First Run
SmartScreen may warn about an unknown publisher:  
→ Click “More info” → “Run anyway” (app runs fully offline).

### Update or Remove
- To update: download and replace the `.exe` file  
- To remove: delete the `.exe` and any exported results

---

## 🖥️ Using the GUI

1. **Launch the app**
   - Windows: double-click `CamTrapNZAnalyzer.exe`
   - macOS/Linux (dev mode): `poetry run camtrapnzanalyzer`

2. **Select your Excel file**
   - The app auto-detects the correct sheet or lets you pick one.
   - If cameras can’t be inferred, a warning dialog explains how to fix it.

3. **Select species**
   - Use “Select All” to include all species or tick specific ones.

4. **Run Analysis**
   - The app summarizes camera usage, computes trap rates, and builds weekly (or custom-bin) detection histories.

5. **Export Results**
   - Produces a single Excel workbook:
     - `CameraDateSummary`
     - `CameraTrapRates` (with chart)
     - `IndependentDetections`
     - One sheet per species for detection histories

---

## 📊 Excel Output Details

The export writes `<prefix>_output.xlsx` with:

- **`CameraDateSummary`** — camera, first/last dates, number of days  
- **`CameraTrapRates`** — columns: `Species`, `Rate_per100CamDays`, `Lower95CI`, `Upper95CI`, `MinusBar`, `PlusBar`  
- **`IndependentDetections`** — 30-minute de-duplicated records  
- **Detection history sheets** — one per species  

The chart on `CameraTrapRates` shows bars at `Rate_per100CamDays` with error bars that end at `Lower95CI` and `Upper95CI` (implemented via `MinusBar = Rate − Lower95CI` and `PlusBar = Upper95CI − Rate`).

---

## 🧰 Developer Install

```bash
poetry install
poetry run camtrapnzanalyzer

## Build a Windows EXE (For Developers)

Builds must be made on Windows (PyInstaller can’t cross‑compile from macOS/Linux).

1) Prepare environment
- Install Python 3.13, Git, and PowerShell.
- `python -m venv venv`
- `.\venv\Scripts\Activate.ps1`
- `python -m pip install -U pip wheel`
- `pip install pyinstaller PyQt5 pandas openpyxl numpy xlsxwriter`

2) Build
- One‑file, windowed GUI:
  - `python -m PyInstaller app\src\gui.py --name CamTrapNZAnalyzer --onefile --windowed --clean --hidden-import PyQt5.sip --collect-submodules openpyxl --collect-submodules xlsxwriter --exclude-module PyQt5.QtWebEngineWidgets --exclude-module PyQt5.QtWebEngineCore --exclude-module PyQt5.QtWebChannel --exclude-module PyQt5.QtWebSockets  --exclude-module PyQt5.QtMultimedia --exclude-module PyQt5.QtNetwork --exclude-module pandas.tests`
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
