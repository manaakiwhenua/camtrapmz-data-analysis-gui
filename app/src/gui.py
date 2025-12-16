import sys, re
from pathlib import Path
from datetime import datetime
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox,
    QScrollArea, QInputDialog, QTextBrowser, QDialog, QSizePolicy,
    QListWidget, QListWidgetItem, QStyle, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QSize
from app.src.main import run_pipeline, export_results
from app.src.analysis import _camera_from_filename

README_URL = "https://github.com/manaakiwhenua/camtrapnz-data-analysis-gui"

# ----------------- small helpers -----------------

def _second_segment(path: str) -> str | None:
    if path is None:
        return None
    parts = re.split(r"[\\/]+", str(path).strip())
    parts = [p for p in parts if p]
    return parts[1] if len(parts) >= 2 else None

def _normalize_token(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(s).strip().lower())

def detect_species_as_camera(df: pd.DataFrame, species: list[str]) -> dict:
    out = {
        "used_camera_cols": ("Camera" in df.columns) or ("Label" in df.columns),
        "n_with_filename": 0,
        "n_with_second_seg": 0,
        "n_seg_matching_species": 0,
        "ratio": 0.0,
        "sample_matches": [],
        "n_with_camera": 0,
        "n_species_seg_with_camera": 0,
    }
    if "Filename" not in df.columns or df.empty:
        return out

    species_norm = {_normalize_token(s) for s in species if isinstance(s, str) and s.strip()}
    fn = pd.Series(df["Filename"]).dropna().astype(str)
    out["n_with_filename"] = len(fn)

    segs = fn.map(_second_segment)
    out["n_with_second_seg"] = int(segs.dropna().shape[0])

    def _is_species(seg: str | None) -> bool:
        if not isinstance(seg, str):
            return False
        seg = seg.strip()
        if not seg:
            return False
        return _normalize_token(seg) in species_norm

    species_mask = segs.map(_is_species)
    out["n_seg_matching_species"] = int(species_mask.sum())
    if out["n_with_second_seg"]:
        out["ratio"] = out["n_seg_matching_species"] / out["n_with_second_seg"]
    out["sample_matches"] = segs[species_mask].dropna().astype(str).unique().tolist()[:5]

    cam_src = fn.map(_camera_from_filename)
    if len(cam_src):
        cam_df = pd.DataFrame(cam_src.tolist(), index=fn.index, columns=["camera", "source"])
        cam_vals = cam_df["camera"].astype(str).str.strip()
        valid = cam_vals.ne("")
        out["n_with_camera"] = int(valid.sum())
        species_mask = species_mask.reindex(fn.index, fill_value=False)
        out["n_species_seg_with_camera"] = int((species_mask & valid).sum())

    return out

# -------------------------------------------------

