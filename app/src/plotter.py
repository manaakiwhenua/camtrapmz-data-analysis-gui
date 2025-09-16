import matplotlib.pyplot as plt
import pandas as pd

def add_trap_chart_to_sheet(writer, df, sheet_name="CameraTrapRates",
                            table_start_row=0, table_start_col=0, place_chart_right=True):
    """Add a bar chart with error bars to an Excel sheet using xlsxwriter.
    Args:
        writer (pd.ExcelWriter): an open ExcelWriter with xlsxwriter engine
        df (pd.DataFrame): DataFrame containing trap rate data
        sheet_name (str): name of the sheet to add the chart to
        table_start_row (int): starting row of the data table in the sheet
        table_start_col (int): starting column of the data table in the sheet
        place_chart_right (bool): if True, place chart to the right of the table; else below
    """
    # expects columns: Species, Rate_per100CamDays, Lower95CI, Upper95CI, MinusBar, PlusBar
    required = ["Species","Rate_per100CamDays","Lower95CI","Upper95CI","MinusBar","PlusBar"]
    missing = [c for c in required if c not in df.columns]
    if missing or df.empty:
        return  # nothing to chart or wrong columns

    wb = writer.book
    ws = writer.sheets[sheet_name]

    n = len(df)
    r0 = table_start_row + 1                 # first data row (below header)
    r1 = r0 + n - 1                          # last data row
    c_species, c_rate, c_minus, c_plus = table_start_col+0, table_start_col+1, table_start_col+4, table_start_col+5

    chart = wb.add_chart({"type": "column"})
    chart.add_series({
        "name":       "Rate per 100 Camera-Days",
        "categories": [sheet_name, r0, c_species, r1, c_species],
        "values":     [sheet_name, r0, c_rate,    r1, c_rate],
        "y_error_bars": {
            "type": "custom",
            "plus_values":  [sheet_name, r0, c_plus,  r1, c_plus],
            # Show only positive (upper) error bars
            "direction": "plus",
        },
    })
    chart.set_title({"name": "Camera Trap Rate Per Species"})
    chart.set_x_axis({"name": "Species"})
    chart.set_y_axis({"name": "Trap Rate per 100 Camera Days"})
    chart.set_legend({"position": "bottom"})
    chart.set_style(10)

    if place_chart_right:
        ws.insert_chart(table_start_row, table_start_col + len(df.columns) + 2, chart)
    else:
        ws.insert_chart(r1 + 3, table_start_col, chart)

