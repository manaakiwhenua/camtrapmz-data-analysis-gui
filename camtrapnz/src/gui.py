import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit,
    QFileDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QScrollArea
)
from .main import run_pipeline, export_results

DEFAULT_SPECIES = ["Stoat", "Ferret", "Cat", "Pig", "Bird", "Dog", "Possum", "Rat", "Hedgehog", "Rabbit", "Mouse", "Weasel", "Other"]

class CameraTrapApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Camera Trap Analyzer")
        self.setGeometry(100, 100, 600, 400)

        self.file_label = QLabel("No file selected")
        self.browse_btn = QPushButton("Browse Excel")
        self.run_btn = QPushButton("Run Analysis")
        self.export_btn = QPushButton("Export Results")
        self.export_btn.setEnabled(False)  # Initially disabled
        self.bin_input = QLineEdit()
        self.bin_input.setPlaceholderText("Bin size in days (e.g. 7)")
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        # Species checkboxes
        self.species_checks = [QCheckBox(sp) for sp in DEFAULT_SPECIES]
        species_box = QVBoxLayout()
        for chk in self.species_checks:
            species_box.addWidget(chk)
        species_group = QWidget()
        species_group.setLayout(species_box)
        scroll = QScrollArea()
        scroll.setWidget(species_group)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(100)
        scroll.setMaximumHeight(200)

        layout = QVBoxLayout()
        layout.addWidget(self.file_label)
        layout.addWidget(self.browse_btn)
        layout.addWidget(QLabel("Select species:"))
        layout.addWidget(scroll)
        layout.addWidget(QLabel("Select bin size:"))
        layout.addWidget(self.bin_input)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.log)
        self.setLayout(layout)

        self.browse_btn.clicked.connect(self.select_file)
        self.run_btn.clicked.connect(self.run_analysis)
        self.export_btn.clicked.connect(self.export_results)

        self.file_path = None

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx)")
        if path:
            self.file_path = path
            self.file_label.setText(f"📁 {path}")
            self.log.append("File selected.")

    def run_analysis(self):
        results, messages = run_pipeline(self.file_path,
                                 selected_species=[chk.text() for chk in self.species_checks if chk.isChecked()],
                                 bin_days=int(self.bin_input.text()))

        if results is None:
            for msg in messages:
                self.log.append(msg)
            self.export_btn.setEnabled(False)
        else:
            self.results_data = results
            for msg in messages:
                self.log.append(msg)
            self.log.append("✅ Analysis completed. You can now export results.")
            self.export_btn.setEnabled(True)

    
    def export_results(self):
        if not hasattr(self, "results_data") or self.results_data is None:
            self.log.append("⚠️ No analysis data available. Please run analysis first.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save Results")
        if not folder:
            self.log.append("⚠️ No folder selected. Export cancelled.")
            return

        prefix = f"{folder}/camera_trap"
        export_messages = export_results(self.results_data, output_prefix=prefix)
        for msg in export_messages:
            self.log.append(msg)

def launch_gui():
    app = QApplication(sys.argv)
    gui = CameraTrapApp()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    launch_gui()

