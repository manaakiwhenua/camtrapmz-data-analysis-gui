# tests/test_analysis_independent.py
import pandas as pd
from app.src.analysis import identify_independent_detections

def test_independent_detections_30_min_rule():
    df = pd.DataFrame({
        "Filename": [
            "images/Cam01/a.jpg", "images/Cam01/b.jpg", "images/Cam01/c.jpg"
        ],
        "Burst_class": ["Cat", "Cat", "Cat"],
        "Date_taken": [
            "2021-01-01 00:00:00",
            "2021-01-01 00:10:00",  # within 30m -> drop
            "2021-01-01 00:40:00",  # >=30m -> keep
        ],
    })
    out = identify_independent_detections(df)
    cam = list(out["Camera"])
    assert cam == ["Cam01", "Cam01"]
    assert len(out) == 2