class CameraTrapApp(QWidget):
    def __init__(self):
        super().__init__()
        self.file_path: str | None = None
        self.selected_sheet: str | None = None
        self.species_checks: list[QCheckBox] = []
        self.species_col: str | None = None
        self.results_data: dict | None = None
        self._build_ui()
        self._last_log = None  # for de-dupe
        self.results_dirty: bool = False
        self.last_export_path: str | None = None

        # NEW: block running when user cancels on empty Verified_class
        self.requires_verified: bool = False
        self.species_source: str | None = None  # "verified" or "burst"

    # ---------- logging helpers ----------

    def _log(self, kind: str, text: str) -> None:
        style = QApplication.style()
        icon = {
            "file":  style.standardIcon(QStyle.SP_DirOpenIcon),
            "search":style.standardIcon(QStyle.SP_FileDialogContentsView),
            "ok":    style.standardIcon(QStyle.SP_DialogApplyButton),
            "warn":  style.standardIcon(QStyle.SP_MessageBoxWarning),
            "info":  style.standardIcon(QStyle.SP_MessageBoxInformation),
            "err":   style.standardIcon(QStyle.SP_MessageBoxCritical),
            "save":  style.standardIcon(QStyle.SP_DialogSaveButton),
        }.get(kind, style.standardIcon(QStyle.SP_FileIcon))

        if self._last_log == (kind, text):
            return
        self._last_log = (kind, text)

        it = QListWidgetItem(text)
        it.setIcon(icon)
        self.log_list.addItem(it)
        self.log_list.scrollToBottom()

    def log_file(self, t):  self._log("file", t)
    def log_search(self, t):self._log("search", t)
    def log_ok(self, t):    self._log("ok", t)
    def log_info(self, t):  self._log("info", t)
    def log_warn(self, t):  self._log("warn", t)
    def log_err(self, t):   self._log("err", t)
    def log_save(self, t):  self._log("save", t)

    def log_separator(self) -> None:
        """Visual separator between log sessions (auto-stretches with the window)."""
        item = QListWidgetItem()
        item.setFlags(Qt.NoItemFlags)  # not selectable/clickable
        item.setSizeHint(QSize(0, 12)) # controls separator height

        line = QFrame(self.log_list)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color:#cfcfcf;")  # subtle line; optional

        self.log_list.addItem(item)
        self.log_list.setItemWidget(item, line)
        self.log_list.scrollToBottom()

        self._last_log = None  # reset de-dupe boundary

    # ---------- UI ----------
    def _build_ui(self) -> None:
        self.setWindowTitle("CamTrapNZ Analyzer")
        self.setGeometry(100, 100, 700, 500)

        layout = QVBoxLayout(self)

        self.file_label = QLabel("No file selected")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.file_label)

        self.browse_btn = QPushButton("Browse Excel")
        self.help_btn = QPushButton("Help")
        header_row = QHBoxLayout()
        header_row.addWidget(self.browse_btn)
        header_row.addStretch()
        header_row.addWidget(self.help_btn)
        layout.addLayout(header_row)

        self.hint = QLabel(
            "Tip: The Analyzer only needs camera IDs or names to appear somewhere in the `Filename` column of the "
            "CamTrapNZ export (e.g., paths like Cam02/IMG_0001.JPG or filenames like Cam02_IMG_0001.JPG). "
            "As long as each camera is identifiable in `Filename`, you’re good to go."
        )
        self.hint.setWordWrap(True)
        self.hint.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.hint.setStyleSheet("color:#666; font-style:italic; font-size:11px;")
        layout.addWidget(self.hint)

        self.species_box = QVBoxLayout()
        self.species_group = QWidget()
        self.species_group.setLayout(self.species_box)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.species_group)
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(140)
        self.scroll.setMaximumHeight(240)

        self.select_all_chk = QCheckBox("Select All")
        self.select_all_chk.stateChanged.connect(self._toggle_select_all)

        species_hdr = QHBoxLayout()
        species_hdr.addWidget(QLabel("Select species:"))
        species_hdr.addStretch()
        species_hdr.addWidget(self.select_all_chk)
        layout.addLayout(species_hdr)
        layout.addWidget(self.scroll)

        layout.addWidget(QLabel("Select bin size:"))
        self.bin_input = QLineEdit()
        self.bin_input.setPlaceholderText("Bin size in days (e.g. 7)")
        layout.addWidget(self.bin_input)

        self.run_btn = QPushButton("Run Analysis")
        self.export_btn = QPushButton("Export Results")
        self.export_btn.setEnabled(False)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.export_btn)

        self.log_list = QListWidget()
        self.log_list.setUniformItemSizes(True)
        layout.addWidget(self.log_list)

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
        <p>The Analyzer only needs each camera ID or name to be visible somewhere in the <code>Filename</code> column of your CamTrapNZ export.</p>
        <ul>
        <li>Many projects organise photos in folders like <code>Cam01/IMG_0001.JPG</code>. Those folder names flow through to <code>Filename</code> (either as the second path segment or as a prefix added by CamTrapNZ) and are detected automatically.</li>
        <li>If your workflow already embeds the camera ID directly in the image name (e.g., <code>Cam02_IMG_0001.JPG</code>), that’s equally valid — the Analyzer simply scans the text for camera tokens.</li>
        </ul>
        <p>Full instructions and screenshots are available in the
        <a href="{README_URL}">README</a>.</p>
        <hr>
        <p><b>Binning:</b> weeks are left-closed, right-open [start, end);
        cameras outside their active window are marked “NA”.</p>
        """
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
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

        # Visual separator for a new session
        if self.log_list.count() > 0:
            self.log_separator()

        # NEW: reset “paused” state whenever a new file is chosen
        self.requires_verified = False
        self.species_source = None
        self.run_btn.setEnabled(True)

        self.file_path = path
        try:
            species_count, sheet = self._load_species_from_file()
            self.file_label.setText(f"📁 {Path(path).as_posix()}")
            # only log if we successfully produced a list
            if species_count > 0:
                self.log_file(f"Selected {Path(path).name} — sheet '{sheet}' — {species_count} species")
        except Exception as e:
            self.log_err(f"Failed to inspect file: {e}")
            self.file_path = None
            self.selected_sheet = None
            self.export_btn.setEnabled(False)
            self.run_btn.setEnabled(True)

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

        # optional: separator in log when picking a new file
        #self._log("info", " ")

        xls = pd.ExcelFile(self.file_path, engine="openpyxl")

        # ---------- choose sheet ----------
        sheet_to_use: str | None = None
        if "Sheet1" in xls.sheet_names:
            sheet_to_use = "Sheet1"
        elif len(xls.sheet_names) == 1:
            sheet_to_use = xls.sheet_names[0]
        else:
            for name in xls.sheet_names:
                try:
                    head = xls.parse(name, nrows=5)
                    if "Verified_class" in head.columns or ("Burst_class" in head.columns):
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

        # Both columns exist by default, but keep guardrails
        has_v = "Verified_class" in df.columns
        has_b = "Burst_class" in df.columns

        if not has_v and not has_b:
            raise ValueError(
                f"Expected 'Verified_class' or 'Burst_class' not found in sheet '{sheet_to_use}'."
            )

        if not has_v and has_b:
            # Allowed: Burst-only file
            QMessageBox.warning(
                self,
                "Verified_class not found",
                "This file has no 'Verified_class' column.\n\n"
                "The Analyzer will use 'Burst_class' (unverified). "
                "If you want verified results, export a verified file from CamTrapNZ."
            )
            self.log_warn("Verified_class column not found — using Burst_class (unverified).")
            self.species_col = "Burst_class"
            species_series = df["Burst_class"].fillna("").astype(str).str.strip()

        elif has_v:
            # Your existing Verified_class logic (non-empty => use it; empty => ask Cancel/Continue)
            v = df["Verified_class"].fillna("").astype(str).str.strip()
            if v.ne("").any():
                self.species_col = "Verified_class"
                species_series = v
                self.log_info("Using Verified_class for species list.")
            else:
                # your existing Cancel vs Continue dialog here...
                # NEW: Popup Cancel vs Continue
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle("Verified_class is empty")
                box.setText("This file has an empty 'Verified_class' column.")
                box.setInformativeText(
                    "This usually means the data has not been verified in CamTrapNZ.\n\n"
                    "Do you want to continue using 'Burst_class' (unverified), "
                    "or cancel and load a verified export?"
                )
                cont_btn = box.addButton("Continue with Burst_class (unverified)", QMessageBox.AcceptRole)
                cancel_btn = box.addButton("Cancel (load verified file)", QMessageBox.RejectRole)
                box.setDefaultButton(cancel_btn)
                box.exec_()

                if box.clickedButton() is cancel_btn:
                    self.species_col = None
                    self.requires_verified = True
                    self.log_warn("Verified_class is empty — please export a VERIFIED file from CamTrapNZ export to continue.")
                    # Pause here: disale actions and leave current file selected but unusable
                    self.run_btn.setEnabled(False)
                    self.export_btn.setEnabled(False)

                    # Clear any existing species list
                    for chk in self.species_checks:
                        self.species_box.removeWidget(chk)
                        chk.deleteLater()
                    self.species_checks = []
                    self._update_select_all()
                    return 0, sheet_to_use
                else:
                    self.species_col = "Burst_class"
                    species_series = df["Burst_class"].fillna("").astype(str).str.strip()
                    self.log_warn("Continuing with Burst_class (unverified) as species list.")
        else:
            # has_v is False, has_b is True handled above, so this branch is just safety
            self.species_col = "Burst_class"
            species_series = df["Burst_class"].fillna("").astype(str).str.strip()

        # ---------- clean species list ----------
        species_series = species_series[(species_series != "") & (~species_series.str.lower().isin({"other animal","not classified","empty"}))]
        unique_species = sorted(species_series.unique())

        # preflight: species-as-camera detection (keep your existing logic)
        try:
            diag = detect_species_as_camera(df, unique_species)
            needs_camera_col = not diag["used_camera_cols"]
            species_heavy = diag["n_with_second_seg"] > 0 and diag["ratio"] >= 0.5
            sample = ", ".join(diag["sample_matches"])

            if needs_camera_col and diag["n_with_camera"] == 0:
                if diag["n_with_filename"] > 0 and diag["n_with_second_seg"] == 0:
                    self.log_warn(
                        "No subfolders detected in ‘Filename’ (no second path segment). "
                        "Please re-export with “Retain subfolders”."
                    )
                elif species_heavy:
                    self.log_warn(
                        "The second path segment in 'Filename' looks like species names, not camera IDs. "
                        "Please re-export from CamTrapNZ with 'Retain subfolders' enabled so camera folders are preserved "
                        "(e.g., images/Cam02/IMG_0001.JPG). "
                        f"Matches: {diag['n_seg_matching_species']}/{diag['n_with_second_seg']} "
                        f"({diag['ratio']:.0%})" + (f"; examples: {sample}" if sample else "")
                    )
                else:
                    self.log_warn(
                        "Cameras could not be inferred from the data. "
                        "Please add a 'Camera' column or re-export with camera folders retained."
                    )
        except Exception:
            pass

        # rebuild species checkbox list
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

    def _log_from_emoji(self, raw: str) -> None:
        """Route a pipeline message that starts with an emoji to the right icon."""
        msg = str(raw).strip()
        kind = "info"
        # map leading markers to kinds and strip the marker
        if msg.startswith("📥"):
            kind, msg = "file", msg[1:].strip()
        elif msg.startswith("🔎"):
            kind, msg = "search", msg[1:].strip()
        elif msg.startswith("⚠️"):
            # some emoji are two code points; slice conservatively
            kind, msg = "warn", msg.lstrip("⚠️ ").strip()
        elif msg.startswith("ℹ️"):
            kind, msg = "info", msg.lstrip("ℹ️ ").strip()
        elif msg.startswith("✅"):
            kind, msg = "ok", msg[1:].strip()
        elif msg.startswith("❌"):
            kind, msg = "err", msg[1:].strip()
        elif msg.startswith("💾"):
            kind, msg = "save", msg[1:].strip()

        {
            "file":  self.log_file,
            "search":self.log_search,
            "ok":    self.log_ok,
            "warn":  self.log_warn,
            "info":  self.log_info,
            "err":   self.log_err,
            "save":  self.log_save,
        }.get(kind, self.log_info)(msg)

    def closeEvent(self, event):
        """Handle app close — confirm and offer to save if needed."""
        # Case 1: There are unsaved results
        if getattr(self, "results_dirty", False):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Unsaved Analysis Results")
            box.setText("You have analysis results that haven’t been exported.")
            box.setInformativeText("Do you want to save before closing?")
            save_btn    = box.addButton("Save && Close", QMessageBox.AcceptRole)
            discard_btn = box.addButton("Close without saving", QMessageBox.DestructiveRole)
            cancel_btn  = box.addButton("Cancel", QMessageBox.RejectRole)
            box.setDefaultButton(save_btn)
            box.exec_()

            clicked = box.clickedButton()
            if clicked is save_btn:
                self.export_results_clicked()
                if getattr(self, "results_dirty", False):  # user cancelled export
                    event.ignore()
                    return
                event.accept()
            elif clicked is discard_btn:
                event.accept()
            else:
                event.ignore()
            return

        # Case 2: Results are already saved or no analysis done yet
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Close CamTrapNZ Analyzer")
        box.setText("All results are saved. Do you want to close the app?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.Yes)
        result = box.exec_()

        if result == QMessageBox.Yes:
            self.log_info("App closed.")  # optional: log exit
            event.accept()
        else:
            event.ignore()

    # ---------- Pipeline ----------
    def run_analysis(self) -> None:
        if not self.file_path:
            self.log_warn("Please select a file first.")
            return

        # NEW: block running if user cancelled because Verified_class empty
        if getattr(self, "requires_verified", False):
            self.results_data = None
            self.export_btn.setEnabled(False)
            self.log_warn("Analysis paused: please load a verified CamTrapNZ export (Verified_class is empty).")
            return

        bin_text = self.bin_input.text().strip()
        try:
            bin_days = int(bin_text) if bin_text else 7
        except ValueError:
            bin_days = 7
            self.log_info("Invalid bin size; using default 7 days.")

        selected = [chk.text() for chk in self.species_checks if chk.isChecked()]
        sheet = getattr(self, "selected_sheet", None)

        # NOTE: this assumes your pipeline still uses Burst_class internally.
        # If you later update analysis/main to use Verified_class, pass a species_col argument instead.
        results, messages = run_pipeline(
            self.file_path,
            selected_species=selected or None,
            bin_days=bin_days,
            sheet_name=sheet,
            species_col_override=self.species_col,
        )

        if results is None:
            for msg in messages:
                self._log_from_emoji(msg)
            self.results_data = None
            self.results_dirty = False
            self.last_export_path = None
            self.export_btn.setEnabled(False)
            return

        for msg in messages:
            self._log_from_emoji(msg)

        self.results_data = results
        self.export_btn.setEnabled(True)
        self.results_dirty = True
        self.last_export_path = None

        n_cam = len(results["summary"])
        n_ind = len(results["independent"])
        n_tr  = len(results["trap_rates"])
        used = results.get("species_col_used", self.species_col or "unknown")
        self.log_ok(f"Analysis complete ({used}) — cameras: {n_cam}, detections: {n_ind} (indep), trap-rate species: {n_tr}")

    # ---------- Export ----------
    def export_results_clicked(self) -> None:
        if not self.results_data:
            self.log_warn("No analysis data available. Please run analysis first.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save Results")
        if not folder:
            self.log_warn("No folder selected. Export cancelled.")
            return

        selected = [chk.text() for chk in self.species_checks if chk.isChecked()]
        species_str = "-".join(selected) if selected else "AllSpecies"
        bin_txt = self.bin_input.text().strip() or "7"
        date_str = datetime.now().strftime("%Y-%m-%d")
        prefix = f"{folder}/camera_trap_{species_str}_bin{bin_txt}_{date_str}"

        out_path = export_results(self.results_data, output_prefix=prefix)
        if out_path is None:
            self.log_err("Export failed (see console).")
            return

        self.log_save(f"Saved: {out_path} (chart in 'CameraTrapRates')")
        self.results_dirty = False
        self.last_export_path = out_path

# ---------- entry ----------
def launch_gui():
    app = QApplication(sys.argv)
    gui = CameraTrapApp()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    launch_gui()