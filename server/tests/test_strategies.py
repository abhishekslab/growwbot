"""
Unit tests for strategies module.
"""

import pytest
from strategies.base import AlgoSignal, BaseAlgorithm
from strategies.momentum import MomentumScalping
from strategies.mean_reversion import MeanReversion
from strategies.registry import StrategyRegistry, get_strategy, list_strategies


class TestAlgoSignal:
    def test_algo_signal_creation(self):
        signal = AlgoSignal(
            algo_id="test_algo",
            symbol="RELIANCE",
            action="BUY",
            entry_price=2500.0,
            stop_loss=2450.0,
            target=2600.0,
            quantity=10,
            confidence=0.75,
            reason="Test signal",
            fee_breakeven=0.5,
            expected_profit=500.0,
        )
        assert signal.algo_id == "test_algo"
        assert signal.symbol == "RELIANCE"
        assert signal.action == "BUY"
        assert signal.entry_price == 2500.0

    def test_algo_signal_to_dict(self):
        signal = AlgoSignal(
            algo_id="test_algo",
            symbol="RELIANCE",
            action="BUY",
            entry_price=2500.0,
            stop_loss=2450.0,
            target=2600.0,
            quantity=10,
            confidence=0.75,
            reason="Test signal",
            fee_breakeven=0.5,
            expected_profit=500.0,
        )
        d = signal.to_dict()
        assert d["algo_id"] == "test_algo"
        assert d["symbol"] == "RELIANCE"
        assert d["quantity"] == 10


class TestMomentumScalping:
    def test_momentum_strategy_creation(self, sample_config):
        strategy = MomentumScalping(sample_config)
        assert strategy.ALGO_ID == "momentum_scalp"
        assert strategy.ALGO_NAME == "Momentum Scalping"

    def test_momentum_evaluate_insufficient_candles(self, sample_config):
        strategy = MomentumScalping(sample_config)
        result = strategy.evaluate("RELIANCE", [], 2500.0, {})
        assert result is None

    def test_momentum_evaluate_bearish_ema(self, sample_config, sample_candles):
        strategy = MomentumScalping(sample_config)
        result = strategy.evaluate("RELIANCE", sample_candles[:30], 2500.0, {})
        assert result is None

    def test_momentum_clone_with_config(self, sample_config):
        strategy = MomentumScalping(sample_config)
        clone = strategy.clone_with_config({"capital": 200000})
        assert isinstance(clone, MomentumScalping)


class TestMeanReversion:
    def test_mean_reversion_creation(self, sample_config):
        strategy = MeanReversion(sample_config)
        assert strategy.ALGO_ID == "mean_reversion"
        assert strategy.ALGO_NAME == "Mean Reversion"

    def test_mean_reversion_evaluate_insufficient_candles(self, sample_config):
        strategy = MeanReversion(sample_config)
        result = strategy.evaluate("RELIANCE", [], 2500.0, {})
        assert result is None

    def test_mean_reversion_clone_with_config(self, sample_config):
        strategy = MeanReversion(sample_config)
        clone = strategy.clone_with_config({"risk_percent": 2})
        assert isinstance(clone, MeanReversion)


class TestStrategyRegistry:
    def test_registry_initialize(self):
        StrategyRegistry.initialize()
        strategies = list_strategies()
        assert len(strategies) >= 2
        assert any(s["algo_id"] == "momentum_scalp" for s in strategies)
        assert any(s["algo_id"] == "mean_reversion" for s in strategies)

    def test_get_strategy(self, sample_config):
        strategy = get_strategy("momentum_scalp", sample_config)
        assert isinstance(strategy, MomentumScalping)

    def test_get_unknown_strategy(self, sample_config):
        strategy = get_strategy("unknown_algo", sample_config)
        assert strategy is None


class TestBaseAlgorithm:
    def test_compute_position_size(self, sample_config):
        class TestAlgo(BaseAlgorithm):
            pass

        algo = TestAlgo()
        qty = algo.compute_position_size(2500.0, 2450.0, 100000, 1)
        assert qty > 0
        assert qty <= 40  # Should be capped by capital

    def test_compute_position_size_zero_risk(self, sample_config):
        class TestAlgo(BaseAlgorithm):
            pass

        algo = TestAlgo()
        qty = algo.compute_position_size(2500.0, 2500.0, 100000, 1)
        assert qty == 0

    def test_should_skip_symbol(self):
        class TestAlgo(BaseAlgorithm):
            ALGO_ID = "test_algo"

        algo = TestAlgo()
        open_positions = [
            {"symbol": "RELIANCE", "algo_id": "test_algo"},
            {"symbol": "TCS", "algo_id": "other_algo"},
        ]
        assert algo.should_skip_symbol("RELIANCE", {}, open_positions) is True
        assert algo.should_skip_symbol("TCS", {}, open_positions) is False
        assert algo.should_skip_symbol("INFY", {}, open_positions) is False
