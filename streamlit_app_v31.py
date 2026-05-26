from __future__ import annotations

from pathlib import Path
import tempfile
import pandas as pd
import streamlit as st

from hvac_v31_engine import BuildingSpec, HVACSpec, CalibrationConfig, compute_v31_baseline, metrics_dataframe
from calibrate_hvac_v31_designbuilder import read_designbuilder_daily, align_designbuilder_and_driver, build_driver_from_merged, fit_monthly_factors, fit_ridge_residual

st.set_page_config(page_title="HVAC v3.1 DesignBuilder-Calibrated Baseline", layout="wide")
st.title("HVAC v3.1 — DesignBuilder-Calibrated Baseline Solver")
st.caption("Envelope + infiltration + solar + thermal mass + PLR + component energy + residual calibration")

with st.sidebar:
    st.header("Inputs")
    db_file = st.file_uploader("DesignBuilder daily workbook (.xlsx)", type=["xlsx"])
    driver_file = st.file_uploader("Weather or old solver daily CSV", type=["csv"])
    residual_alpha = st.number_input("Residual ridge alpha", min_value=0.0, value=100.0, step=25.0)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Building parameters")
    b = BuildingSpec()
    b.floor_area_m2 = st.number_input("Floor area (m²)", value=float(b.floor_area_m2))
    b.volume_m3 = st.number_input("Volume (m³)", value=float(b.volume_m3))
    b.h_infiltration_w_per_k = st.number_input("Infiltration H (W/K)", value=float(b.h_infiltration_w_per_k))
    b.glazing_area_m2 = st.number_input("Glazing area (m²)", value=float(b.glazing_area_m2))
    b.shgc = st.number_input("SHGC", value=float(b.shgc), min_value=0.0, max_value=1.0)
with col2:
    st.subheader("HVAC parameters")
    h = HVACSpec()
    h.cooling_capacity_kw = st.number_input("Cooling capacity (kW)", value=float(h.cooling_capacity_kw))
    h.nominal_cooling_cop = st.number_input("Nominal cooling COP", value=float(h.nominal_cooling_cop))
    h.operation_hours_per_day = st.number_input("Operation hours/day", value=float(h.operation_hours_per_day))
    h.fan_base_kw = st.number_input("Fan base kW", value=float(h.fan_base_kw))
    h.pump_base_kw = st.number_input("Pump base kW", value=float(h.pump_base_kw))

if st.button("Run HVAC v3.1 calibration", type="primary", disabled=(db_file is None or driver_file is None)):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        db_path = td / "db.xlsx"
        driver_path = td / "driver.csv"
        db_path.write_bytes(db_file.getvalue())
        driver_path.write_bytes(driver_file.getvalue())
        db = read_designbuilder_daily(db_path)
        driver = pd.read_csv(driver_path)
        merged = align_designbuilder_and_driver(db, driver)
        engine_input = build_driver_from_merged(merged)
        physics = compute_v31_baseline(engine_input, b, h, CalibrationConfig.empty())
        work = pd.concat([db.iloc[: len(physics)].reset_index(drop=True), physics.drop(columns=["date"], errors="ignore")], axis=1)
        work["date"] = db.iloc[: len(work)]["date"].values
        work["year"] = pd.to_datetime(work["date"]).dt.year
        work["month"] = pd.to_datetime(work["date"]).dt.month
        years = sorted(work["year"].dropna().unique().tolist())
        train_years = years[:-1] if len(years) > 1 else years
        train = work[work["year"].isin(train_years)].copy()
        monthly_factors = fit_monthly_factors(train, "db_total_kwh", "energy_kwh_v31_physics")
        seasonal_cal = CalibrationConfig(monthly_factors=monthly_factors, residual_coefficients={}, feature_names=tuple())
        seasonal = compute_v31_baseline(engine_input, b, h, seasonal_cal)
        work2 = pd.concat([db.iloc[: len(seasonal)].reset_index(drop=True), seasonal.drop(columns=["date"], errors="ignore")], axis=1)
        work2["date"] = db.iloc[: len(work2)]["date"].values
        work2["year"] = pd.to_datetime(work2["date"]).dt.year
        work2["month"] = pd.to_datetime(work2["date"]).dt.month
        train2 = work2[work2["year"].isin(train_years)].copy()
        train2["residual_target"] = train2["db_total_kwh"] - train2["energy_kwh_v31_seasonal"]
        intercept, coefs, feature_names = fit_ridge_residual(train2, "residual_target", alpha=residual_alpha)
        final_cal = CalibrationConfig(monthly_factors=monthly_factors, residual_coefficients=coefs, feature_names=tuple(feature_names), residual_intercept=intercept)
        final = compute_v31_baseline(engine_input, b, h, final_cal)
        out = pd.concat([db.iloc[: len(final)].reset_index(drop=True), final.drop(columns=["date"], errors="ignore")], axis=1)
        out["date"] = db.iloc[: len(out)]["date"].values
        metrics = metrics_dataframe({
            "v31_physics": (out["db_total_kwh"], out["energy_kwh_v31_physics"]),
            "v31_seasonal": (out["db_total_kwh"], out["energy_kwh_v31_seasonal"]),
            "v31_final": (out["db_total_kwh"], out["energy_kwh_v31_final"]),
        })
        st.subheader("Validation metrics")
        st.dataframe(metrics, use_container_width=True)
        st.subheader("Daily energy")
        chart = out[["date", "db_total_kwh", "energy_kwh_v31_physics", "energy_kwh_v31_final"]].set_index("date")
        st.line_chart(chart)
        st.download_button("Download daily outputs CSV", out.to_csv(index=False).encode(), "hvac_v31_daily_outputs.csv", "text/csv")
