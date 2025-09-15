import pandas as pd
from math import sqrt
from datetime import datetime, timedelta
import re

### 🔧 Utilities

def parse_exif_date(date_str) -> datetime | None:
    """EXIF 'YYYY:MM:DD HH:MM:SS' → datetime, else None."""
    try:
        date_part, time_part = str(date_str).strip().split(" ")
        y, m, d = map(int, date_part.split(":"))
        h, mi, s = map(int, time_part.split(":"))
        return datetime(y, m, d, h, mi, s)
    except Exception:
        return None

def ensure_datetime_inplace(df: pd.DataFrame, column: str = "Date_taken") -> pd.DataFrame:
    """
    Make df[column] a proper datetime:
    - keep datetimes
    - try pandas to_datetime
    - fallback to EXIF parser
    Drops rows where parsing fails.
    """
    s = df[column]
    # keep datetimes
    out = s.where(s.apply(lambda x: isinstance(x, datetime)))
    
    # try pandas parser
    mask = out.isna()
    if mask.any():
        # try ISO-style first
        out.loc[mask] = pd.to_datetime(s[mask], errors="coerce", format="%Y-%m-%d %H:%M:%S")

    mask = out.isna()
    if mask.any():
        # try EXIF-style
        out.loc[mask] = pd.to_datetime(s[mask], errors="coerce", format="%Y:%m:%d %H:%M:%S")

    mask = out.isna()
    if mask.any():
        # final fallback: custom EXIF parser
        out.loc[mask] = s[mask].apply(parse_exif_date)

    df[column] = out
    df.dropna(subset=[column], inplace=True)
    return df

def get_bins(start_date: datetime, end_date: datetime, step: int = 7) -> list[datetime]:
    """Generate date bins from start to end date with a specified step in days.
    Args:
        start_date (datetime): start date for bins
        end_date (datetime): end date for bins
        step (int): number of days for each bin
    Returns:
        list: list of datetime objects representing bin edges"""
    bins, d = [], start_date
    while d <= end_date:
        bins.append(d)
        d += timedelta(days=step)
    return bins

def extract_camera(label) -> str:
    m = re.search(r"(Cam\d{2})", str(label))
    return m.group(1) if m else ""

def has_detection(df: pd.DataFrame, cam: str, sp: str, start: datetime, end: datetime) -> bool:
    """Check if there are detections for a specific camera and species within a date range.
    Args:
        df (DataFrame): DataFrame containing detection data
        cam (str): camera identifier
        sp (str): species name
        start (datetime): start of the date range
        end (datetime): end of the date range
    Returns:
        bool: True if there are detections, False otherwise
    """
    sub = df[df["Label"].str.contains(cam, na=False) & (df["Burst_class"] == sp)]
    # assumes df["Date_taken"] already datetime
    return any((sub["Date_taken"] >= start) & (sub["Date_taken"] < end))

