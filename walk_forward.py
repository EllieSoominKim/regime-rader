from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from filtered_hmm import GaussianHMMFiltered
from model_selection import compare_regime_counts
from filtered_hmm import match_states_across_refits


@dataclass
class WalkForwardResult:
    index: pd.DatetimeIndex
    probabilities: pd.DataFrame


class WalkForwardRegimeEngine:
    """Run a realistic expanding-window regime detection workflow.

    Parameters
    ----------
    n_states:
        Number of HMM states to fit and track when no candidate counts are provided.
    candidate_state_counts:
        Optional candidate regime counts for model selection at each refit.
    selection_criterion:
        Model selection criterion to use when candidate_state_counts is provided.
        One of 'aic' or 'bic'.
    refit_frequency:
        Pandas frequency string for refit cadence, e.g. 'W' or 'M'.
    min_train_window:
        Minimum number of observations required before the first fit.
    n_init:
        Number of random restarts for HMM fitting.
    """

    def __init__(
        self,
        n_states: int,
        candidate_state_counts: Optional[Iterable[int]] = None,
        selection_criterion: str = "bic",
        refit_frequency: str = "W",
        min_train_window: int = 60,
        n_init: int = 1,
        random_state: Optional[int] = None,
        n_iter: int = 100,
        covariance_type: str = "diag",
        crisis_top_k: int = 1,
    ) -> None:
        self.n_states = n_states
        self.candidate_state_counts = tuple(candidate_state_counts) if candidate_state_counts is not None else None
        if selection_criterion not in {"aic", "bic"}:
            raise ValueError("selection_criterion must be either 'aic' or 'bic'")
        self.selection_criterion = selection_criterion
        self.refit_frequency = refit_frequency
        self.min_train_window = min_train_window
        self.n_init = n_init
        self.random_state = random_state
        self.n_iter = n_iter
        self.covariance_type = covariance_type
        self.crisis_top_k = crisis_top_k

    def run(self, obs: pd.Series) -> pd.DataFrame:
        if not isinstance(obs.index, pd.DatetimeIndex):
            raise ValueError("obs must be indexed by a pandas DatetimeIndex")

        if len(obs) < self.min_train_window + 1:
            raise ValueError("obs must contain more rows than min_train_window")

        obs = obs.sort_index()
        dates = obs.index
        results = []
        refit_dates = self._compute_refit_dates(dates)
        self.refit_models_ = {}
        self.refit_comparisons_ = {}
        self.max_state_columns_ = self.n_states if self.candidate_state_counts is None else max(self.candidate_state_counts)

        model: Optional[GaussianHMMFiltered] = None
        selected_n_states: Optional[int] = None

        for current_idx, current_date in enumerate(dates):
            if current_idx < self.min_train_window:
                # tuple: date, state_probs, argmax_state, crisis_prob, refit_flag, selected_n_states
                results.append((current_date, None, None, None, False, None))
                continue

            if current_date in refit_dates or model is None:
                train_slice = obs.iloc[:current_idx]
                if self.candidate_state_counts is not None:
                    comparison = compare_regime_counts(
                        train_slice.values,
                        state_counts=self.candidate_state_counts,
                        n_init=self.n_init,
                        random_state=self.random_state,
                        n_iter=self.n_iter,
                        covariance_type=self.covariance_type,
                    )
                    self.refit_comparisons_[current_date] = comparison
                    selected_model = (
                        comparison.aic_winner if self.selection_criterion == "aic" else comparison.bic_winner
                    )
                    model = selected_model.model
                    selected_n_states = selected_model.n_states
                else:
                    model = GaussianHMMFiltered(
                        n_states=self.n_states,
                        covariance_type=self.covariance_type,
                        n_iter=self.n_iter,
                        n_init=self.n_init,
                        random_state=self.random_state,
                    )
                    model.fit(train_slice.values)
                    selected_n_states = self.n_states
                self.refit_models_[current_date] = model
                # If there was a prior refit, compute mapping from new->prior
                if len(self.refit_models_) > 1:
                    prior_dates = sorted(d for d in self.refit_models_.keys() if d < current_date)
                    if prior_dates:
                        last_prior = prior_dates[-1]
                        prior_model = self.refit_models_[last_prior]
                        try:
                            mapping = match_states_across_refits(prior_model, model, obs=train_slice.values)
                            setattr(model, "_prior_mapping", mapping)
                            setattr(model, "_prior_n_states", int(prior_model.n_states))
                        except Exception:
                            pass
                refit_flag = True
            else:
                refit_flag = False
                if selected_n_states is None:
                    selected_n_states = self.n_states

            filtered_probs = model.filtered_probabilities(obs.iloc[: current_idx + 1].values)
            state_probs = filtered_probs[-1]
            # If the model contains a prior mapping, align probs to the prior's
            # indexing so `crisis_probability` remains continuous across refits.
            if hasattr(model, "_prior_mapping") and hasattr(model, "_prior_n_states"):
                prior_n = int(model._prior_n_states)
                mapping = np.asarray(model._prior_mapping, dtype=float)
                aligned = filtered_probs @ mapping
                crisis_prob = float(np.sum(aligned[:, prior_n - self.crisis_top_k :], axis=1)[-1])
            else:
                crisis_prob = float(model.crisis_probability(filtered_probs, top_k=self.crisis_top_k)[-1])
            argmax_state = int(np.argmax(state_probs))
            results.append((current_date, state_probs, argmax_state, crisis_prob, refit_flag, selected_n_states))

        rows = []
        for date, state_probs, argmax_state, crisis_prob, refit_flag, selected_n_states in results:
            if state_probs is None:
                row = {f"state_{i}": np.nan for i in range(self.max_state_columns_)}
                row["regime"] = np.nan
                row["crisis_probability"] = np.nan
                row["refit"] = False
                row["selected_n_states"] = np.nan
            else:
                row = {
                    f"state_{i}": float(state_probs[i]) if i < len(state_probs) else np.nan
                    for i in range(self.max_state_columns_)
                }
                row["regime"] = argmax_state
                row["crisis_probability"] = crisis_prob
                row["refit"] = refit_flag
                row["selected_n_states"] = int(selected_n_states)
            rows.append(row)

        return pd.DataFrame(rows, index=dates)

    def _compute_refit_dates(self, dates: pd.DatetimeIndex) -> set[pd.Timestamp]:
        anchor = dates[0]
        target_dates = pd.date_range(start=anchor, end=dates[-1], freq=self.refit_frequency)
        aligned = []
        for target in target_dates:
            candidates = dates[dates >= target]
            if len(candidates) > 0:
                aligned.append(candidates[0])
        return set(aligned)
