from __future__ import annotations

from collections.abc import Iterable, Mapping

import pandas as pd


class AnalysisEngine:
    """Foundation for analysis of experimental run data."""

    def build_run_dataframe(self, runs: Iterable[Mapping[str, object]]) -> pd.DataFrame:
        data = list(runs)
        if not data:
            return pd.DataFrame(columns=[])
        return pd.DataFrame(data)

    def summarize_quality(self, runs: Iterable[Mapping[str, object]]) -> dict[str, float]:
        df = self.build_run_dataframe(runs)
        if df.empty or "quality" not in df.columns:
            return {"average_quality": 0.0}
        return {"average_quality": float(df["quality"].mean())}

    def plot_quality_against_power(self, runs: Iterable[Mapping[str, object]]) -> dict[str, list[float] | str]:
        df = self.build_run_dataframe(runs)
        if df.empty or "power_w" not in df.columns or "quality" not in df.columns:
            return {"x": [], "y": [], "title": "Power vs Quality"}
        ordered = df[["power_w", "quality"]].dropna().sort_values("power_w")
        return {
            "x": [float(value) for value in ordered["power_w"].tolist()],
            "y": [float(value) for value in ordered["quality"].tolist()],
            "title": "Power vs Quality",
        }

    def plot_quality_against_speed(self, runs: Iterable[Mapping[str, object]]) -> dict[str, list[float] | str]:
        df = self.build_run_dataframe(runs)
        if df.empty or "speed_mm_s" not in df.columns or "quality" not in df.columns:
            return {"x": [], "y": [], "title": "Speed vs Quality"}
        ordered = df[["speed_mm_s", "quality"]].dropna().sort_values("speed_mm_s")
        return {
            "x": [float(value) for value in ordered["speed_mm_s"].tolist()],
            "y": [float(value) for value in ordered["quality"].tolist()],
            "title": "Speed vs Quality",
        }
