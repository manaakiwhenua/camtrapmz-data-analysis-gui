# tests/test_analysis_traprates.py
import pandas as pd
from app.src.analysis import calculate_trap_rates

def test_trap_rates_basic():
    summary = pd.DataFrame({
        "Camera": ["Cam1", "Cam2"],
        "FirstPhoto": ["2021-01-01", "2021-01-01"],
        "LastPhoto": ["2021-01-10", "2021-01-10"],
        "NumberOfDays": [10, 10],  # 20 cam-days
    })
    detections = pd.DataFrame({
        "Camera": ["Cam1", "Cam2"],
        "Burst_class": ["Cat", "Cat"],
        "Date_taken": ["2021-01-02", "2021-01-03"],
    })

    out = calculate_trap_rates(summary, detections)
    row = out[out["Species"] == "Cat"].iloc[0]
    assert row["Rate_per100CamDays"] > 0
    assert row["Lower95CI"] <= row["Rate_per100CamDays"] <= row["Upper95CI"]

def test_trap_rates_zero_effort_raises():
    summary = pd.DataFrame({
        "Camera": ["Cam1"],
        "FirstPhoto": ["2021-01-01"],
        "LastPhoto": ["2021-01-01"],
        "NumberOfDays": [0],
    })
    detections = pd.DataFrame(columns=["Camera","Burst_class","Date_taken"])
    import pytest
    with pytest.raises(ValueError):
        calculate_trap_rates(summary, detections)
