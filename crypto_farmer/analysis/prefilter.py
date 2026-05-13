from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd
from pydantic import BaseModel

from crypto_farmer.signals.models import IndicatorSnapshot, SignalAction


class PrefilterConfig(BaseModel):
    rsi_oversold: float
    rsi_overbought: float
    volume_anomaly_factor: float
    atr_expansion_factor: float
    cooldown_minutes: int


@dataclass
class PrefilterDecision:
    passes: bool
    triggers: list[str] = field(default_factory=list)
    reason: str | None = None


def _direction_from_rsi(rsi: float, cfg: PrefilterConfig) -> SignalAction:
    if rsi <= cfg.rsi_oversold:
        return SignalAction.BUY
    if rsi >= cfg.rsi_overbought:
        return SignalAction.SELL
    return SignalAction.HOLD


class Prefilter:
    def __init__(self, cfg: PrefilterConfig) -> None:
        self._cfg = cfg

    def evaluate(
        self,
        snap: IndicatorSnapshot,
        *,
        recent_history: pd.DataFrame,
        last_signal_for_pair: tuple[SignalAction, datetime] | None,
    ) -> PrefilterDecision:
        triggers = self._collect_triggers(snap, recent_history)
        if not triggers:
            return PrefilterDecision(passes=False, reason="no_triggers")

        if last_signal_for_pair is not None:
            last_action, last_time = last_signal_for_pair
            elapsed = datetime.now(timezone.utc) - last_time
            if elapsed < timedelta(minutes=self._cfg.cooldown_minutes):
                # Cooldown only applies after a directional (BUY/SELL) signal.
                # A previous HOLD imposes no cooldown.
                if last_action != SignalAction.HOLD:
                    proposed = _direction_from_rsi(snap.rsi, self._cfg)
                    opposite = {
                        SignalAction.BUY: SignalAction.SELL,
                        SignalAction.SELL: SignalAction.BUY,
                    }
                    if proposed != opposite[last_action]:
                        return PrefilterDecision(passes=False, reason="cooldown", triggers=triggers)

        return PrefilterDecision(passes=True, triggers=triggers)

    def _collect_triggers(
        self, snap: IndicatorSnapshot, history: pd.DataFrame
    ) -> list[str]:
        triggers: list[str] = []
        if snap.rsi <= self._cfg.rsi_oversold or snap.rsi >= self._cfg.rsi_overbought:
            triggers.append("rsi_extreme")
        # ratios return None when their denominator is zero (data quality issue).
        # Treat None as "no trigger" — never crash on missing data.
        vol_ratio = snap.volume_anomaly_ratio()
        if vol_ratio is not None and vol_ratio >= self._cfg.volume_anomaly_factor:
            triggers.append("volume_anomaly")
        atr_ratio = snap.atr_expansion_ratio()
        if atr_ratio is not None and atr_ratio >= self._cfg.atr_expansion_factor:
            triggers.append("atr_expansion")
        if self._ema_cross_recent(history):
            triggers.append("ema_cross")
        if self._range_breakout(snap, history):
            triggers.append("range_breakout")
        return triggers

    def _ema_cross_recent(self, history: pd.DataFrame) -> bool:
        if history.empty or {"ema_20", "ema_50"} - set(history.columns):
            return False
        last3 = history.tail(3)
        signs = (last3["ema_20"] - last3["ema_50"]).apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0).tolist()
        return len(set(signs)) > 1  # hubo cambio de signo en las últimas 3 velas

    def _range_breakout(self, snap: IndicatorSnapshot, history: pd.DataFrame) -> bool:
        if history.empty or not {"high", "low", "close"}.issubset(history.columns):
            return False
        last_20 = history.tail(20)
        if len(last_20) < 5:
            return False
        max_high = last_20["high"].iloc[:-1].max() if len(last_20) > 1 else last_20["high"].max()
        min_low = last_20["low"].iloc[:-1].min() if len(last_20) > 1 else last_20["low"].min()
        close = float(last_20["close"].iloc[-1])
        return close > max_high or close < min_low
