import sys
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit,
    QFileDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QScrollArea,
    QInputDialog
)
from .main import run_pipeline, export_results
import pandas as pd

class CameraTrapApp(QWidget):
    """
    Camera Trap Analyzer GUI.

    Attributes
    ----------
    file_path : Optional[str]
        Path to the selected Excel file.
    species_checks : List[QCheckBox]
        Dynamically generated species selection checkboxes.
    results_data : dict
        Analysis results after pipeline execution.
    """
    def __init__(self):
        """Initialize the GUI window and components."""
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Configure GUI layout, widgets, and signal connections."""
        self.setWindowTitle("CamTrapNZ Analyzer")
        self.setGeometry(100, 100, 600, 400)

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
        self.scroll.setMinimumHeight(100)
        self.scroll.setMaximumHeight(200)

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
        layout.addWidget(QLabel("Select species:"))
        layout.addWidget(self.scroll)
        layout.addWidget(QLabel("Select bin size:"))
        layout.addWidget(self.bin_input)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(QLabel("Log:"))
        layout.addWidget(self.log)

        self.setLayout(layout)

        # Connect buttons to functions
        self.browse_btn.clicked.connect(self.select_file)
        self.run_btn.clicked.connect(self.run_analysis)
        self.export_btn.clicked.connect(self.export_results)

        self.file_path = None

    def select_file(self):
        """Open file dialog to select an Excel file and load species list."""
        path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx)")
        if path:
            self.file_path = path
            self.load_species_from_file()
            self.file_label.setText(f"📁 {path}")
            self.log.append("File selected.")
    
    def toggle_select_all(self, state):
        """Select or deselect all species checkboxes."""
        for chk in self.species_checks:
            chk.setChecked(state == 2)

    
    def load_species_from_file(self):
        """Extract unique species from the Excel file and populate checkboxes.

        Rules:
        - Use "Sheet1" if present.
        - If only one sheet, use that sheet.
        - If multiple sheets, try auto-detect a sheet containing 'Burst_class'.
          If none match, prompt user to choose a sheet.
        """
        try:
            xls = pd.ExcelFile(self.file_path, engine="openpyxl")

            sheet_to_use = None
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
                        self,
                        "Select Worksheet",
                        "Multiple sheets found. Choose one:",
                        xls.sheet_names,
                        0,
                        False,
                    )
                    if not ok:
                        self.log.append("⚠️ No sheet selected. Loading cancelled.")
                        return
                    sheet_to_use = choice

            df = xls.parse(sheet_to_use)
            if "Burst_class" not in df.columns:
                raise ValueError(f"Required column 'Burst_class' not found in sheet '{sheet_to_use}'.")

            unique_species = sorted(df["Burst_class"].dropna().unique())

            # Clear previous checkboxes (including an existing 'Select All')
            for chk in self.species_checks:
                self.species_box.removeWidget(chk)
                chk.deleteLater()
            self.species_checks = []

            # Remove old 'Select All' if present
            if hasattr(self, "select_all_chk") and self.select_all_chk is not None:
                try:
                    self.select_all_chk.stateChanged.disconnect()
                except Exception:
                    pass
                self.species_box.removeWidget(self.select_all_chk)
                self.select_all_chk.deleteLater()
                self.select_all_chk = None

            # Add "Select All" checkbox
            self.select_all_chk = QCheckBox("Select All")
            self.select_all_chk.stateChanged.connect(self.toggle_select_all)
            self.species_box.addWidget(self.select_all_chk)

            # Add species checkboxes
            for sp in unique_species:
                chk = QCheckBox(sp)
                self.species_checks.append(chk)
                self.species_box.addWidget(chk)

            # Remember the sheet used (may be useful later)
            self.selected_sheet = sheet_to_use

            self.log.append(f"✅ Loaded {len(unique_species)} species from sheet '{sheet_to_use}'.")
        except Exception as e:
            self.log.append(f"❌ Failed to load species: {str(e)}")

    def run_analysis(self):
        """Run the analysis pipeline and update state with results."""
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
        else:
            self.results_data = results
            for msg in messages:
                self.log.append(msg)
            # Helpful summary
            tr = results.get("trap_rates")
            if tr is not None:
                self.log.append(f"📈 Trap rates rows: {len(tr)}; columns: {list(tr.columns)}")
            self.log.append("✅ Analysis completed. You can now export results.")
            self.export_btn.setEnabled(True)

    
    def export_results(self):
        """Export analysis results to Excel with embedded chart."""
        if not hasattr(self, "results_data") or self.results_data is None:
            self.log.append("⚠️ No analysis data available. Please run analysis first.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save Results")
        if not folder:
            self.log.append("⚠️ No folder selected. Export cancelled.")
            return

        species_str = "-".join([chk.text() for chk in self.species_checks if chk.isChecked()])
        bin_text = self.bin_input.text().strip()
        bin_str = bin_text if bin_text else "7"
        date_str = datetime.now().strftime("%Y-%m-%d")
        prefix = f"{folder}/camera_trap_{species_str}_bin{bin_str}_{date_str}"

        export_messages = export_results(self.results_data, output_prefix=prefix)
        for msg in export_messages:
            self.log.append(msg)
        self.log.append(f"📊 Wrote trap rates & chart to sheet 'CameraTrapRates' in: {prefix}_output.xlsx")

def launch_gui():
    """Launch the Camera Trap Analyzer GUI app."""
    app = QApplication(sys.argv)
    gui = CameraTrapApp()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    launch_gui()
