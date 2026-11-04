#!/usr/bin/env bash
# Full incident-arm re-run on the corrected cumulative-incidence estimand, four countries.
# One log per step so a failure is attributable instead of buried in a single stream.
set -u
cd "$(dirname "$0")" || exit 1        # the script lives in analysis/, which is where the
                                       # scripts/intl/... paths below are relative to
LOG=output/pipeline
mkdir -p "$LOG"
PY=python

run () {                       # run <name> <command...>
  name=$1; shift
  echo "=== [$name] $* $(date +%H:%M:%S)"
  if "$@" > "$LOG/$name.log" 2>&1; then
    echo "--- [$name] OK $(date +%H:%M:%S)"; tail -2 "$LOG/$name.log"
  else
    echo "--- [$name] FAILED; see $LOG/$name.log"; tail -25 "$LOG/$name.log"
  fi
}

# primary: both estimands in one table, so the convention is a column and not a footnote
run loco_primary      $PY scripts/intl/run_incident_loco.py --boot 2000 --horizon 4
run internal          $PY scripts/intl/run_incident_internal.py
run adapt_cif         $PY scripts/intl/incident_adaptation.py --horizon-rule cif_mid --reps 10
run adapt_legacy      $PY scripts/intl/incident_adaptation.py --horizon-rule exclusive_start --reps 10
run recal_cif         $PY scripts/intl/incident_horizon_recalibration.py --horizon-rule cif_mid --reps 20
run recal_legacy      $PY scripts/intl/incident_horizon_recalibration.py --horizon-rule exclusive_start --reps 20
run competing         $PY scripts/intl/incident_competing_risks.py --models logistic,elasticnet,xgboost --rules cif_mid,exclusive_start --fractions 0.02,0.05,0.10,0.25,0.50 --reps 20
# P1: the middle of the model-update spectrum, so "recalibration beats retraining" is not a
# comparison against a straw man (pooled updating, penalised revision toward the frozen
# coefficients at four lambdas, time-terms-only update, de novo refit)
run update_strategies $PY scripts/intl/incident_update_strategies.py --models logistic,elasticnet,spline_logistic --fractions 0.02,0.05,0.10,0.25,0.50 --reps 20
# sensitivity arms: cif_mid only, the estimand choice is carried by the primary table
run loco_time_none    $PY scripts/intl/run_incident_loco.py --boot 1000 --horizon 4 --time none --horizon-rules cif_mid
run loco_extended     $PY scripts/intl/run_incident_loco.py --boot 1000 --horizon 4 --features extended --horizon-rules cif_mid
run loco_weights      $PY scripts/intl/run_incident_loco.py --boot 1000 --horizon 4 --weights --horizon-rules cif_mid
run loco_H6           $PY scripts/intl/run_incident_loco.py --boot 1000 --horizon 6 --horizon-rules cif_mid
run shap              $PY scripts/intl/incident_shap.py --rows 4000
echo "=== pipeline finished $(date +%H:%M:%S)"
