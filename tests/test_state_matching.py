from filtered_hmm import GaussianHMMFiltered, match_states_across_refits
import numpy as np


def make_dummy_filtered(means, variances, covariance_type="diag"):
    n = len(means)
    f = GaussianHMMFiltered(n_states=n, covariance_type=covariance_type, n_init=1)
    # create minimal model-like object
    class M:
        pass

    m = M()
    m.means_ = np.array(means).reshape(n, 1)
    if covariance_type == "diag":
        m.covars_ = np.array(variances).reshape(n, 1)
    else:
        m.covars_ = np.array(variances)
    f.model = m
    f.state_variances_ = np.array(variances)
    return f


def test_match_split_case():
    # prior has 2 states, new has 3 (split)
    prior = make_dummy_filtered(means=[-1.0, 1.0], variances=[0.1, 0.5])
    new = make_dummy_filtered(means=[-1.05, -0.95, 1.02], variances=[0.11, 0.09, 0.48])
    mapping = match_states_across_refits(prior, new)
    assert mapping.shape == (3, 2)
    assert np.allclose(mapping.sum(axis=1), 1.0)
    assert mapping[0, 0] > mapping[0, 1]
    assert mapping[2, 1] > mapping[2, 0]
    assert mapping[1, 0] > mapping[1, 1]


def test_match_merge_case():
    # prior has 3 states, new has 2 (merge)
    prior = make_dummy_filtered(means=[-2.0, 0.0, 2.0], variances=[0.1, 0.2, 0.15])
    new = make_dummy_filtered(means=[-1.95, 1.98], variances=[0.12, 0.14])
    mapping = match_states_across_refits(prior, new)
    assert mapping.shape == (2, 3)
    assert np.allclose(mapping.sum(axis=1), 1.0)
    assert np.max(mapping, axis=1).min() > 0.5