from __future__ import annotations

from dataclasses import dataclass

from crypto_farmer.signals.models import IndicatorSnapshot


@dataclass
class Situation:
    pair: str
    rsi: float
    macd: float
    macd_signal: float
    ema_20: float
    ema_50: float
    atr_ratio: float
    volume_ratio: float
    bb_position: float  # 0 = en BB inferior, 1 = en BB superior

    @classmethod
    def from_snapshot(cls, snap: IndicatorSnapshot) -> "Situation":
        bb_width = snap.bb_upper - snap.bb_lower
        bb_pos = ((snap.ema_20 - snap.bb_lower) / bb_width) if bb_width > 0 else 0.5
        atr_ratio = snap.atr_expansion_ratio()
        vol_ratio = snap.volume_anomaly_ratio()
        return cls(
            pair=snap.pair,
            rsi=snap.rsi,
            macd=snap.macd,
            macd_signal=snap.macd_signal,
            ema_20=snap.ema_20,
            ema_50=snap.ema_50,
            atr_ratio=atr_ratio if atr_ratio is not None else 0.0,
            volume_ratio=vol_ratio if vol_ratio is not None else 0.0,
            bb_position=max(0.0, min(1.0, bb_pos)),
        )

    def as_text(self) -> str:
        return (
            f"Situación {self.pair}: "
            f"RSI {self.rsi:.1f}, "
            f"MACD {self.macd:.4f}/signal {self.macd_signal:.4f}, "
            f"EMA20 vs EMA50: {self.ema_20:.2f} vs {self.ema_50:.2f} "
            f"({'alcista' if self.ema_20 > self.ema_50 else 'bajista'}), "
            f"ATR expansion {self.atr_ratio:.2f}x, "
            f"volumen {self.volume_ratio:.2f}x media, "
            f"posición en BB {self.bb_position:.2f}"
        )

    def short_summary(self) -> str:
        rsi_label = (
            "sobreventa" if self.rsi <= 30
            else "sobrecompra" if self.rsi >= 70
            else "neutral"
        )
        trend = "alcista" if self.ema_20 > self.ema_50 else "bajista"
        return (
            f"{self.pair} RSI {rsi_label} ({self.rsi:.0f}), "
            f"tendencia {trend}, vol {self.volume_ratio:.1f}x"
        )
