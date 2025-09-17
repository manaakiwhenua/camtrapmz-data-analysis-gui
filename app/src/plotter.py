import pandas as pd

def add_trap_chart_to_sheet(
    writer: pd.ExcelWriter,
    df: pd.DataFrame,
    sheet_name: str = "CameraTrapRates",
    table_start_row: int = 0,
    table_start_col: int = 0,
    place_chart_right: bool = True,
) -> None:
    """
    Clustered column chart with custom error bars bound directly to:
      A Species, B Rate_per100CamDays, E MinusBar, F PlusBar

    IMPORTANT: when the table is written with header at table_start_row,
    the first DATA row in Excel is (table_start_row + 2).

    Args:
        writer: pd.ExcelWriter with xlsxwriter engine
        df: DataFrame with required columns (Species, Rate_per100CamDays, MinusBar
            PlusBar)
        sheet_name: Name of the sheet where the table is written
        table_start_row: Row index (0-based) where the table header is written
        table_start_col: Column index (0-based) where the table starts
        place_chart_right: If True, place chart to the right of the table;
            otherwise, place it below the table.
    Returns: None
    """
    required = ["Species","Rate_per100CamDays","MinusBar","PlusBar"]
    if df.empty or any(c not in df.columns for c in required):
        return

    n = len(df)
    if n == 0:
        return

    # Header at table_start_row  -> Excel row (table_start_row + 1)
    # Data begins one row below header -> Excel row (table_start_row + 2)
    first = table_start_row + 2               # <-- FIXED (was +1 before)
    last  = first + n - 1
    sheet_esc = sheet_name.replace("'", "''")

    # Absolute A1 ranges (fixed columns A,B,E,F)
    cats_rng  = f"$A${first}:$A${last}"
    vals_rng  = f"$B${first}:$B${last}"
    minus_rng = f"$E${first}:$E${last}"
    plus_rng  = f"$F${first}:$F${last}"

    wb = writer.book
    ws = writer.sheets[sheet_name]

    chart = wb.add_chart({"type": "column"})
    chart.add_series({
        "name":       "Trap Rate per 100 Camera Days",
        "categories": f"='{sheet_esc}'!{cats_rng}",
        "values":     f"='{sheet_esc}'!{vals_rng}",
        "y_error_bars": {
            "type": "custom",
            "minus_values": f"='{sheet_esc}'!{minus_rng}",
            "plus_values":  f"='{sheet_esc}'!{plus_rng}",
            "end_style": 1,
        },
    })

    chart.set_title({"name": "Camera Trap Rate per Species"})
    chart.set_x_axis({"name": "Species"})
    chart.set_y_axis({"name": "Trap Rate per 100 Camera Days", "min": 0})
    chart.set_legend({"none": True})
    chart.set_style(10)

    # Place chart
    if place_chart_right:
        ws.insert_chart(table_start_row, table_start_col + df.shape[1] + 2, chart)
    else:
        ws.insert_chart(last + 3, table_start_col, chart)