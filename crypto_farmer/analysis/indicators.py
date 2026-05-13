from __future__ import annotations

from datetime import timezone

import pandas as pd
import pandas_ta as ta

from crypto_farmer.signals.models import IndicatorSnapshot


class IndicatorEngine:
    MIN_ROWS = 60

    def compute(self, pair: str, df: pd.DataFrame) -> IndicatorSnapshot:
        if len(df) < self.MIN_ROWS:
            raise ValueError(f"Faltan datos: {len(df)} filas, mínimo {self.MIN_ROWS}")

        d = df.copy()
        d["rsi"] = ta.rsi(d["close"], length=14)
        macd = ta.macd(d["close"], fast=12, slow=26, signal=9)
        d["macd"] = macd["MACD_12_26_9"]
        d["macd_signal"] = macd["MACDs_12_26_9"]
        d["macd_hist"] = macd["MACDh_12_26_9"]
        d["ema_20"] = ta.ema(d["close"], length=20)
        d["ema_50"] = ta.ema(d["close"], length=50)
        bb = ta.bbands(d["close"], length=20, std=2.0)
        d["bb_upper"] = bb["BBU_20_2.0_2.0"]
        d["bb_lower"] = bb["BBL_20_2.0_2.0"]
        d["atr"] = ta.atr(d["high"], d["low"], d["close"], length=14)
        d["atr_mean_20"] = d["atr"].rolling(20).mean()
        d["volume_mean_24h"] = d["volume"].rolling(96).mean()  # 96×15min = 24h

        last = d.iloc[-1]
        ts = last["timestamp"]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        return IndicatorSnapshot(
            pair=pair,
            timestamp=ts,
            rsi=float(last["rsi"]),
            macd=float(last["macd"]),
            macd_signal=float(last["macd_signal"]),
            macd_hist=float(last["macd_hist"]),
            ema_20=float(last["ema_20"]),
            ema_50=float(last["ema_50"]),
            bb_upper=float(last["bb_upper"]),
            bb_lower=float(last["bb_lower"]),
            atr=float(last["atr"]),
            atr_mean_20=float(last["atr_mean_20"]) if pd.notna(last["atr_mean_20"]) else float(last["atr"]),
            volume=float(last["volume"]),
            volume_mean_24h=float(last["volume_mean_24h"]) if pd.notna(last["volume_mean_24h"]) else float(d["volume"].mean()),
        )
