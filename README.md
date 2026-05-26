# HVAC v3.1 — DesignBuilder-Calibrated Baseline Solver

This deployment bundle upgrades the previous HVAC v3 baseline solver into **HVAC v3.1**, a DesignBuilder-calibrated daily baseline model.

The goal is to reduce daily error before running degradation, S0-S3, severity-axis, strategy-axis, and APO analyses.

## What is new in HVAC v3.1

HVAC v3.1 adds the missing daily-pattern physics:

1. Envelope UA heat-transfer layer
2. Infiltration / ventilation sensible-load layer
3. Solar-gain proxy using glazing area and SHGC
4. Internal gains with schedule factor
5. Thermal-mass lag / smoothing
6. Heating-cooling deadband logic
7. PLR- and outdoor-temperature-dependent COP
8. Separate fan, pump, and auxiliary energy terms
9. Seasonal + residual DesignBuilder calibration layer

The model equation is now:

```text
E_HVAC,t = E_cool,t + E_heat,t + E_fan,t + E_pump,t + E_aux,t
```

with:

```text
Q_load,t = Q_env,t + Q_inf,t + Q_solar,t + Q_internal,t + Q_mass,t
```

## Why this version is needed

Your previous validation had good annual agreement but high daily error:

```text
Total error ≈ +1.30%
Daily MAPE ≈ 37.10%
Daily CVRMSE ≈ 47.02%
```

That means the old solver was balanced annually but did not reproduce the DesignBuilder daily pattern. HVAC v3.1 targets this daily load-shape mismatch.

## Files in this bundle

| File | Purpose |
|---|---|
| `hvac_v31_engine.py` | Main v3.1 baseline solver |
| `calibrate_hvac_v31_designbuilder.py` | CLI calibration and validation runner |
| `run_hvac_v31_auto.py` | Auto-run script using files in `examples/` |
| `hvac_v31_core_solver_patch.py` | Patch to import into your existing HVAC v3 code |
| `streamlit_app_v31.py` | Optional Streamlit app |
| `sample_hvac_v31_config.json` | Editable building/HVAC configuration |
| `requirements.txt` | Python requirements |
| `examples/` | Example DesignBuilder and solver input files |
| `outputs/` | Tested example outputs |

## Fast run

From inside this folder:

```bash
pip install -r requirements.txt
python run_hvac_v31_auto.py
```

On Windows, you can also run:

```text
RUN_ME_FIRST.bat
```

## Manual run

```bash
python calibrate_hvac_v31_designbuilder.py \
  --designbuilder_xlsx "examples/ALL DATA - Design builder Data.xlsx" \
  --weather_or_solver_csv "examples/baseline_no_degradation_daily.csv" \
  --output_dir outputs \
  --train_years 2020,2021,2022,2023 \
  --validate_years 2024 \
  --residual_alpha 100 \
  --max_lag_days 7
```

## Example results from the included files

| Case | Daily MAPE | Daily CVRMSE | NMBE |
|---|---:|---:|---:|
| v3.1 physics only | 75.25% | 83.08% | +1.50% |
| v3.1 component + seasonal calibration | 22.94% | 29.62% | -2.21% |
| v3.1 final calibrated | 14.67% | 19.30% | -0.04% |
| 2024 holdout final calibrated | 14.83% | 20.03% | -0.21% |

Important: the raw physics-only v3.1 still requires calibration because DesignBuilder contains detailed schedules, thermal zoning, control logic, and plant models that are not fully available from the reduced-order inputs. The final calibrated version is the deployable baseline.

## How to connect this to your existing HVAC v3 project

After running calibration, import the patch:

```python
from hvac_v31_core_solver_patch import apply_hvac_v31_patch_to_daily_results

refined_daily = apply_hvac_v31_patch_to_daily_results(
    daily_df,
    calibration_json="outputs/hvac_v31_calibration_coefficients.json"
)

# Use this as the clean baseline energy:
refined_daily["energy_kwh_v31_final"]
```

Then rebuild:

1. Clean baseline validation
2. S0 reactive degradation
3. S1 scheduled preventive maintenance
4. S2 condition-based degradation-aware maintenance
5. S3 predictive full APO
6. Two-axis Severity × Strategy matrix
7. CatBoost surrogate acceleration, if needed

## Scientific interpretation

HVAC v3.1 should be described as a **DesignBuilder-calibrated reduced-order baseline solver**. It is not a black-box replacement for physics. It combines physical HVAC load terms with a transparent calibration layer to correct residual DesignBuilder-specific daily effects.

Recommended thesis sentence:

> HVAC v3.1 was introduced to improve the daily calibration of the reduced-order baseline solver against DesignBuilder. The solver incorporates envelope heat transfer, infiltration, solar gains, internal gains, thermal-mass lag, heating/cooling deadband logic, PLR-based COP correction, and component-level fan, pump, and auxiliary energy terms. A final seasonal and residual calibration layer was then fitted using DesignBuilder outputs to reduce daily load-shape error while preserving the physical interpretability of the model.

## Outputs generated

| Output | Description |
|---|---|
| `hvac_v31_daily_outputs.csv` | Full daily comparison and corrected energy columns |
| `hvac_v31_metrics_before_after.csv` | Full-period validation metrics |
| `hvac_v31_metrics_holdout.csv` | Holdout-year validation metrics |
| `hvac_v31_calibration_coefficients.json` | Reusable calibration coefficients |
| `v31_monthly_bias.csv` | Monthly bias diagnostics |
| `v31_lag_scan.csv` | Daily shift/lag diagnostic |
| `v31_daily_energy_before_after.png` | Daily time-series validation plot |
| `v31_scatter_before_after.png` | Scatter plot |
| `v31_monthly_bias_before_after.png` | Monthly bias plot |

## Important warning

Do not use S3/APO results for final thesis defence until the clean baseline is validated. The correct workflow is:

```text
Clean baseline calibration → degradation model → S0-S3 → Severity × Strategy matrix → surrogate acceleration
```
