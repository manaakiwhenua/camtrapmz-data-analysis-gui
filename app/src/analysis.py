import pandas as pd
import math
from datetime import datetime, timedelta
import re

# ---------- Date parsing utilities ----------

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

    # try ISO-style first
    mask = out.isna()
    if mask.any():
        out.loc[mask] = pd.to_datetime(s[mask], errors="coerce", format="%Y-%m-%d %H:%M:%S")

    # then EXIF-style
    mask = out.isna()
    if mask.any():
        out.loc[mask] = pd.to_datetime(s[mask], errors="coerce", format="%Y:%m:%d %H:%M:%S")

    # final fallback: custom parser
    mask = out.isna()
    if mask.any():
        out.loc[mask] = s[mask].apply(parse_exif_date)

    df[column] = out
    df.dropna(subset=[column], inplace=True)
    return df

# ---------- Camera extraction helpers ----------

_CAM_RE_NUM = re.compile(r'(?i)(?<![0-9A-Za-z])cam(?:era)?[\s_-]*0*([0-9]+)(?=$|[^0-9A-Za-z])')

def _camera_num(name: str) -> int:
    """
    Extract an integer camera ID from strings like:
      'Cam8', 'Cam08', 'Cam 8', 'Cam_8', 'Camera12', 'Camera_12', 'Cam11 Dec21 to May22'
    Returns +inf if no number is found so those sort last.
    """
    m = _CAM_RE_NUM.search(str(name))
    return int(m.group(1)) if m else math.inf

def _dedupe_camera_and_label(df: pd.DataFrame, keep_original_label: bool = False) -> pd.DataFrame:
    """
    Ensure we don't ship both 'Camera' and a duplicate 'Label'.
    - If no 'Label', nothing to do.
    - If 'Label' present and identical to 'Camera', drop 'Label'.
    - If different and keep_original_label=True, rename to 'OriginalLabel';
      else drop it.
    """
    if "Label" not in df.columns:
        return df
    if "Camera" not in df.columns:
        return df

    cam = df["Camera"].astype(str)
    lab = df["Label"].astype(str)
    if cam.equals(lab):
        return df.drop(columns=["Label"])

    if keep_original_label:
        new_name = "OriginalLabel"
        i = 1
        while new_name in df.columns:
            new_name = f"OriginalLabel_{i}"; i += 1
        return df.rename(columns={"Label": new_name})

    return df.drop(columns=["Label"])

_CAM_FALLBACK_RE = re.compile(r"(?i)(?<![0-9A-Za-z])(cam(?:era)?[\s_-]*0*[0-9]+)(?=$|[^0-9A-Za-z])")

def _looks_like_camera_label(text: str) -> bool:
    """Heuristic: label either starts with 'cam' or contains digits (common for camera IDs)."""
    t = str(text).strip().lower()
    return bool(t) and (t.startswith("cam") or re.search(r"\d", t) is not None)

def _camera_from_filename(path: str) -> tuple[str, str]:
    """
    Return (camera, source) where source ∈ {'second-seg','regex','none'}.
    (Species-misread handled in normalize_raw; this function only extracts.)
    """
    s = str(path).strip()
    parts = [p for p in re.split(r"[\\/]+", s) if p]
    second = parts[1] if len(parts) >= 2 else ""

    if second:
        if _looks_like_camera_label(second):
            return second, "second-seg"
        m = _CAM_FALLBACK_RE.search(s)
        if m:
            return m.group(1), "regex"
        return second, "second-seg"

    m = _CAM_FALLBACK_RE.search(s)
    if m:
        return m.group(1), "regex"
    return "", "none"

