from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from filtered_hmm import GaussianHMMFiltered


@dataclass
class RegimeModelFit:
    n_states: int
    log_likelihood: float
    n_parameters: int
    aic: float
    bic: float
    model: GaussianHMMFiltered
    degenerate: bool = False


@dataclass
class RegimeComparisonResult:
    candidates: list[RegimeModelFit]
    aic_winner: RegimeModelFit
    bic_winner: RegimeModelFit


def compare_regime_counts(
    obs,
    state_counts: Iterable[int] = (2, 3),
    n_init: int = 1,
    random_state: Optional[int] = None,
    n_iter: int = 100,
    covariance_type: str = "diag",
    degenerate_variance_rel_tol: float = 0.05,
) -> RegimeComparisonResult:
    """Fit candidate Gaussian HMMs and compare their AIC/BIC.

    BIC penalizes complexity more heavily than AIC as the sample size grows.
    For a regime-detection service that values stability over overly flexible
    state definitions, BIC is often the more conservative choice. The function
    does not force a single winner; it returns both the AIC-optimal and the
    BIC-optimal candidate so the caller can choose the appropriate tradeoff.
    """
    obs_arr = np.asarray(obs, dtype=np.float64)
    if obs_arr.ndim == 1:
        obs_arr = obs_arr.reshape(-1, 1)
    candidates: list[RegimeModelFit] = []

    for n_states in state_counts:
        model = GaussianHMMFiltered(
            n_states=n_states,
            covariance_type=covariance_type,
            n_iter=n_iter,
            n_init=n_init,
            random_state=random_state,
        )
        model.fit(obs_arr)
        log_likelihood = model.model.score(obs_arr)
        aic = model.aic(obs_arr)
        bic = model.bic(obs_arr)
        # Degenerate-state guard: disqualify candidate only when two or more
        # components are effectively the same distribution. We require both
        # nearly-identical variances and near-zero mean separation to avoid
        # rejecting valid multi-state fits with equal-variance but distinct
        # means.
        degenerate = False
        try:
            vars_ = np.asarray(model.state_variances_)
            means = np.asarray(model.model.means_)
            if means.ndim == 1:
                means = means.reshape(-1, 1)
            if vars_.size >= 2:
                for i in range(vars_.size):
                    for j in range(i + 1, vars_.size):
                        rel_var = abs(vars_[i] - vars_[j]) / max(vars_[i], vars_[j], 1e-12)
                        if rel_var < float(degenerate_variance_rel_tol):
                            max_var = max(vars_[i], vars_[j], 1e-12)
                            diff = means[i] - means[j]
                            mean_separation = np.sqrt(np.sum((diff ** 2) / max_var))
                            if mean_separation < 0.5:
                                degenerate = True
                                break
                    if degenerate:
                        break
        except Exception:
            degenerate = False

        # If degenerate and this is a higher-state candidate, bump its
        # information criteria so it won't be selected over simpler models.
        if degenerate and n_states > min(state_counts):
            aic = float("inf")
            bic = float("inf")
        candidates.append(
                RegimeModelFit(
                n_states=n_states,
                log_likelihood=log_likelihood,
                n_parameters=model.n_parameters(),
                aic=aic,
                bic=bic,
                model=model,
                degenerate=degenerate,
            )
        )

    aic_winner = min(candidates, key=lambda candidate: candidate.aic)
    bic_winner = min(candidates, key=lambda candidate: candidate.bic)
    return RegimeComparisonResult(
        candidates=candidates,
        aic_winner=aic_winner,
        bic_winner=bic_winner,
    )
