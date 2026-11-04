"""Person-clustered INTERNAL reference for the incident-stroke LOCO arm.

The decay that the transportability claim rests on needs a reference. Row-level cross-validation
is not one: these panels put 2-8 intervals on each adult, so a row-level split puts the same
person's neighbouring intervals in both the training fold and the held-out fold, and every decay
computed against it is optimistic. This script refits the identical pipelines under
StratifiedGroupKFold on cohort|pid, per country and pooled, and writes

  data/processed/intl/incident/incident_internal_clustered.csv

with the internal AUROC under both splits side by side, plus the mean held-out LOCO AUROC taken
from the primary run so the decay column is computed from files rather than from memory.

Nothing here changes the primary arm: the LOCO fits already respect the country boundary, and no
person crosses countries, so only the reference is affected.

Usage
  python run_incident_internal.py [--features common|extended] [--time linear|none] [--loco FILE]
"""
import os, sys, glob, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
import run_incident_loco as I
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import roc_auc_score, brier_score_loss

OUT = I.OUT
SEED = V2.SEED


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def oof(X, y, groups, name, n_splits=5, cluster=True):
    """Out-of-fold probabilities. cluster=False splits rows (the optimistic reference we keep
    only to show how much the clustering matters)."""
    p = np.full(len(y), np.nan)
    from sklearn.model_selection import StratifiedKFold
    if cluster:
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=SEED)
        folds = splitter.split(X, y, groups)
    else:
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=SEED)
        folds = splitter.split(X, y)
    for tr, te in folds:
        fr = I.Frozen(X.iloc[tr], y[tr], name)
        p[te] = fr.predict(X.iloc[te])
    return p


def main():
    fset, time_mode = flag("--features", "common"), flag("--time", "linear")
    # The un-suffixed `incident_loco_common_linear_H4.csv` was the pre-audit THREE-panel table; the
    # four-panel run writes `_uw` (unweighted, primary) and `_w` (design-weighted). Joining the old
    # name silently measured a four-panel internal CV against a three-panel external mean, which is
    # what made this row's decay column wrong. The stale files now live in incident/superseded/.
    loco_name = flag("--loco", "incident_loco_common_linear_H4_uw.csv")
    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    grp = (pp["cohort"].astype(str) + "|" + pp["pid"].astype(str)).values
    print(f"internal reference | rows={len(pp)} persons={pd.Series(grp).nunique()} "
          f"features={fset} time={time_mode}", flush=True)

    loco = pd.read_csv(os.path.join(OUT, loco_name))
    lv = flag("--level", "interval")
    held_tbl = loco[loco.level == lv]
    mean_loco = held_tbl.groupby("model")["auroc"].mean()

    rows = []
    for name in I.BASE:
        pc = oof(X, y, grp, name, cluster=True)
        rc = oof(X, y, grp, name, cluster=False)
        q = float(y.mean())
        row = dict(model=name, feature_set=fset, time=time_mode, level=lv,
                   n=len(y), events=int(y.sum()), obs_prev=q,
                   brier_naive_oracle=q * (1 - q),
                   auroc_clustered=float(roc_auc_score(y, pc)),
                   brier_clustered=float(brier_score_loss(y, pc)),
                   auroc_rowlevel=float(roc_auc_score(y, rc)),
                   brier_rowlevel=float(brier_score_loss(y, rc)),
                   mean_loco=float(mean_loco.get(name, np.nan)),
                   rows_per_person=len(pp) / pd.Series(grp).nunique())
        row["decay_clustered"] = row["auroc_clustered"] - row["mean_loco"]
        row["decay_rowlevel"] = row["auroc_rowlevel"] - row["mean_loco"]
        for c, sub in held_tbl[held_tbl.model == name].groupby("held"):
            row[f"auroc_held_{c}"] = float(sub.auroc.iloc[0])
        rows.append(row)
        print(f"  {name:22s} clustered {row['auroc_clustered']:.4f}  row-level "
              f"{row['auroc_rowlevel']:.4f}  mean LOCO {row['mean_loco']:.4f}  "
              f"decay(clustered) {row['decay_clustered']:+.4f}", flush=True)
    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_internal_{fset}_{time_mode}_{lv}.csv")
    out.to_csv(dest, index=False)
    print("wrote", dest)


if __name__ == "__main__":
    main()