### 1. Summarise Camera Dates
def summarise_camera_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise the first and last photo dates for each camera.
    Args:
        df (DataFrame): DataFrame containing camera data with columns ["Label", "Date_taken"]
    Returns:
        DataFrame: summary DataFrame with columns ["Camera", "FirstPhoto", "LastPhoto", "NumberOfDays"]
    """
    df = df.copy()
    ensure_datetime_inplace(df, "Date_taken")

    # Aggregate first/last per camera
    g = (
        df.groupby("Label", as_index=False)["Date_taken"]
          .agg(FirstPhoto="min", LastPhoto="max")
          .rename(columns={"Label": "Camera"})
    )

    # Ensure true pandas datetime64[ns] dtypes on aggregated columns
    g["FirstPhoto"] = pd.to_datetime(g["FirstPhoto"], errors="coerce")
    g["LastPhoto"]  = pd.to_datetime(g["LastPhoto"],  errors="coerce")

    # Compute inclusive calendar days (ignore time-of-day)
    first_d = g["FirstPhoto"].dt.floor("D")
    last_d  = g["LastPhoto"].dt.floor("D")
    g["NumberOfDays"] = (last_d - first_d).dt.days + 1

    return g[["Camera", "FirstPhoto", "LastPhoto", "NumberOfDays"]]

### 2. Identify Independent Detections
def identify_independent_detections(df: pd.DataFrame) -> pd.DataFrame:
    """Identify independent detections based on a 30-minute threshold.
    Args:
        df (DataFrame): DataFrame containing detection data with columns ["Label", "Burst_class", "Date_taken"]
    Returns:
        DataFrame: DataFrame with independent detections, dropping duplicates within 30 minutes
    """
    df = df.copy()
    ensure_datetime_inplace(df, "Date_taken")
    #df.sort_values("Date_taken", inplace=True)

    seen, out_rows = {}, []
    for _, row in df.iterrows():
        k = f"{row['Label']}|{row['Burst_class']}"
        dt = row["Date_taken"]
        if k not in seen or (dt - seen[k]) >= timedelta(minutes=30):
            seen[k] = dt
            out_rows.append(row)
    return pd.DataFrame(out_rows)

### 3. Calculate Trap Rates with Confidence Intervals
def calculate_trap_rates(summary_df: pd.DataFrame,
                         detections_df: pd.DataFrame,
                         species_col: str = "Burst_class",
                         count_col: str = "Count",
                         z: float = 1.96) -> pd.DataFrame:
    """
    Trap rates per 100 camera-days using Wilson (binomial) CI on p = count / total_days.

    Notes:
    - Ensure summary_df['NumberOfDays'] are *inclusive* calendar days.
    - detections_df should be *independent detections* (after the 30-min rule).
    - Each row counts as 1 unless a Count column is provided.
    """
    # Effort (camera-days) as float
    total_days = float(pd.to_numeric(summary_df["NumberOfDays"], errors="coerce").fillna(0).sum())
    if total_days <= 0:
        raise ValueError("Total effort is zero; check NumberOfDays in summary_df.")

    # Counts per species
    det = detections_df.copy()
    if count_col not in det.columns:
        det[count_col] = 1
    det[count_col] = pd.to_numeric(det[count_col], errors="coerce").fillna(1).astype(int)

    counts = det.groupby(species_col, dropna=False)[count_col].sum()

    # Wilson CI on p = k / total_days (then scale ×100)
    rows = []
    for species, k in counts.items():
        p = k / total_days
        denom  = 1.0 + (z**2) / total_days
        center = p + (z**2) / (2.0 * total_days)
        margin = z * sqrt(p*(1.0 - p)/total_days + (z**2)/(4.0 * total_days**2))
        lower  = (center - margin) / denom
        upper  = (center + margin) / denom

        rate100 = round(p * 100.0, 2)
        lo100   = round(lower * 100.0, 2)
        up100   = round(upper * 100.0, 2)

        rows.append([
            str(species) if pd.notna(species) else "Unknown",
            rate100, lo100, up100,
            round(rate100 - lo100, 2),
            round(up100 - rate100, 2)
        ])

    out = pd.DataFrame(rows, columns=["Species", "Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"])
    return out.sort_values("Rate_per100CamDays", ascending=False, ignore_index=True)

### 🧮 4. Create Detection Histories
def create_detection_histories(file_path: str, species_list: list, bin_size: int) -> dict[str, pd.DataFrame]:
    """Create detection histories for specified species with a given bin size.
    Args:
        file_path (str): path to the input Excel file
        species_list (list): list of species to include in the histories
        bin_size (int): number of days for binning detection histories
    Returns:
        dict: dictionary of DataFrames with detection histories for each species
    """
    raw = pd.read_excel(file_path, sheet_name="Sheet1")
    summary = pd.read_excel(file_path, sheet_name="CameraDateSummary")

    # Ensure datetime types
    ensure_datetime_inplace(raw, "Date_taken")
    for col in ("FirstPhoto", "LastPhoto"):
        if col in summary.columns:
            summary[col] = pd.to_datetime(summary[col], errors="coerce")
    summary.dropna(subset=["FirstPhoto", "LastPhoto"], inplace=True)

    cam_dates = {
        extract_camera(row["Camera"]): (row["FirstPhoto"], row["LastPhoto"])
        for _, row in summary.iterrows() if extract_camera(row["Camera"])
    }

    start_date = raw["Date_taken"].min()
    end_date = raw["Date_taken"].max() + timedelta(days=bin_size)
    bins = get_bins(start_date, end_date, step=bin_size)

    all_histories: dict[str, pd.DataFrame] = {}
    for sp in species_list:
        history, headers = [], ["Camera"] + [b.strftime("%Y-%m-%d") for b in bins[:-1]]
        for r in range(1, 33):
            cam = f"Cam{r:02}"
            active = cam_dates.get(cam, (None, None))
            row = [cam]
            for i in range(len(bins) - 1):
                bin_start, bin_end = bins[i], bins[i+1]
                if not active[0] or bin_end < active[0] or bin_start > active[1]:
                    row.append("-")
                elif has_detection(raw, cam, sp, bin_start, bin_end):
                    row.append(1)
                else:
                    row.append(0)
            history.append(row)
        all_histories[sp] = pd.DataFrame(history, columns=headers)
    return all_histories

def write_detection_histories(histories_dict: dict, writer) -> None:
    """Write detection histories to an Excel writer.
    Args:
        histories_dict (dict): dictionary of DataFrames with detection histories
        writer (ExcelWriter): pandas ExcelWriter object to write to
    """
    for species, df in histories_dict.items():
        df.to_excel(writer, sheet_name=species, index=False)
