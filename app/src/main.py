import pandas as pd
from .analysis import (
    summarise_camera_dates,
    identify_independent_detections,
    calculate_trap_rates,
    create_detection_histories,
    write_detection_histories
)
from .plotter import add_trap_chart_to_sheet

def run_pipeline(file_path: str, selected_species=None, bin_days=7, sheet_name: str | None = None) -> tuple:
    """Run the full analysis pipeline on the provided data file.
    Args:
        file_path (str): path to the input Excel file
        selected_species (list): list of species to filter results, if None all species are included
        bin_days (int): number of days for binning detection histories
        sheet_name (str | None): worksheet name to read raw data from; defaults to "Sheet1"
    Returns:
        results (dict): dictionary containing DataFrames of analysis results
        messages (list): list of status messages from the pipeline
    """
    messages = []
    try:
        raw_df = pd.read_excel(file_path, sheet_name=(sheet_name or "Sheet1"), engine="openpyxl")
        messages.append("📥 Data loaded successfully.")
    except Exception as e:
        return None, [f"❌ Failed to load data: {str(e)}"]

    summary_df = summarise_camera_dates(raw_df)
    messages.append("📊 Summarized camera dates.")

    independent_df = identify_independent_detections(raw_df)
    messages.append("🔍 Identified independent detections.")

    trap_rates_df = calculate_trap_rates(summary_df, independent_df)
    messages.append("📈 Calculated trap rates.")

    # ✅ Filter trap rates to selected species
    if selected_species:
        trap_rates_df = trap_rates_df[trap_rates_df["Species"].isin(selected_species)]

    histories_dict = create_detection_histories(
        file_path, species_list=selected_species, bin_size=bin_days, sheet_name=sheet_name
    )
    messages.append("📜 Created detection history tables.")

    # Package results
    results = {
        "summary": summary_df,
        "trap_rates": trap_rates_df,
        "independent": independent_df,
        "histories": histories_dict
    }

    return results, messages

def export_results(results, output_prefix: str = "camera_trap") -> list:
    """
    Write results to an Excel workbook and embed a chart on the CameraTrapRates sheet.
    - Uses xlsxwriter (charts must be added before closing the writer).
    - Cleans trap-rate rows to guarantee numeric columns and equal-length ranges.
    """
    try:
        out_path = f"{output_prefix}_output.xlsx"

        with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
            # 1) Always write the other sheets
            results["summary"].to_excel(writer, sheet_name="CameraDateSummary", index=False)

            # 2) Prepare trap rates in fixed column order (A..F expected by the plotter)
            trap = results["trap_rates"].copy()
            cols = ["Species", "Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"]
            trap = trap[[c for c in cols if c in trap.columns]]

            # Coerce numerics
            for c in ("Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"):
                if c in trap.columns:
                    trap[c] = pd.to_numeric(trap[c], errors="coerce")

            # CRITICAL: Drop rows that would break the chart (non-numeric)
            trap_clean = trap.dropna(
                subset=["Rate_per100CamDays", "MinusBar", "PlusBar"]
            ).reset_index(drop=True)

            # 3) Write the cleaned table and add the chart
            # Write table at (row=0, col=0): header is row 1 in Excel, data starts at row 2
            startrow = 0
            startcol = 0
            trap_clean.to_excel(writer, sheet_name="CameraTrapRates", index=False,
                                startrow=startrow, startcol=startcol)

            # Chart from the same table
            add_trap_chart_to_sheet(
                writer, trap_clean, sheet_name="CameraTrapRates",
                table_start_row=startrow, table_start_col=startcol, place_chart_right=True
            )

            # 4) write independent detections and histories
            results["independent"].to_excel(writer, sheet_name="IndependentDetections", index=False)
            write_detection_histories(results["histories"], writer)

        return [f"📁 Exported to: {out_path}"]
    except Exception as e:
        return [f"❌ Export failed: {str(e)}"]
