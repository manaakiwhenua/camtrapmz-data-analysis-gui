# tests/test_main_pipeline.py
from app.src.main import run_pipeline
import pandas as pd

def test_run_pipeline_happy_path(tmp_path, simple_df, monkeypatch):
    # write a temporary Excel file
    p = tmp_path / "test.xlsx"
    simple_df.to_excel(p, index=False)

    results, msgs = run_pipeline(str(p))
    assert results is not None
    assert "summary" in results
    assert "trap_rates" in results
    assert any("Loaded data" in m or "Loaded" in m for m in msgs)