def camera_extraction_report(df: pd.DataFrame) -> dict:
    """Quick stats about how 'Camera' might be inferred from 'Filename'."""
    rep = dict(
        total=len(df), has_filename=0,
        second_seg=0, regex=0, none=0,
        species_misread=0,  # NEW
        examples_none=[], examples_species=[]
    )
    if "Filename" not in df.columns:
        return rep

    rep["has_filename"] = df["Filename"].notna().sum()

    # Lowercased species set for misread detection
    species_set = set(
        pd.Series(df.get("Burst_class", []))
          .dropna().astype(str).str.strip().str.lower()
          .unique()
    )

    examples_none, examples_sp = [], []
    for _, raw in df["Filename"].dropna().items():
        cam, src = _camera_from_filename(raw)
        cam = cam.strip()
        if cam:
            if cam.lower() in species_set and src in {"second-seg", "regex"}:
                rep["species_misread"] += 1
                if len(examples_sp) < 3: examples_sp.append(str(raw))
                continue
            if src == "second-seg":
                rep["second_seg"] += 1
            elif src == "regex":
                rep["regex"] += 1
            else:
                rep["none"] += 1
                if len(examples_none) < 3: examples_none.append(str(raw))
        else:
            rep["none"] += 1
            if len(examples_none) < 3: examples_none.append(str(raw))

    rep["examples_none"] = examples_none
    rep["examples_species"] = examples_sp
    return rep

def normalize_raw(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize types and create a robust 'Camera' column.

    Preference order:
      1) existing Camera (non-empty)
      2) Label (verbatim, non-empty)
      3) Filename → camera folder (2nd path segment) or prefixed CamXX token
      4) (legacy) parse Label as path

    Adds 'Camera_source' for auditing. Rows with missing Camera or Date_taken are dropped.
    If a Filename-derived camera equals a species name, it's invalidated (source='species-misread').
    """
    df = df.copy()
    ensure_datetime_inplace(df, "Date_taken")

    # Species set for detecting species-as-camera misreads
    species_set = set(
        pd.Series(df.get("Burst_class", []))
          .dropna().astype(str).str.strip().str.lower()
          .unique()
    )

    camera = pd.Series("", index=df.index, dtype="object")
    source = pd.Series("none", index=df.index, dtype="object")

    # 1) Existing Camera
    if "Camera" in df.columns:
        cam_col = df["Camera"].astype(str).str.strip()
        pick = cam_col.ne("")
        camera = cam_col.where(pick, other=camera)
        source.loc[pick] = "existing"

    # 2) Label (only where still empty)
    if "Label" in df.columns:
        lab = df["Label"].astype(str).str.strip()
        need = (camera == "") & lab.ne("")
        camera.loc[need] = lab.loc[need]
        source.loc[need] = "label"

    # 3) Filename → second segment / regex (only where still empty)
    if "Filename" in df.columns:
        need = (camera == "") & df["Filename"].notna()
        if need.any():
            ex = df.loc[need, "Filename"].astype(str).apply(_camera_from_filename)
            cam2 = ex.map(lambda x: x[0])
            src2 = ex.map(lambda x: x[1])
            # invalidate if matches a species name
            mis = cam2.str.lower().isin(species_set) & src2.isin(["second-seg", "regex"])
            # keep valid ones
            camera.loc[need & ~mis] = cam2.loc[need & ~mis]
            source.loc[need & ~mis]  = src2.loc[need & ~mis]
            # mark misreads
            source.loc[need & mis] = "species-misread"

    # 4) Legacy: parse Label as a path for any remaining empties
    if "Label" in df.columns:
        need = (camera == "") & df["Label"].notna()
        if need.any():
            ex3 = df.loc[need, "Label"].astype(str).apply(_camera_from_filename)
            cam3 = ex3.map(lambda x: x[0])
            src3 = ex3.map(lambda x: x[1])
            mis3 = cam3.str.lower().isin(species_set) & src3.isin(["second-seg", "regex"])
            camera.loc[need & ~mis3] = cam3.loc[need & ~mis3]
            source.loc[need & ~mis3] = src3.loc[need & ~mis3]
            source.loc[need & mis3]  = "species-misread"

    df["Camera"] = camera.str.strip()
    if "Burst_class" in df.columns:
        df["Burst_class"] = df["Burst_class"].astype(str).str.strip()

    df["Camera_source"] = source
    # Require a non-empty Camera
    df = df[(df["Camera"] != "")].copy()
    return df

# ---------- Binning & queries ----------

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

# tiny debugger to verify the offending bin
def debug_bin(df: pd.DataFrame, cam: str, sp: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Inspect rows that fall into a specific [start, end) bin for a camera/species."""
    sub = normalize_raw(df)
    hit = sub[(sub["Camera"] == cam) &
              (sub["Burst_class"] == sp) &
              (sub["Date_taken"].between(start, end, inclusive="left"))]
    return hit.sort_values("Date_taken")[["Camera", "Burst_class", "Date_taken"] + ([ "Label"] if "Label" in sub.columns else [])]

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
    sub = df[(df["Camera"] == cam) & (df["Burst_class"] == sp)]
    return sub["Date_taken"].between(start, end, inclusive="left").any()

