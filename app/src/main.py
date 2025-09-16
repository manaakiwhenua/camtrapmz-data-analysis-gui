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

def export_results(results, output_prefix="camera_trap") -> list:
    """Export analysis results to Excel and generate plots.
    Args:
        results (dict): dictionary containing analysis results
        output_prefix (str): prefix for output files
    Returns:
        messages (list): list of status messages from the export process"""
    try:
        # IMPORTANT: use xlsxwriter so we can add charts BEFORE closing
        with pd.ExcelWriter(f"{output_prefix}_output.xlsx", engine="xlsxwriter") as writer:
            results["summary"].to_excel(writer, sheet_name="CameraDateSummary", index=False)
            results["trap_rates"].to_excel(writer, sheet_name="CameraTrapRates", index=False)
            results["independent"].to_excel(writer, sheet_name="IndependentDetections", index=False)
            write_detection_histories(results["histories"], writer)

            # add chart in the same writer session
            add_trap_chart_to_sheet(writer, results["trap_rates"], sheet_name="CameraTrapRates",
                                    table_start_row=0, table_start_col=0, place_chart_right=True)

        return [f"📁 Exported to: {output_prefix}_output.xlsx"]
    except Exception as e:
        return [f"❌ Export failed: {str(e)}"]
