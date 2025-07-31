import pytest
from datetime import datetime
from camera_utils import parse_exif_date

def test_valid_exif_date():
    date_str = "2023:08:12 15:20:00"
    result = parse_exif_date(date_str)
    assert result == datetime(2023, 8, 12, 15, 20, 0)

def test_invalid_exif_date_format():
    date_str = "2023/08/12 15:20:00"
    assert parse_exif_date(date_str) is None

def test_empty_string():
    assert parse_exif_date("") is None