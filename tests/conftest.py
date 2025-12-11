import pytest
import pandas as pd
from datetime import datetime

@pytest.fixture
def simple_df():
    """Minimal CamTrapNZ-like export with good filenames & dates."""
    return pd.DataFrame({
        "Filename": [
            "images/Cam01/IMG_0001.JPG",
            "images/Cam01/IMG_0002.JPG",
            "images/Cam02/IMG_0003.JPG",
        ],
        "Burst_class": ["Cat", "Cat", "Dog"],
        "Date_taken": [
            "2021-01-01 00:00:00",
            "2021-01-01 00:10:00",
            "2021-01-02 05:00:00",
        ],
    })

@pytest.fixture
def df_with_label_and_camera():
    return pd.DataFrame({
        "Label": ["Cam10", "Cam11 Dec21 to May22"],
        "Camera": ["Cam10", "Cam11 Dec21 to May22"],
        "Burst_class": ["Cat", "Dog"],
        "Date_taken": ["2021-01-01 10:00:00", "2021-01-02 12:00:00"],
    })