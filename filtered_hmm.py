from __future__ import annotations

import copy
import numpy as np
from scipy.special import logsumexp
from hmmlearn.hmm import GaussianHMM
from typing import Optional
from scipy.optimize import linear_sum_assignment


class GaussianHMMFiltered:
    """Gaussian HMM wrapper with forward-only filtered probabilities.

    This class uses hmmlearn to fit HMM parameters via EM/Baum-Welch,
    but it computes filtered probabilities manually using a forward-only
    scaled alpha pass. The returned probabilities are P(state_t | obs_1..obs_t),
    not the smoothed posterior that would use future observations.
    """

    def __init__(
        self,
        n_states: int,
        covariance_type: str = "diag",
        init_params: str = "stmc",
        params: str = "stmc",
        n_iter: int = 100,
        n_init: int = 1,
        tol: float = 1e-4,
        random_state: Optional[int] = None,
    ) -> None:
        self.n_states = n_states
        self.covariance_type = covariance_type
        self.init_params = init_params
        self.params = params
        self.n_iter = n_iter
        self.n_init = max(1, n_init)
        self.tol = tol
        self.random_state = random_state
        self.model = GaussianHMM(
            n_components=n_states,
            covariance_type=covariance_type,
            init_params=init_params,
            params=params,
            n_iter=n_iter,
            tol=tol,
            random_state=random_state,
        )

    def fit(self, obs: np.ndarray) -> "GaussianHMMFiltered":
        """Fit HMM parameters to the observed sequence.

        If n_init > 1, fit is repeated with different random restarts and the
        model with the highest log-likelihood is kept. This reduces the risk
        that the fitted model is a poor local optimum, which is especially
        important for model selection with AIC/BIC.
        """
        obs = self._validate_obs(obs)

        best_score = -np.inf
        best_model = None

        for init_index in range(self.n_init):
            if init_index == 0:
                self.model.random_state = self.random_state
            else:
                self.model.random_state = None

            self.model.fit(obs)
            score = self.model.score(obs)
            if score > best_score:
                best_score = score
                best_model = copy.deepcopy(self.model)

        if best_model is not None:
            self.model = best_model
            self._canonicalize_state_order()

        return self

    def filtered_probabilities(self, obs: np.ndarray) -> np.ndarray:
        """Return filtered state probabilities for obs.

        The output is P(state_t | obs_1..obs_t), computed with the
        forward-only alpha recursion. This is safe for real-time use and
        walk-forward backtests because it does not use any future data.
        """
        obs = self._validate_obs(obs)
        self._check_fitted()

        log_emission = self._compute_log_emission_prob(obs)
        n_samples = obs.shape[0]

        log_alpha = np.zeros((n_samples, self.n_states), dtype=np.float64)
        log_alpha[0] = np.log(self.model.startprob_ + 1e-16) + log_emission[0]
        log_alpha[0] -= logsumexp(log_alpha[0])

        for t in range(1, n_samples):
            log_pred = log_alpha[t - 1][:, np.newaxis] + np.log(self.model.transmat_ + 1e-16)
            log_alpha[t] = logsumexp(log_pred, axis=0) + log_emission[t]
            log_alpha[t] -= logsumexp(log_alpha[t])

        return np.exp(log_alpha)

    def aic(self, obs: np.ndarray) -> float:
        """Return the Akaike Information Criterion for the fitted model."""
        obs = self._validate_obs(obs)
        self._check_fitted()
        log_likelihood = self.model.score(obs)
        k = self._n_free_parameters(obs.shape[1])
        return 2 * k - 2 * log_likelihood

    def bic(self, obs: np.ndarray) -> float:
        """Return the Bayesian Information Criterion for the fitted model."""
        obs = self._validate_obs(obs)
        self._check_fitted()
        log_likelihood = self.model.score(obs)
        n_samples = obs.shape[0]
        k = self._n_free_parameters(obs.shape[1])
        return np.log(n_samples) * k - 2 * log_likelihood

    def n_parameters(self, n_features: Optional[int] = None) -> int:
        """Return the number of free parameters in the Gaussian HMM."""
        if n_features is None:
            if not hasattr(self.model, "means_"):
                raise ValueError("Model must be fitted or n_features provided")
            n_features = self.model.means_.shape[1]
        return self._n_free_parameters(n_features)

    def _n_free_parameters(self, n_features: int) -> int:
        n_states = self.n_states
        transition_params = n_states * (n_states - 1)
        start_params = n_states - 1

        if self.covariance_type == "tied":
            cov_params = n_features * (n_features + 1) // 2
            emission_params = n_states * n_features + cov_params
        elif self.covariance_type == "full":
            cov_params = n_states * n_features * (n_features + 1) // 2
            emission_params = n_states * n_features + cov_params
        elif self.covariance_type == "diag":
            emission_params = n_states * n_features + n_states * n_features
        elif self.covariance_type == "spherical":
            emission_params = n_states * n_features + n_states
        else:
            raise ValueError(f"Unsupported covariance type: {self.covariance_type}")

        return transition_params + start_params + emission_params

    def _check_fitted(self) -> None:
        if not hasattr(self.model, "means_"):
            raise ValueError("HMM must be fitted before calling this method")

    def _validate_obs(self, obs: np.ndarray) -> np.ndarray:
        obs_arr = np.asarray(obs, dtype=np.float64)
        if obs_arr.ndim == 1:
            obs_arr = obs_arr.reshape(-1, 1)
        if obs_arr.ndim != 2:
            raise ValueError("Observation array must be 1D or 2D")
        return obs_arr

    def crisis_probability(self, filtered_probs: np.ndarray, top_k: int = 1) -> np.ndarray:
        """Compute crisis probability from filtered state probabilities.

        Crisis probability is defined as the summed probability mass of the
        highest-variance states. With the canonical state ordering enforced
        after fit, these are the last `top_k` states.
        """
        if top_k < 1 or top_k > self.n_states:
            raise ValueError("top_k must be between 1 and n_states")
        filtered_probs = np.asarray(filtered_probs, dtype=np.float64)
        if filtered_probs.ndim != 2 or filtered_probs.shape[1] != self.n_states:
            raise ValueError("filtered_probs must be a 2D array with one column per state")
        self._check_fitted()
        return np.sum(filtered_probs[:, self.n_states - top_k :], axis=1)

    def _canonicalize_state_order(self) -> None:
        self._check_fitted()
        variances = self._compute_state_variances()
        variances = np.asarray(variances)

        # Normalize variances to a 1D array of length n_states.
        if variances.ndim > 1:
            # Sum across extra dimensions to produce per-state scalars
            try:
                variances = variances.reshape(self.n_states, -1).sum(axis=1)
            except Exception:
                variances = variances.ravel()

        if variances.size != self.n_states:
            # Best-effort fallback using stored covars shape
            cov = getattr(self.model, "covars_", None)
            if cov is None:
                variances = np.zeros(self.n_states, dtype=np.float64)
            else:
                cov = np.asarray(cov)
                if cov.ndim == 3 and cov.shape[0] == self.n_states:
                    variances = np.array([np.trace(cov[i]) for i in range(self.n_states)], dtype=np.float64)
                elif cov.ndim == 2 and cov.shape[0] == self.n_states:
                    variances = np.sum(cov, axis=1)
                else:
                    variances = np.full(self.n_states, float(np.sum(cov) / self.n_states), dtype=np.float64)

        means = np.asarray(self.model.means_)
        mean_scores = np.sum(means, axis=1)

        # Ensure keys are same shape and 1D
        variances = np.asarray(variances).ravel()
        mean_scores = np.asarray(mean_scores).ravel()
        if variances.size != mean_scores.size or variances.size != self.n_states:
            # As a last resort, create a stable identity ordering
            order = np.arange(self.n_states)
        else:
            order = np.lexsort((mean_scores, variances))

        # Reorder model parameters according to canonical order
        self.model.startprob_ = self.model.startprob_[order]
        self.model.transmat_ = self.model.transmat_[order][:, order]
        self.model.means_ = self.model.means_[order]

        if self.covariance_type in {"diag", "full", "spherical"}:
            try:
                self.model.covars_ = self.model.covars_[order]
            except Exception:
                # If covars are not indexable in this form, leave as-is
                pass
        elif self.covariance_type == "tied":
            # tied covariance shared across states; nothing to reorder
            pass
        else:
            raise ValueError(f"Unsupported covariance type: {self.covariance_type}")

        self.state_variances_ = variances[order]
        self.state_order_ = order

    def _compute_state_variances(self) -> np.ndarray:
        cov = getattr(self.model, "covars_", None)
        if cov is None:
            return np.zeros(self.n_states, dtype=np.float64)

        cov = np.asarray(cov)
        if self.covariance_type == "diag":
            # diag covars may come in shapes (n_states, n_features), (n_states,), or (n_features,)
            if cov.ndim == 2 and cov.shape[0] == self.n_states:
                return np.sum(cov, axis=1)
            if cov.ndim == 1 and cov.size == self.n_states:
                return cov.astype(np.float64)
            if cov.ndim == 1:
                return np.full(self.n_states, float(np.sum(cov)), dtype=np.float64)
            # fallback
            return np.full(self.n_states, float(np.sum(cov) / self.n_states), dtype=np.float64)

        if self.covariance_type == "spherical":
            # spherical may be scalar or per-state vector
            if cov.ndim == 0:
                return np.full(self.n_states, float(cov), dtype=np.float64)
            if cov.ndim == 1 and cov.size == self.n_states:
                return cov.astype(np.float64)
            return np.full(self.n_states, float(np.mean(cov)), dtype=np.float64)

        if self.covariance_type == "full":
            # cov shape expected (n_states, n_features, n_features)
            if cov.ndim == 3 and cov.shape[0] == self.n_states:
                return np.array([np.trace(cov[state]) for state in range(self.n_states)], dtype=np.float64)
            # fallback: try summing diagonals
            try:
                return np.array([np.trace(cov[state]) for state in range(self.n_states)], dtype=np.float64)
            except Exception:
                return np.full(self.n_states, float(np.sum(cov) / self.n_states), dtype=np.float64)

        if self.covariance_type == "tied":
            # single shared covariance
            if cov.ndim == 2:
                shared_variance = np.trace(cov)
            else:
                shared_variance = float(np.sum(cov))
            return np.full(self.n_states, shared_variance, dtype=np.float64)

        raise ValueError(f"Unsupported covariance type: {self.covariance_type}")




    def _compute_log_emission_prob(self, obs: np.ndarray) -> np.ndarray:
        means = self.model.means_ if hasattr(self.model, "means_") else np.zeros((self.n_states, obs.shape[1]))

        if self.covariance_type == "diag":
            covars = self.model.covars_ if hasattr(self.model, "covars_") else np.ones((self.n_states, obs.shape[1]))
            return self._gaussian_log_prob_diag(obs, means, covars)
        if self.covariance_type == "spherical":
            variances = self.model.covars_ if hasattr(self.model, "covars_") else np.ones(self.n_states)
            return self._gaussian_log_prob_spherical(obs, means, variances)
        if self.covariance_type == "full":
            covars = self.model.covars_ if hasattr(self.model, "covars_") else np.tile(np.eye(obs.shape[1]), (self.n_states, 1, 1))
            return self._gaussian_log_prob_full(obs, means, covars)
        if self.covariance_type == "tied":
            covar = self.model.covars_ if hasattr(self.model, "covars_") else np.eye(obs.shape[1])
            return self._gaussian_log_prob_full(obs, means, np.repeat(covar[np.newaxis, :, :], self.n_states, axis=0))
        raise ValueError(f"Unsupported covariance type: {self.covariance_type}")

    @staticmethod
    def _gaussian_log_prob_diag(obs: np.ndarray, means: np.ndarray, covars: np.ndarray) -> np.ndarray:
        n_samples, n_features = obs.shape
        n_states = means.shape[0]
        log_prob = np.empty((n_samples, n_states), dtype=np.float64)
        for state in range(n_states):
            var = covars[state]
            if var.ndim == 0:
                var = np.full(n_features, var)
            diff = obs - means[state]
            log_det = np.sum(np.log(2 * np.pi * var))
            quad = np.sum((diff ** 2) / var, axis=1)
            log_prob[:, state] = -0.5 * (log_det + quad)
        return log_prob

    @staticmethod
    def _gaussian_log_prob_spherical(obs: np.ndarray, means: np.ndarray, variances: np.ndarray) -> np.ndarray:
        n_samples, n_features = obs.shape
        n_states = means.shape[0]
        log_prob = np.empty((n_samples, n_states), dtype=np.float64)
        for state in range(n_states):
            var = variances[state]
            log_det = n_features * np.log(2 * np.pi * var)
            diff = obs - means[state]
            quad = np.sum((diff ** 2) / var, axis=1)
            log_prob[:, state] = -0.5 * (log_det + quad)
        return log_prob

    @staticmethod
    def _gaussian_log_prob_full(obs: np.ndarray, means: np.ndarray, covars: np.ndarray) -> np.ndarray:
        n_samples, n_features = obs.shape
        n_states = means.shape[0]
        log_prob = np.empty((n_samples, n_states), dtype=np.float64)
        for state in range(n_states):
            cov = covars[state]
            L = np.linalg.cholesky(cov)
            log_det = 2.0 * np.sum(np.log(np.diag(L)))
            diff = obs - means[state]
            y = np.linalg.solve(L, diff.T)
            quad = np.sum(y ** 2, axis=0)
            log_prob[:, state] = -0.5 * (n_features * np.log(2 * np.pi) + log_det + quad)
        return log_prob