# ---------- 1) Camera date summary ----------

def summarise_camera_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise the first and last photo dates for each camera.
    Args:
        df (DataFrame): DataFrame containing detection data with columns ["Camera", "Date_taken
    Returns:
        DataFrame: DataFrame with columns ["Camera", "FirstPhoto", "LastPhoto", "NumberOfDays"]
    """
    df = normalize_raw(df)
    g = (
        df.groupby("Camera", as_index=False)["Date_taken"]
          .agg(FirstPhoto="min", LastPhoto="max")
    )
    g["FirstPhoto"] = pd.to_datetime(g["FirstPhoto"], errors="coerce")
    g["LastPhoto"]  = pd.to_datetime(g["LastPhoto"],  errors="coerce")

    # inclusive calendar days
    first_d = g["FirstPhoto"].dt.floor("D")
    last_d  = g["LastPhoto"].dt.floor("D")
    g["NumberOfDays"] = (last_d - first_d).dt.days + 1

    # natural camera ordering
    g = (
        g.assign(_camnum=g["Camera"].map(_camera_num), _orig=range(len(g)))
         .sort_values(["_camnum", "_orig"], kind="stable")
         .drop(columns=["_camnum","_orig"])
    )
    return g[["Camera", "FirstPhoto", "LastPhoto", "NumberOfDays"]]


# ---------- 2) Independent detections ----------

def identify_independent_detections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify independent detections (>=30 min apart) per (Camera, Burst_class),
    while preserving original column order and adding 'Camera' as the first column.
    Final sort: Camera (numeric-aware) -> Date_taken.
    """
    # 1) Normalize to ensure Camera + valid datetimes
    x = normalize_raw(df)

    # 2) Sort within groups to compute time gaps
    x = x.sort_values(["Camera", "Burst_class", "Date_taken"], kind="stable")

    # 3) Keep first event per (Camera, Species), then keep rows with gap >= 30 minutes
    gap = x.groupby(["Camera", "Burst_class"], sort=False)["Date_taken"].diff()
    keep = gap.isna() | (gap >= pd.Timedelta(minutes=30))
    out = x.loc[keep].copy()

    # 4) Put 'Camera' first, keep other columns in original order
    cols = out.columns.tolist()
    if "Camera" in cols:
        cols = ["Camera"] + [c for c in cols if c != "Camera"]
        out = out[cols]

    # 5) Avoid duplicate 'Label' vs 'Camera'
    out = _dedupe_camera_and_label(out, keep_original_label=True)

    # 6) Final ordering (Option A): Camera (numeric-aware) -> Date_taken
    out = (
        out.assign(_camnum=out["Camera"].map(_camera_num))
           .sort_values(["_camnum", "Camera", "Date_taken"], kind="stable")
           .drop(columns="_camnum")
           .reset_index(drop=True)
    )

    return out

# ---------- 3) Trap rates ----------

def calculate_trap_rates(summary_df: pd.DataFrame,
                         detections_df: pd.DataFrame,
                         species_col: str = "Burst_class",
                         count_col: str = "Count",
                         z: float = 1.96) -> pd.DataFrame:
    """Trap rates per 100 camera-days using Wilson CI on p = count / total_days.
    Args:
        summary_df (DataFrame): DataFrame summarizing camera dates with columns ["Camera", 
            "FirstPhoto", "LastPhoto", "NumberOfDays"]
        detections_df (DataFrame): DataFrame containing independent detections with columns
            ["Camera", species_col, "Date_taken", (optional) count_col]
        species_col (str): column name for species in detections_df
        count_col (str): column name for count of detections in detections_df; if absent,
            each row counts as 1
        z (float): z-score for confidence interval (1.96 for 95% CI)
    Returns:
        DataFrame: DataFrame with columns ["Species", "Rate_per100CamDays", "Lower95CI",
            "Upper95CI", "MinusBar", "PlusBar"]
    """
    total_days = float(pd.to_numeric(summary_df["NumberOfDays"], errors="coerce").fillna(0).sum())
    if total_days <= 0:
        raise ValueError("Total effort is zero; check NumberOfDays in summary_df.")

    det = detections_df.copy()
    if count_col not in det.columns:
        det[count_col] = 1
    det[count_col] = pd.to_numeric(det[count_col], errors="coerce").fillna(1).astype(int)

    counts = det.groupby(species_col, dropna=False, observed=True)[count_col].sum()

    rows = []
    for species, k in counts.items():
        p = k / total_days
        denom  = 1.0 + (z**2) / total_days
        center = p + (z**2) / (2.0 * total_days)
        margin = z * math.sqrt(p*(1.0 - p)/total_days + (z**2)/(4.0 * total_days**2))
        lower  = (center - margin) / denom
        upper  = (center + margin) / denom

        rate100 = p * 100.0
        lo100   = lower * 100.0
        up100   = upper * 100.0

        rows.append([
            str(species) if pd.notna(species) else "Unknown",
            round(rate100, 2),
            round(lo100, 2),
            round(up100, 2),
            round(rate100 - lo100, 2),
            round(up100 - rate100, 2),
        ])

    out = pd.DataFrame(rows, columns=[
        "Species","Rate_per100CamDays","Lower95CI","Upper95CI","MinusBar","PlusBar"
    ])
    out.sort_values(["Rate_per100CamDays","Species"], ascending=[False, True], inplace=True, ignore_index=True)
    return out

# ---------- 4) Detection histories ----------

def create_detection_histories(df: pd.DataFrame, species_list: list,
                               bin_size: int, sheet_name: str | None = None
                               ) -> dict[str, pd.DataFrame]:
    """Create detection histories for specified species with a given bin size.
    Args:
        file_path (str): path to the input Excel file
        species_list (list): list of species to include in the histories
        bin_size (int): number of days for binning detection histories
        sheet_name (str | None): worksheet name to read raw data from; defaults to "Sheet1"
    Returns:
        dict: dictionary of DataFrames with detection histories for each species
    """
    #raw0 = pd.read_excel(file_path, sheet_name=(sheet_name or "Sheet1"))
    raw = normalize_raw(df)

    # active windows
    summary = summarise_camera_dates(df).copy()
    for col in ("FirstPhoto", "LastPhoto"):
        if col in summary.columns:
            summary[col] = pd.to_datetime(summary[col], errors="coerce")
    summary = summary.dropna(subset=["FirstPhoto", "LastPhoto"]).copy()
    cam_dates = dict(zip(summary["Camera"], zip(summary["FirstPhoto"], summary["LastPhoto"])))

    # bin edges anchored at midnight
    start_date = raw["Date_taken"].min().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date   = (raw["Date_taken"].max() + timedelta(days=bin_size)).replace(hour=0, minute=0, second=0, microsecond=0)
    bins = get_bins(start_date, end_date, step=bin_size)

    # camera order = first-seen order in data (so it matches user expectations)
    cams_in_order = sorted(pd.unique(raw["Camera"]), key=_camera_num)
    species_to_use = species_list or sorted(raw["Burst_class"].dropna().unique())

    all_hist: dict[str, pd.DataFrame] = {}
    for sp in species_to_use:
        headers = ["Camera"] + [b.strftime("%Y-%m-%d") for b in bins[:-1]]
        rows = []
        for cam in cams_in_order:
            first, last = cam_dates.get(cam, (None, None))
            row = [cam]
            for i in range(len(bins) - 1):
                b0, b1 = bins[i], bins[i+1]
                if (first is None) or (b1 < first) or (b0 > last):
                    row.append("NA")
                else:
                    row.append(1 if has_detection(raw, cam, sp, b0, b1) else 0)
            rows.append(row)
        all_hist[sp] = pd.DataFrame(rows, columns=headers)
    return all_hist

def write_detection_histories(histories_dict: dict, writer) -> None:
    """Write detection histories to an Excel writer.
    Args:
        histories_dict (dict): dictionary of DataFrames with detection histories
        writer (ExcelWriter): pandas ExcelWriter object to write to
    """
    for species, df in histories_dict.items():
        df.to_excel(writer, sheet_name=species, index=False)
