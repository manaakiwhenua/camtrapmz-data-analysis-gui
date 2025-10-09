import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit,
    QFileDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QScrollArea, QInputDialog, QTextBrowser, QDialog, QVBoxLayout
)
from PyQt5.QtCore import Qt
from app.src.main import run_pipeline, export_results

README_URL = "https://github.com/manaakiwhenua/camtrapmz-data-analysis-gui"

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
        super().__init__()
        self.file_path: str | None = None
        self.selected_sheet: str | None = None
        self.species_checks: list[QCheckBox] = []
        self.results_data: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("CamTrapNZ Analyzer")
        self.setGeometry(100, 100, 700, 500)

        # Main layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # File row: label, Browse + Help
        self.file_label = QLabel("No file selected")
        layout.addWidget(self.file_label)

        self.browse_btn = QPushButton("Browse Excel")
        self.help_btn = QPushButton("Help")
        header_row = QHBoxLayout()
        header_row.addWidget(self.browse_btn)
        header_row.addStretch()
        header_row.addWidget(self.help_btn)
        layout.addLayout(header_row)

        self.hint = QLabel(
            'Tip: Export from CamTrapNZ with “Retain subfolders” ON so '
            'Filename looks like images/Cam02/IMG_0001.JPG.'
        )
        self.hint.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.hint)

        # Species selection (dynamic list inside scroll)
        self.species_box = QVBoxLayout()
        self.species_group = QWidget()
        self.species_group.setLayout(self.species_box)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.species_group)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(140)
        self.scroll.setMaximumHeight(240)

        # "Select All" outside scroll
        self.select_all_chk = QCheckBox("Select All")
        self.select_all_chk.stateChanged.connect(self._toggle_select_all)

        species_hdr = QHBoxLayout()
        species_hdr.addWidget(QLabel("Select species:"))
        species_hdr.addStretch()
        species_hdr.addWidget(self.select_all_chk)
        layout.addLayout(species_hdr)
        layout.addWidget(self.scroll)

        # Bin size
        layout.addWidget(QLabel("Select bin size:"))
        self.bin_input = QLineEdit()
        self.bin_input.setPlaceholderText("Bin size in days (e.g. 7)")
        layout.addWidget(self.bin_input)

        # Actions
        self.run_btn = QPushButton("Run Analysis")
        self.export_btn = QPushButton("Export Results")
        self.export_btn.setEnabled(False)

        layout.addWidget(self.run_btn)
        layout.addWidget(self.export_btn)

        # Log
        layout.addWidget(QLabel("Log:"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # Connections
        self.browse_btn.clicked.connect(self._select_file)
        self.help_btn.clicked.connect(self._show_help)
        self.run_btn.clicked.connect(self.run_analysis)
        self.export_btn.clicked.connect(self.export_results_clicked)

    # ---------- Help dialog ----------
    def _show_help(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("CamTrapNZ Analyzer – Help")
        lay = QVBoxLayout(dlg)
        html = f"""
        <h3>CamTrapNZ Analyzer – Help</h3>
        <p>Export from CamTrapNZ with <b>“Retain subfolders”</b> enabled so the camera
        folder appears in <code>Filename</code>.</p>
        <p>Full instructions and screenshots in the
        <a href="{README_URL}">README</a>.</p>
        <hr>
        <p><b>Binning:</b> weeks are left-closed, right-open [start, end);
        cameras outside their active window are marked “NA”.</p>
        """

        view = QTextBrowser()
        view.setOpenExternalLinks(True)   # let the OS/browser open the link
        view.setHtml(html)
        lay.addWidget(view)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)

        dlg.resize(720, 520)
        dlg.exec_()

    # ---------- File & species ----------
    def _select_file(self) -> None:
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
        if state == Qt.PartiallyChecked:
            return
        check = (state == Qt.Checked)
        for chk in self.species_checks:
            was = chk.blockSignals(True)
            chk.setChecked(check)
            chk.blockSignals(was)
        was = self.select_all_chk.blockSignals(True)
        self.select_all_chk.setTristate(False)
        self.select_all_chk.setCheckState(Qt.Checked if check else Qt.Unchecked)
        self.select_all_chk.blockSignals(was)

    def _update_select_all(self) -> None:
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
        if not self.file_path:
            raise ValueError("No file path set.")
        xls = pd.ExcelFile(self.file_path, engine="openpyxl")

        sheet_to_use: str | None = None
        if "Sheet1" in xls.sheet_names:
            sheet_to_use = "Sheet1"
        elif len(xls.sheet_names) == 1:
            sheet_to_use = xls.sheet_names[0]
        else:
            for name in xls.sheet_names:
                try:
                    head = xls.parse(name, nrows=5)
                    if "Burst_class" in head.columns:
                        sheet_to_use = name
                        break
                except Exception:
                    continue
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

        unique_species = (
            pd.Series(df["Burst_class"])
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )
        unique_species = sorted(unique_species)

        # wipe and rebuild species list
        for chk in self.species_checks:
            self.species_box.removeWidget(chk)
            chk.deleteLater()
        self.species_checks = []
        for sp in unique_species:
            chk = QCheckBox(sp)
            chk.stateChanged.connect(self._update_select_all)
            self.species_checks.append(chk)
            self.species_box.addWidget(chk)

        self.selected_sheet = sheet_to_use
        self._update_select_all()
        return len(unique_species), sheet_to_use

    # ---------- Pipeline ----------
    def run_analysis(self) -> None:
        if not self.file_path:
            self.log.append("⚠️ Please select a file first.")
            return

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

        for msg in messages:
            if msg.startswith(("⚠️", "ℹ️", "✅")):
                self.log.append(msg)

        self.results_data = results
        n_cam = len(results["summary"])
        n_ind = len(results["independent"])
        n_tr = len(results["trap_rates"])
        self.log.append(f"✅ Analysis complete — cameras: {n_cam}, detections: {n_ind} (indep), trap-rate species: {n_tr}")
        self.export_btn.setEnabled(True)

    # ---------- Export ----------
    def export_results_clicked(self) -> None:
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
        if out_path is None:
            self.log.append("❌ Export failed (see console).")
            return
        self.log.append(f"💾 Saved: {out_path} (chart in 'CameraTrapRates')")


def launch_gui():
    app = QApplication(sys.argv)
    gui = CameraTrapApp()
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    launch_gui()
