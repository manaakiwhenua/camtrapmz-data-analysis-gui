# tests/test_gui_helpers.py
import pandas as pd
from app.src.gui import detect_species_as_camera

def test_detect_species_as_camera_flags_when_second_seg_matches_species():
    df = pd.DataFrame({
        "Filename": [
            "images/Cat/IMG_001.JPG",
            "images/Cat/IMG_002.JPG",
            "images/Dog/IMG_003.JPG",
        ],
        "Burst_class": ["Cat", "Cat", "Dog"],
    })
    species = ["Cat", "Dog"]
    diag = detect_species_as_camera(df, species)

    assert diag["n_with_second_seg"] == 3
    assert diag["n_seg_matching_species"] >= 1
    assert diag["ratio"] > 0
    assert "Cat" in diag["sample_matches"]
