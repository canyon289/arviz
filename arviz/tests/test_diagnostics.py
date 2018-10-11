"""Test Diagnostic methods"""
import pytest
import numpy as np

from arviz import load_arviz_data
from ..stats import gelman_rubin, effective_n, geweke


class TestDiagnostics:
    good_rhat = 1.1

    @classmethod
    def setup_class(cls):
        inference_data = load_arviz_data("centered_eight")
        cls.data = inference_data.posterior  # pylint:disable=no-member

    @pytest.mark.parametrize("var_names", (None, "mu", ["mu", "tau"]))
    def test_gelman_rubin(self, var_names):
        """Confirm Gelman-Rubin statistic is close to 1 for a large number of samples.
        Also checks the correct shape"""
        rhat_data = gelman_rubin(self.data, var_names=var_names)
        for rhat in rhat_data.data_vars.values():
            assert ((1 / self.good_rhat < rhat.values) | (rhat.values < self.good_rhat)).all()

        # In None case check that all varnames from rhat_data match input data
        if var_names is None:
            assert list(rhat_data.data_vars) == list(self.data.data_vars)

    def test_gelman_rubin_bad(self):
        """Confirm Gelman-Rubin statistic is far from 1 for a small number of samples."""
        rhat = gelman_rubin(np.hstack([20 + np.random.randn(100, 1), np.random.randn(100, 1)]))
        assert 1 / self.good_rhat > rhat or self.good_rhat < rhat

    def test_effective_n_array(self):
        eff_n = effective_n(np.random.randn(4, 100))
        assert eff_n > 100
        assert eff_n < 800

    @pytest.mark.parametrize("var_names", (None, "mu", ["mu", "tau"]))
    def test_effective_n_dataset(self, var_names):
        eff_n = effective_n(self.data, var_names=var_names)
        assert eff_n.mu > 100  # This might break if the data is regenerated

    def test_geweke(self):
        first = 0.1
        last = 0.5
        intervals = 100

        gw_stat = geweke(np.random.randn(10000), first=first, last=last, intervals=intervals)

        # all geweke values should be between -1 and 1 for this many draws from a
        # normal distribution
        assert ((gw_stat[:, 1] > -1) | (gw_stat[:, 1] < 1)).all()

        assert gw_stat.shape[0] == intervals
        assert 10000 * last - gw_stat[:, 0].max() == 1
