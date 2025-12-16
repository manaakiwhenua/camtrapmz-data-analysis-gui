import pandas as pd
from app.src.analysis import (
    choose_species_column,
    normalize_raw,
    summarise_camera_dates,
    identify_independent_detections,
    calculate_trap_rates,
    create_detection_histories,
    write_detection_histories,
)
from app.src.plotter import add_trap_chart_to_sheet

_CAMERA_SOURCE_LABELS = {
    "existing": "existing 'Camera'",
    "camera-col": "existing 'Camera'",  # backward compatible
    "label": "Label",
    "second-seg": "Filename (folder)",
    "regex": "Filename (regex)",
    "species-misread": "looks like species (ignored)",
    "none": "no camera (ignored)",
}

def _camera_source_summary(norm: pd.DataFrame) -> str | None:
    if "Camera_source" not in norm.columns or norm.empty:
        return None
    src = norm["Camera_source"].value_counts(dropna=False).to_dict()
    parts = [f"{src[k]} {_CAMERA_SOURCE_LABELS[k]}" for k in _CAMERA_SOURCE_LABELS if src.get(k)]
    return ("🔎 Camera sources: " + "; ".join(parts) + f" — kept {len(norm)} rows.") if parts else None

def run_pipeline(
    file_path: str,
    selected_species=None,
    bin_days: int = 7,
    sheet_name: str | None = None,
    species_col_override: str | None = None,
) -> tuple[dict | None, list[str]]:
    """Run the camera-trap analysis pipeline on an Excel file."""
    msgs: list[str] = []

    # Load
    try:
        raw = pd.read_excel(file_path, sheet_name=(sheet_name or "Sheet1"), engine="openpyxl")
    except Exception as e:
        return None, [f"❌ Failed to load data: {e}"]

    # Decide species column
    if species_col_override:
        species_col = species_col_override
        status = "override"
        if species_col not in raw.columns:
            return None, [f"❌ Specified species column '{species_col}' not found in the selected sheet."]
    else:
        species_col, status = choose_species_column(raw)
        if species_col is None:
            return None, ["❌ Missing both 'Verified_class' and 'Burst_class' columns."]
        
    if status != "override":
        if status == "verified":
            msgs.append("ℹ️ Using Verified_class for species.")
        elif status == "fallback-empty":
            msgs.append("⚠️ Verified_class is empty — using Burst_class instead.")
        elif status == "fallback-missing":
            msgs.append("⚠️ Verified_class is missing — using Burst_class instead.")

    # Normalize once to establish Camera + clean dates
    norm = normalize_raw(raw)
    dropped = len(raw) - len(norm)

    # Brief camera-source summary
    line = _camera_source_summary(norm)
    if line:
        msgs.append(line)
    if dropped:
        msgs.append(f"⚠️ Dropped {dropped} rows lacking Camera and/or valid Date_taken.")
    if norm.empty:
        msgs.append("❌ No usable rows after cleaning (no Camera or Date_taken).")
        return None, msgs

    # Core analysis
    summary = summarise_camera_dates(norm)
    indep   = identify_independent_detections(norm, species_col=species_col)
    rates   = calculate_trap_rates(summary, indep, species_col=species_col)

    # Optional filter
    if selected_species:
        rates = rates[rates["Species"].isin(selected_species)]

    histories = create_detection_histories(norm, species_list=selected_species, bin_size=bin_days, species_col=species_col)

    return {
        "summary": summary,
        "trap_rates": rates,
        "independent": indep,
        "histories": histories,
        "species_col_used": species_col,
    }, msgs

def export_results(results, output_prefix: str = "camera_trap") -> str | None:
    """Write an Excel workbook and add the trap-rate chart."""
    out_path = f"{output_prefix}_output.xlsx"

    try:
        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
            # Camera date summary
            results["summary"].to_excel(writer, sheet_name="CameraDateSummary", index=False)

            # Trap rates (clean numerics, fixed column order)
            trap = results["trap_rates"].copy()
            cols = ["Species", "Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"]
            trap = trap[[c for c in cols if c in trap.columns]]
            for c in ("Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"):
                if c in trap.columns:
                    trap[c] = pd.to_numeric(trap[c], errors="coerce")
            trap = trap.dropna(subset=["Rate_per100CamDays", "MinusBar", "PlusBar"]).reset_index(drop=True)

            # Write + chart
            startrow = startcol = 0
            trap.to_excel(writer, sheet_name="CameraTrapRates", index=False, startrow=startrow, startcol=startcol)
            add_trap_chart_to_sheet(
                writer, trap, sheet_name="CameraTrapRates",
                table_start_row=startrow, table_start_col=startcol, place_chart_right=True
            )

            # Independent detections + detection histories
            results["independent"].to_excel(writer, sheet_name="IndependentDetections", index=False)
            write_detection_histories(results["histories"], writer)

        return out_path
    except Exception as e:
        print(f"[export_results] ERROR: {e}", flush=True)
        return None