import pandas as pd
from math import sqrt
from datetime import datetime, timedelta
import re

### 🔧 Utilities

def parse_exif_date(date_str) -> datetime:
    """Parse EXIF date string into a datetime object.
    Args:
        date_str (str): date string in format "YYYY:MM:DD HH:MM:SS"
    
    Returns:
        datetime: parsed datetime object or None if parsing fails
    """
    try:
        date_part, time_part = date_str.strip().split(" ")
        y, m, d = map(int, date_part.split(":"))
        h, mi, s = map(int, time_part.split(":"))
        return datetime(y, m, d, h, mi, s)
    except:
        return None

def extract_camera(label) -> str:
    """Extract camera identifier from label.
    Args:
        label (str): camera label string
    Returns:
        str: extracted camera identifier or empty string if not found
    """
    match = re.search(r"(Cam\d{2})", str(label))
    return match.group(1) if match else ""

def get_bins(start_date, end_date, step=7) -> list:
    """Generate date bins from start to end date with a specified step in days.
    Args:
        start_date (datetime): start date for bins
        end_date (datetime): end date for bins
        step (int): number of days for each bin
    Returns:
        list: list of datetime objects representing bin edges"""
    bins = []
    d = start_date
    while d <= end_date:
        bins.append(d)
        d += timedelta(days=step)
    return bins

def has_detection(df, cam, sp, start, end) -> bool:
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
    subset = df[df["Label"].str.contains(cam, na=False) & (df["Burst_class"] == sp)]
    parsed_dates = subset["Date_taken"].apply(lambda x: parse_exif_date(str(x)))
    return any((parsed_dates >= start) & (parsed_dates < end))

### 1. Summarise Camera Dates
def summarise_camera_dates(df) -> pd.DataFrame:
    """Summarise the first and last photo dates for each camera.
    Args:
        df (DataFrame): DataFrame containing camera data with columns ["Label", "Date_taken"]
    Returns:
        DataFrame: summary DataFrame with columns ["Camera", "FirstPhoto", "LastPhoto", "NumberOfDays"]
    """
    summary = {}
    # Iterate through each row to build summary

    for _, row in df.iterrows():
        label = row.get("Label")
        date_str = row.get("Date_taken")
        date_taken = parse_exif_date(str(date_str))

        if date_taken is None:
            continue

        if label not in summary:
            summary[label] = [date_taken, date_taken]
        else:
            first, last = summary[label]
            summary[label][0] = min(first, date_taken)
            summary[label][1] = max(last, date_taken)

    # Build final summary DataFrame
    summary_data = []
    for label, (first, last) in summary.items():
        days = (last - first).days + 1
        summary_data.append([label, first, last, days])

    result_df = pd.DataFrame(summary_data, columns=["Camera", "FirstPhoto", "LastPhoto", "NumberOfDays"])
    return result_df

### 2. Identify Independent Detections

def identify_independent_detections(df) -> pd.DataFrame:
    """Identify independent detections based on a 30-minute threshold.
    Args:
        df (DataFrame): DataFrame containing detection data with columns ["Label", "Burst_class", "Date_taken"]
    Returns:
        DataFrame: DataFrame with independent detections, dropping duplicates within 30 minutes
    """
    df["ParsedDate"] = df["Date_taken"].apply(lambda x: parse_exif_date(str(x)))
    df = df.dropna(subset=["ParsedDate"])
    seen, output = {}, []

    for _, row in df.iterrows():
        k = f"{row['Label']}|{row['Burst_class']}"
        dt = row["ParsedDate"]
        if k not in seen or (dt - seen[k]) >= timedelta(minutes=30):
            seen[k] = dt
            output.append(row)

    return pd.DataFrame(output)

### 3. Calculate Trap Rates with Confidence Intervals

def calculate_trap_rates(summary_df, detections_df) -> pd.DataFrame:
    """Calculate trap rates with confidence intervals.
    Args:
        summary_df (DataFrame): DataFrame with camera summary data
        detections_df (DataFrame): DataFrame with independent detections
    Returns:
        DataFrame: DataFrame with trap rates per species, including confidence intervals
    """
    total_days = summary_df["NumberOfDays"].sum()
    detections_df["Count"] = pd.to_numeric(detections_df["Count"], errors="coerce").fillna(1)
    counts = detections_df.groupby("Burst_class")["Count"].sum()

    z, results = 1.96, []
    for species, count in counts.items():
        p = count / total_days
        denom = 1 + z**2 / total_days
        center = p + z**2 / (2 * total_days)
        margin = z * sqrt(p*(1-p)/total_days + z**2 / (4*total_days**2))
        lower, upper = (center - margin) / denom, (center + margin) / denom
        rate = round(p*100, 2)
        results.append([species, rate, round(lower*100, 2), round(upper*100, 2),
                        round(rate - lower*100, 2), round(upper*100 - rate, 2)])

    return pd.DataFrame(results, columns=["Species", "Rate_per100CamDays", "Lower95CI", "Upper95CI", "MinusBar", "PlusBar"])

### 🧮 4. Create Detection Histories

def create_detection_histories(file_path: str, species_list: list, bin_size: int) -> dict:
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

    cam_dates = {extract_camera(row["Camera"]): (row["FirstPhoto"], row["LastPhoto"])
                 for _, row in summary.iterrows() if extract_camera(row["Camera"])}

    dates = raw["Date_taken"].dropna().apply(lambda x: parse_exif_date(str(x)))
    start_date, end_date = dates.min(), dates.max() + timedelta(days=bin_size)
    bins = get_bins(start_date, end_date, step=bin_size)

    all_histories = {}

    for sp in species_list:
        history = []
        headers = ["Camera"] + [b.strftime("%Y-%m-%d") for b in bins[:-1]]

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