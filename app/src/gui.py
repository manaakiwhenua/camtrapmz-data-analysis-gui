import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit,
    QFileDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QScrollArea, QInputDialog
)
from PyQt5.QtCore import Qt
from app.src.main import run_pipeline, export_results

class CameraTrapApp(QWidget):
    """
    Simple GUI to run the CamTrapNZ analysis pipeline and export an Excel
    workbook with summary sheets and an embedded chart.

    Workflow:
      1) Browse and pick an .xlsx file.
      2) (Optionally) tick species and set bin size.
      3) Run Analysis.
      4) Export Results → writes Excel with chart in 'CameraTrapRates'.
    """

    def __init__(self):
        """Initialize the GUI window and components."""
        super().__init__()
        self.file_path: str | None = None
        self.selected_sheet: str | None = None
        self.species_checks: list[QCheckBox] = []
        self.results_data: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Configure GUI layout, widgets, and signal connections."""
        self.setWindowTitle("CamTrapNZ Analyzer")
        self.setGeometry(100, 100, 700, 500)

        # File selection
        self.file_label = QLabel("No file selected")
        self.browse_btn = QPushButton("Browse Excel")

        #Species selection (dynamic)
        self.species_checks = []
        self.species_box = QVBoxLayout()
        self.species_group = QWidget()
        self.species_group.setLayout(self.species_box)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.species_group)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(140)
        self.scroll.setMaximumHeight(240)

        # Select All stays OUTSIDE the scroll so it's always visible
        self.select_all_chk = QCheckBox("Select All")
        self.select_all_chk.stateChanged.connect(self._toggle_select_all)

        # Header row: "Select species:" [..............] [Select All]
        header = QHBoxLayout()
        header.addWidget(QLabel("Select species:"))
        header.addStretch()
        header.addWidget(self.select_all_chk)

        # Bin size input
        self.bin_input = QLineEdit()
        self.bin_input.setPlaceholderText("Bin size in days (e.g. 7)")

        # Action buttons
        self.run_btn = QPushButton("Run Analysis")
        self.export_btn = QPushButton("Export Results")
        self.export_btn.setEnabled(False)  # Initially disabled

        # Log output
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.file_label)
        layout.addWidget(self.browse_btn)
        layout.addLayout(header)
        layout.addWidget(self.scroll)
        layout.addWidget(QLabel("Select bin size:"))
        layout.addWidget(self.bin_input)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(QLabel("Log:"))
        layout.addWidget(self.log)
        self.setLayout(layout)

        # Connect buttons to functions
        self.browse_btn.clicked.connect(self._select_file)
        self.run_btn.clicked.connect(self.run_analysis)
        self.export_btn.clicked.connect(self.export_results_clicked)

    def _select_file(self) -> None:
        """Open file dialog to select an Excel file and load species list."""
        path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx)")
        if not path:
            return
        
        self.file_path = path
        try:
            species_count, sheet = self._load_species_from_file()
            self.file_label.setText(f"📁 {path}")
            self.log.append(f"📁 Selected {Path(path).name} — sheet '{sheet}' — {species_count} species")
        except Exception as e:
            self.log.append(f"❌ Failed to inspect file: {e}")
            self.file_path = None
            self.selected_sheet = None
            self.export_btn.setEnabled(False)
    
    def _toggle_select_all(self, state: int) -> None:
        """Toggle all species checkboxes to match the Select All state."""
        # Ignore programmatic PartiallyChecked transitions
        if state == Qt.PartiallyChecked:
            return
        check = (state == Qt.Checked)
        for chk in self.species_checks:
            was = chk.blockSignals(True)
            chk.setChecked(check)
            chk.blockSignals(was)
        # normalize to non-tristate after bulk op
        was = self.select_all_chk.blockSignals(True)
        self.select_all_chk.setTristate(False)
        self.select_all_chk.setCheckState(Qt.Checked if check else Qt.Unchecked)
        self.select_all_chk.blockSignals(was)

    def _update_select_all(self) -> None:
        """Keep Select All in sync with individual boxes."""
        if not self.species_checks:
            was = self.select_all_chk.blockSignals(True)
            self.select_all_chk.setTristate(False)
            self.select_all_chk.setCheckState(Qt.Unchecked)
            self.select_all_chk.blockSignals(was)
            return

        total = len(self.species_checks)
        checked = sum(chk.isChecked() for chk in self.species_checks)

        was = self.select_all_chk.blockSignals(True)
        if checked == 0:
            self.select_all_chk.setTristate(False)
            self.select_all_chk.setCheckState(Qt.Unchecked)
        elif checked == total:
            self.select_all_chk.setTristate(False)
            self.select_all_chk.setCheckState(Qt.Checked)
        else:
            self.select_all_chk.setTristate(True)
            self.select_all_chk.setCheckState(Qt.PartiallyChecked)
        self.select_all_chk.blockSignals(was)
    
    def _load_species_from_file(self) -> tuple[int, str]:
        """Read the workbook, pick a reasonable sheet, and populate species checkboxes.

        Rules:
        - Use "Sheet1" if present.
        - If only one sheet, use that sheet.
        - If multiple sheets, try auto-detect a sheet containing 'Burst_class'.
          If none match, prompt user to choose a sheet.
        """
        if not self.file_path:
            raise ValueError("No file path set.")
        
        xls = pd.ExcelFile(self.file_path, engine="openpyxl")

        sheet_to_use: str | None = None
        # Prefer Sheet1 if it exists
        if "Sheet1" in xls.sheet_names:
            sheet_to_use = "Sheet1"
        # Single-sheet workbooks → use that sheet
        elif len(xls.sheet_names) == 1:
            sheet_to_use = xls.sheet_names[0]
        else:
            # Try auto-detect a reasonable sheet by column presence
            for name in xls.sheet_names:
                try:
                    head = xls.parse(name, nrows=5)
                    if "Burst_class" in head.columns:
                        sheet_to_use = name
                        break
                except Exception:
                    continue
            # If still unknown, prompt the user to pick
            if sheet_to_use is None:
                choice, ok = QInputDialog.getItem(
                    self, "Select Worksheet",
                    "Multiple sheets found. Choose one:",
                    xls.sheet_names, 0, False,
                )
                if not ok:
                    raise RuntimeError("No sheet selected")
                sheet_to_use = choice

        df = xls.parse(sheet_to_use)
        if "Burst_class" not in df.columns:
            raise ValueError(f"Required column 'Burst_class' not found in sheet '{sheet_to_use}'.")

        # Clean species strings
        unique_species = (
            pd.Series(df["Burst_class"])
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )
        unique_species = sorted(unique_species)

        # Clear previous species (leave self.select_all_chk alone)
        for chk in self.species_checks:
            self.species_box.removeWidget(chk)
            chk.deleteLater()
        self.species_checks = []

        # Add species checkboxes (inside scroll)
        for sp in unique_species:
            chk = QCheckBox(sp)
            # keep Select All synchronized with manual changes
            chk.stateChanged.connect(self._update_select_all)
            self.species_checks.append(chk)
            self.species_box.addWidget(chk)

        self.selected_sheet = sheet_to_use
        self._update_select_all()
        return len(unique_species), sheet_to_use

# ------------- Pipeline --------------

    def run_analysis(self) -> None:
        """Run the analysis pipeline and hold the results in memory."""
        if not self.file_path:
            self.log.append("⚠️ Please select a file first.")
            return

        # Safe bin size: default to 7 if blank/invalid
        bin_text = self.bin_input.text().strip()
        try:
            bin_days = int(bin_text) if bin_text else 7
        except ValueError:
            bin_days = 7
            self.log.append("ℹ️ Invalid bin size; using default 7 days.")

        selected = [chk.text() for chk in self.species_checks if chk.isChecked()]
        sheet = getattr(self, "selected_sheet", None)

        results, messages = run_pipeline(
            self.file_path,
            selected_species=selected or None,
            bin_days=bin_days,
            sheet_name=sheet
        )

        if results is None:
            for msg in messages:
                self.log.append(msg)
            self.export_btn.setEnabled(False)
            return
        
        self.results_data = results
        # compact summary instead of step-by-step spam
        n_cam = len(results["summary"])
        n_ind = len(results["independent"])
        n_tr  = len(results["trap_rates"])
        self.log.append(f"✅ Analysis complete — cameras: {n_cam}, detections: {n_ind} (indep), trap-rate species: {n_tr}")
        self.export_btn.setEnabled(True)

# ------------- Export --------------
    
    def export_results_clicked(self) -> None:
        """Write the Excel workbook with embedded chart."""
        if not self.results_data:
            self.log.append("⚠️ No analysis data available. Please run analysis first.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save Results")
        if not folder:
            self.log.append("⚠️ No folder selected. Export cancelled.")
            return

        selected = [chk.text() for chk in self.species_checks if chk.isChecked()]
        species_str = "-".join(selected) if selected else "AllSpecies"
        bin_txt = self.bin_input.text().strip() or "7"
        date_str = datetime.now().strftime("%Y-%m-%d")
        prefix = f"{folder}/camera_trap_{species_str}_bin{bin_txt}_{date_str}"

        out_path = export_results(self.results_data, output_prefix=prefix)
        # export_results currently returns a list with one message; take the path out:
        if out_path is None:
            self.log.append("❌ Export failed (see console).")
            return
        
        self.log.append(f"💾 Saved: {out_path} (chart in 'CameraTrapRates')")

def launch_gui():
    """Launch the Camera Trap Analyzer GUI app."""
    app = QApplication(sys.argv)
    gui = CameraTrapApp()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    launch_gui()
