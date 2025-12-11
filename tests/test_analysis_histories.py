# tests/test_analysis_histories.py
from datetime import datetime
import pandas as pd
from app.src.analysis import create_detection_histories

def test_detection_histories_basic(simple_df):
    hist = create_detection_histories(simple_df, species_list=["Cat"], bin_size=7, sheet_name=None)
    cat_df = hist["Cat"]

    assert "Camera" in cat_df.columns
    # first row is Cam01 → should have at least one “1”
    cam1_row = cat_df[cat_df["Camera"] == "Cam01"].iloc[0]
    assert any(v == 1 for v in cam1_row[1:])
