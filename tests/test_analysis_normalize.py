# tests/test_analysis_normalize.py
import pandas as pd
from app.src.analysis import normalize_raw

def test_normalize_prefers_camera_over_label():
    df = pd.DataFrame({
        "Label": ["CamX", ""],
        "Camera": ["CamOld", "Cam02"],
        "Filename": ["images/Cam99/a.jpg", "images/Cam02/b.jpg"],
        "Burst_class": ["Cat", "Dog"],
        "Date_taken": ["2021-01-01 10:00:00", "2021-01-01 11:00:00"],
    })

    out = normalize_raw(df)

    # existing Camera should win over Label where both are non-empty
    assert list(out["Camera"]) == ["CamOld", "Cam02"]
    assert list(out["Camera_source"]) == ["existing", "existing"]

def test_normalize_drops_rows_without_camera_or_date():
    df = pd.DataFrame({
        "Filename": ["IMG_0001.JPG", None],
        "Burst_class": ["Cat", "Dog"],
        "Date_taken": ["", None],
    })
    out = normalize_raw(df)
    assert out.empty
