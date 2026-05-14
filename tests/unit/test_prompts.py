from datetime import datetime, timezone
from pathlib import Path

from crypto_farmer.llm.client import AnalysisContext
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.signals.models import IndicatorSnapshot, OHLCVCandle, OHLCVSummary

PROMPT_PATH = Path("config/prompts/analyze_pair.j2")


def _ctx() -> AnalysisContext:
    snap = IndicatorSnapshot(
        pair="BTC/USDT", timestamp=datetime.now(timezone.utc),
        rsi=28.5, macd=1.0, macd_signal=0.5, macd_hist=0.5,
        ema_20=100.0, ema_50=99.0,
        bb_upper=110.0, bb_lower=90.0,
        atr=5.0, atr_mean_20=4.0,
        volume=120.0, volume_mean_24h=100.0,
    )
    summary = OHLCVSummary(
        recent=[OHLCVCandle(open=100, high=102, low=99, close=101, volume=10)],
        highest_high=102, lowest_low=99,
    ).model_dump()
    return AnalysisContext(
        pair="BTC/USDT", timeframe="15m", indicators=snap,
        ohlcv_summary=summary, news=[],
        memory_hits=[], recent_feedback={"lookback": 20, "win_rate": 0, "summary": "n/a"},
    )


def test_prompt_renders_minimal_context():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    rendered = builder.render(_ctx(), now=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc))
    assert "BTC/USDT" in rendered
    assert "RSI: 28.50" in rendered
    assert "(sin noticias relevantes)" in rendered
    assert "(sin situaciones similares en memoria)" in rendered
    assert "(paper trading no activo)" in rendered
    assert "Tu tarea" in rendered


def test_prompt_renders_open_position():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    ctx = _ctx()
    ctx.portfolio_state = {
        "cash": 639.68,
        "open_positions": 2,
        "this_pair": {
            "has_position": True, "entry_price": 90.61, "qty": 2.2073,
            "current_price": 91.09, "unrealized_pnl_pct": 0.53,
        },
    }
    rendered = builder.render(ctx, now=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc))
    assert "TIENES UNA POSICIÓN ABIERTA" in rendered
    assert "90.61" in rendered
    assert "0.53%" in rendered


def test_prompt_renders_no_position():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    ctx = _ctx()
    ctx.portfolio_state = {
        "cash": 800.0, "open_positions": 1,
        "this_pair": {"has_position": False},
    }
    rendered = builder.render(ctx, now=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc))
    assert "No tienes posición abierta" in rendered
    assert "Cash disponible: 800.0" in rendered


def test_prompt_renders_with_news_and_memory():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    ctx = _ctx()
    ctx.news = [{"published_at": "2026-05-12T09:00:00Z", "title": "BTC rompe"}]
    ctx.memory_hits = [{
        "age": "3 días", "summary": "RSI 27, volumen alto",
        "action": "BUY", "outcome_4h": "+2.1%", "outcome_24h": "+5.3%",
    }]
    rendered = builder.render(ctx, now=datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc))
    assert "BTC rompe" in rendered
    assert "+2.1%" in rendered


def test_system_message_is_stable():
    builder = PromptBuilder(template_path=PROMPT_PATH)
    sys = builder.system_message()
    assert "analista cuantitativo" in sys
    assert "JSON" in sys
    assert "SELL" in sys  # must instruct closing open positions
