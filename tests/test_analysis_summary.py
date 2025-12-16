# tests/test_analysis_summary.py
from datetime import datetime
import pandas as pd
from app.src.analysis import summarise_camera_dates

EXCLUDED_SPECIES = {s.lower() for s in ("Other animal", "Not classified", "Empty")}

def test_excluded_species_case_insensitive():
    s = pd.Series(["Empty", "empty", "EMPTY", "Cat"])
    out = s[~s.str.lower().isin(EXCLUDED_SPECIES)]
    assert list(out) == ["Cat"]

def test_summarise_camera_dates(simple_df):
    out = summarise_camera_dates(simple_df)

    assert set(out.columns) == {"Camera", "FirstPhoto", "LastPhoto", "NumberOfDays"}
    cam01 = out[out["Camera"] == "Cam01"].iloc[0]
    assert cam01["FirstPhoto"].date() == datetime(2021, 1, 1).date()
    assert cam01["LastPhoto"].date() == datetime(2021, 1, 1).date()
    assert cam01["NumberOfDays"] == 1

def test_camera_sorting_numeric_ids():
    df = pd.DataFrame({
        "Camera": ["Cam2", "Cam10", "Cam1"],
        "Burst_class": ["Cat", "Cat", "Cat"],
        "Date_taken": [
            "2021-01-01 00:00:00",
            "2021-01-01 00:01:00",
            "2021-01-01 00:02:00",
        ],
    })
    out = summarise_camera_dates(df)
    assert list(out["Camera"]) == ["Cam1", "Cam2", "Cam10"]
