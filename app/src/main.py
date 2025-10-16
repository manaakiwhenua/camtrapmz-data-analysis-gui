import pandas as pd
from app.src.analysis import (
    normalize_raw,
    summarise_camera_dates,
    identify_independent_detections,
    calculate_trap_rates,
    create_detection_histories,
    write_detection_histories,
)
from app.src.plotter import add_trap_chart_to_sheet


def run_pipeline(
    file_path: str,
    selected_species=None,
    bin_days: int = 7,
    sheet_name: str | None = None,
) -> tuple[dict | None, list[str]]:
    """Run the camera-trap analysis pipeline on an Excel file."""
    msgs: list[str] = []

    # Load
    try:
        raw = pd.read_excel(file_path, sheet_name=(sheet_name or "Sheet1"), engine="openpyxl")
        msgs.append("📥 Loaded data.")
    except Exception as e:
        return None, [f"❌ Failed to load data: {e}"]

    # Normalize once to establish Camera + clean dates
    norm = normalize_raw(raw)
    dropped = len(raw) - len(norm)

    # Brief camera-source summary
    src = norm["Camera_source"].value_counts(dropna=False).to_dict()
    parts = []
    for key, label in {
        "existing": "existing 'Camera'",
        "camera-col": "existing 'Camera'",
        "label": "Label",
        "second-seg": "Filename (folder)",
        "regex": "Filename (regex)",
        "species-misread": "looks like species (ignored)",
        "none": "no camera (ignored)",
    }.items():
        n = src.get(key, 0)
        if n:
            parts.append(f"{n} {label}")
    if parts:
        msgs.append("🔎 Camera sources: " + "; ".join(parts) + f" — kept {len(norm)} rows.")
    if dropped:
        msgs.append(f"⚠️ Dropped {dropped} rows lacking Camera and/or valid Date_taken.")
    if len(norm) == 0:
        msgs.append("❌ No usable rows after cleaning (no Camera or Date_taken).")
        return None, msgs

    # Core analysis
    summary = summarise_camera_dates(raw)
    indep   = identify_independent_detections(raw)
    rates   = calculate_trap_rates(summary, indep)

    # Optional filter
    if selected_species:
        rates = rates[rates["Species"].isin(selected_species)]

    histories = create_detection_histories(raw, species_list=selected_species, bin_size=bin_days, sheet_name=sheet_name)

    results = {
        "summary": summary,
        "trap_rates": rates,
        "independent": indep,
        "histories": histories,
    }
    return results, msgs

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