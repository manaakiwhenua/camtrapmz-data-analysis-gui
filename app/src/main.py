import pandas as pd
from app.src.analysis import (
    camera_extraction_report,
    normalize_raw,
    summarise_camera_dates,
    identify_independent_detections,
    calculate_trap_rates,
    create_detection_histories,
    write_detection_histories,
)
from app.src.plotter import add_trap_chart_to_sheet


def run_pipeline(file_path: str, selected_species=None, bin_days=7, sheet_name: str | None = None) -> tuple:
    """
    Run the full camera trap analysis pipeline on the provided Excel file.

    Returns:
        (results: dict, messages: list[str])

    results contains:
      - summary       (DataFrame)
      - trap_rates    (DataFrame)
      - independent   (DataFrame)
      - histories     (dict[str, DataFrame])
    """
    messages: list[str] = []
    try:
        raw_df = pd.read_excel(file_path, sheet_name=(sheet_name or "Sheet1"), engine="openpyxl")
        messages.append("📥 Data loaded successfully.")
    except Exception as e:
        return None, [f"❌ Failed to load data: {e}"]

    # ▶ Determine what actually provided Camera names (from normalize_raw)
    norm = normalize_raw(raw_df)
    dropped = len(raw_df) - len(norm)

    src_counts = norm["Camera_source"].value_counts(dropna=False).to_dict()
    n_label     = src_counts.get("label", 0)
    n_camcol    = src_counts.get("camera-col", 0)
    n_second    = src_counts.get("second-seg", 0)
    n_regex     = src_counts.get("regex", 0)
    n_none      = src_counts.get("none", 0)
    total_kept  = len(norm)

    parts = []
    if n_label:
        parts.append(f"{n_label} from 'Label'")
    if n_camcol:
        parts.append(f"{n_camcol} from existing 'Camera'")
    if n_second or n_regex:
        if n_second and n_regex:
            parts.append(f"{n_second} from Filename folder, {n_regex} via regex (e.g. cam12)")
        elif n_second:
            parts.append(f"{n_second} from Filename folder")
        else:
            parts.append(f"{n_regex} from Filename via regex (e.g. cam12)")
    if n_none:
        parts.append(f"{n_none} with no camera")

    if parts:
        messages.append("🔎 Camera source breakdown: " + "; ".join(parts) + f" (total {total_kept}).")
    else:
        messages.append("⚠️ Could not infer any camera names — data may be empty after normalization.")

    if dropped > 0:
        messages.append(f"⚠️ Dropped {dropped} rows lacking a Camera or a valid Date_taken.")

    # Optional: only run the Filename health-check if we actually used Filename for some rows
    if n_second or n_regex:
        rep = camera_extraction_report(raw_df)
        if rep["has_filename"] == 0:
            messages.append("⚠️ No 'Filename' column found.")
        else:
            if rep["none"] > 0:
                examples = "; ".join(rep["examples_none"]) if rep["examples_none"] else ""
                messages.append(
                    f"ℹ️ Filename parse check: {rep['second_seg']} clean, {rep['regex']} regex fallback, "
                    f"{rep['none']} not parseable out of {rep['has_filename']}."
                    + (f" Examples without camera: {examples}" if examples else "")
                )

    # Core pipeline (these functions normalize internally as needed)
    summary_df = summarise_camera_dates(raw_df)
    messages.append("📊 Summarized camera dates.")

    independent_df = identify_independent_detections(raw_df)
    messages.append("🔍 Identified independent detections.")

    trap_rates_df = calculate_trap_rates(summary_df, independent_df)
    messages.append("📈 Calculated trap rates.")

    # Optional species filter
    if selected_species:
        trap_rates_df = trap_rates_df[trap_rates_df["Species"].isin(selected_species)]

    histories_dict = create_detection_histories(
        raw_df, species_list=selected_species, bin_size=bin_days, sheet_name=sheet_name
    )
    messages.append("📜 Created detection history tables.")

    results = {
        "summary": summary_df,
        "trap_rates": trap_rates_df,
        "independent": independent_df,
        "histories": histories_dict,
    }
    return results, messages


def export_results(results, output_prefix: str = "camera_trap") -> str | None:
    """
    Write results to an Excel workbook and embed a chart on the CameraTrapRates sheet.

    Returns:
        str path (on success) or None (on failure)
    """
    out_path = f"{output_prefix}_output.xlsx"

    try:
        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
            # CameraDateSummary
            results["summary"].to_excel(writer, sheet_name="CameraDateSummary", index=False)

            # Trap rates in fixed column order expected by plotter
            trap = results["trap_rates"].copy()
            cols = ["Species", "Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"]
            trap = trap[[c for c in cols if c in trap.columns]]

            # Coerce numerics
            for c in ("Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"):
                if c in trap.columns:
                    trap[c] = pd.to_numeric(trap[c], errors="coerce")

            # Drop rows that would break the chart
            trap_clean = trap.dropna(subset=["Rate_per100CamDays", "MinusBar", "PlusBar"]).reset_index(drop=True)

            # Write and chart
            startrow, startcol = 0, 0
            trap_clean.to_excel(writer, sheet_name="CameraTrapRates", index=False,
                                startrow=startrow, startcol=startcol)

            add_trap_chart_to_sheet(
                writer, trap_clean, sheet_name="CameraTrapRates",
                table_start_row=startrow, table_start_col=startcol, place_chart_right=True
            )

            # Independent detections + per-species histories
            results["independent"].to_excel(writer, sheet_name="IndependentDetections", index=False)
            write_detection_histories(results["histories"], writer)

        return out_path

    except Exception as e:
        print(f"[export_results] ERROR: {e}", flush=True)
        return None