def match_states_across_refits(
    prior: "GaussianHMMFiltered",
    new: "GaussianHMMFiltered",
    obs: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Match states from a newly-fitted HMM to a prior HMM.

    Returns a mapping matrix with shape (n_new, n_prior). Each row is a
    probability distribution over prior states for the corresponding new
    state. When observation history `obs` is supplied, it uses shared
    filtered responsibilities to preserve continuity across refits.
    """
    prior._check_fitted()
    new._check_fitted()

    prior_means = np.asarray(prior.model.means_).ravel()
    new_means = np.asarray(new.model.means_).ravel()
    prior_vars = np.asarray(prior.state_variances_) if hasattr(prior, "state_variances_") else np.asarray(prior._compute_state_variances())
    new_vars = np.asarray(new.state_variances_) if hasattr(new, "state_variances_") else np.asarray(new._compute_state_variances())

    n_prior = prior_means.size
    n_new = new_means.size

    if obs is not None:
        obs = new._validate_obs(obs)
        try:
            prior_probs = prior.filtered_probabilities(obs)
            new_probs = new.filtered_probabilities(obs)
            mapping = new_probs.T @ prior_probs
            row_sums = mapping.sum(axis=1, keepdims=True)
            if np.any(row_sums == 0.0):
                raise ValueError("Zero responsibility mass for a new state")
            return mapping / row_sums
        except Exception:
            pass

    mean_scale = max(np.max(np.abs(prior_means)), np.max(np.abs(new_means)), 1.0)
    var_scale = max(np.max(prior_vars), np.max(new_vars), 1.0)

    cost = np.empty((n_new, n_prior), dtype=np.float64)
    for i in range(n_new):
        for j in range(n_prior):
            cost[i, j] = abs(new_means[i] - prior_means[j]) / mean_scale + abs(new_vars[i] - prior_vars[j]) / var_scale

    row_ind, col_ind = linear_sum_assignment(cost)
    mapping = np.zeros((n_new, n_prior), dtype=np.float64)
    for r, c in zip(row_ind, col_ind):
        mapping[r, c] = 1.0

    if n_new > n_prior:
        for i in range(n_new):
            if not np.any(mapping[i]):
                mapping[i, np.argmin(cost[i])] = 1.0

    return mapping
