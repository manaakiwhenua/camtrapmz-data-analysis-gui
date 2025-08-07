import pandas as pd
from .analysis import (
    summarise_camera_dates,
    identify_independent_detections,
    calculate_trap_rates,
    create_detection_histories,
    write_detection_histories
)
from .plotter import plot_trap_rates

def run_pipeline(file_path, selected_species=None, bin_days=7):
    messages = []
    try:
        raw_df = pd.read_excel(file_path, sheet_name="Sheet1", engine="openpyxl")
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
        file_path, species_list=selected_species, bin_size=bin_days
    )
    messages.append("📜 Created detection history tables.")

    # Package results
    results = {
        "summary": summary_df,
        "independent": independent_df,
        "trap_rates": trap_rates_df,
        "histories": histories_dict
    }

    return results, messages

def export_results(results, output_prefix="camera_trap"):
    try:
        with pd.ExcelWriter(f"{output_prefix}_output.xlsx") as writer:
            results["summary"].to_excel(writer, sheet_name="CameraDateSummary", index=False)
            results["independent"].to_excel(writer, sheet_name="IndependentDetections", index=False)
            results["trap_rates"].to_excel(writer, sheet_name="CameraTrapRates", index=False)
            write_detection_histories(results["histories"], writer)

        plot_trap_rates(results["trap_rates"], filename=f"{output_prefix}_trap_rates_plot.png")
        return [f"📁 Exported to: {output_prefix}_output.xlsx and {output_prefix}_rates_plot.png"]
    except Exception as e:
        return [f"❌ Export failed: {str(e)}"]
