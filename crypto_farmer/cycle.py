from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from crypto_farmer.analysis.indicators import IndicatorEngine
from crypto_farmer.analysis.prefilter import Prefilter
from crypto_farmer.data.market import MarketDataSource, MarketFetchError
from crypto_farmer.data.news import NewsFetchError, NewsSource
from crypto_farmer.delivery.notifier import DeliverableSignal, Notifier
from crypto_farmer.learning.embeddings import Embeddings, EmbeddingError
from crypto_farmer.learning.feedback import FeedbackBuilder
from crypto_farmer.learning.memory import Memory
from crypto_farmer.learning.outcomes import OutcomeService
from crypto_farmer.learning.situation import Situation
from crypto_farmer.llm.client import AnalysisContext, LLMCallError
from crypto_farmer.llm.parser import LLMParseError, SignalParser
from crypto_farmer.llm.prompts import PromptBuilder
from crypto_farmer.logging_setup import get_logger
from crypto_farmer.metrics import Metrics
from crypto_farmer.paper.trader import PaperTrader
from crypto_farmer.signals.models import (
    CycleStatus, OHLCVSummary, SignalAction,
)
from crypto_farmer.clock import Clock, SystemClock
from crypto_farmer.storage.db import Storage


log = get_logger(__name__)


@dataclass
class CycleDeps:
    market: MarketDataSource
    news: NewsSource
    indicators: IndicatorEngine
    prefilter: Prefilter
    prompt_builder: PromptBuilder
    parser: SignalParser
    embeddings: Embeddings
    memory: Memory
    feedback: FeedbackBuilder
    outcomes: OutcomeService
    notifier: Notifier
    storage: Storage
    metrics: Metrics
    pairs: list[str]
    timeframe: str
    ohlcv_lookback: int
    min_confidence: int
    news_max_age_hours: int
    memory_k: int
    feedback_lookback: int
    paper_trader: PaperTrader | None = None
    clock: Clock = field(default_factory=SystemClock)


@dataclass
class CycleResult:
    cycle_id: int
    status: CycleStatus
    pairs_analyzed: int
    pairs_passed_prefilter: int
    signals_generated: int
    notes: str | None = None


class Cycle:
    def __init__(self, deps: CycleDeps) -> None:
        self._deps = deps

    def run(self) -> CycleResult:
        d = self._deps
        cycle_id = d.storage.start_cycle()
        d.metrics.inc("cycles_started")
        log.info("cycle_started", extra={"cycle_id": cycle_id})

        notes: list[str] = []
        try:
            ohlcv_by_pair = self._fetch_ohlcv()
        except MarketFetchError as e:
            log.error("cycle_aborted_market_fetch", extra={"cycle_id": cycle_id, "error": str(e)})
            d.storage.finish_cycle(
                cycle_id, status=CycleStatus.FAILED,
                pairs_analyzed=0, pairs_passed_prefilter=0,
                signals_generated=0, notes=f"market_fetch_failed: {e}",
            )
            d.metrics.inc("cycles_failed")
            return CycleResult(
                cycle_id=cycle_id, status=CycleStatus.FAILED,
                pairs_analyzed=0, pairs_passed_prefilter=0,
                signals_generated=0, notes="market_fetch_failed",
            )

        news_items: list = []
        try:
            since = d.clock.now() - timedelta(hours=d.news_max_age_hours)
            news_items = d.news.fetch_recent(since=since)
        except NewsFetchError as e:
            notes.append(f"news_unavailable: {e}")
            log.warning("news_fetch_failed", extra={"cycle_id": cycle_id, "error": str(e)})

        snapshots: dict[str, Any] = {}
        for pair, df in ohlcv_by_pair.items():
            try:
                snapshots[pair] = (df, d.indicators.compute(pair, df))
            except ValueError as e:
                notes.append(f"{pair}_insufficient_data")
                log.warning("indicators_skipped", extra={"pair": pair, "error": str(e)})

        passed: list[tuple[str, Any]] = []
        for pair, (df, snap) in snapshots.items():
            last_row = d.storage.last_signal_for_pair(pair)
            last_sig = None
            if last_row:
                last_sig = (
                    SignalAction(last_row["action"]),
                    datetime.fromisoformat(last_row["generated_at"].replace("Z", "+00:00")),
                )
            decision = d.prefilter.evaluate(
                snap,
                recent_history=df.tail(20).assign(
                    ema_20=df["close"].ewm(span=20).mean().tail(20),
                    ema_50=df["close"].ewm(span=50).mean().tail(20),
                )[["high", "low", "close", "ema_20", "ema_50"]],
                last_signal_for_pair=last_sig,
            )
            if decision.passes:
                passed.append((pair, snap))

        feedback = d.feedback.build(lookback=d.feedback_lookback)
        signals_generated = 0
        for pair, snap in passed:
            df = ohlcv_by_pair[pair]
            relevant_news = [
                {"published_at": n.published_at.isoformat(), "title": n.title}
                for n in news_items if not n.related_pairs or pair in n.related_pairs
            ][:8]
            situation = Situation.from_snapshot(snap)
            memory_hits: list[dict] = []
            embedding = None
            try:
                embedding = d.embeddings.embed(situation.as_text())
                hits = d.memory.search(embedding=embedding, k=d.memory_k, pair_filter=pair)
                memory_hits = [
                    {
                        "age": h.metadata.get("timestamp", "?"),
                        "summary": h.text[:120],
                        "action": h.metadata.get("action", "?"),
                        "outcome_4h": h.metadata.get("return_4h", "?"),
                        "outcome_24h": h.metadata.get("return_24h", "?"),
                    }
                    for h in hits
                ]
            except EmbeddingError as e:
                notes.append(f"embeddings_unavailable: {e}")
                log.warning("embeddings_failed", extra={"pair": pair, "error": str(e)})

            price = float(ohlcv_by_pair[pair]["close"].iloc[-1])

            # Portfolio state: let the LLM know what it already holds so it can
            # reason about SELL on open positions, not just BUY blindly.
            portfolio_state: dict[str, Any] = {}
            if d.paper_trader is not None:
                wallet = d.paper_trader.wallet()
                pos = d.paper_trader.position_for(pair)
                this_pair: dict[str, Any] = {"has_position": pos is not None}
                if pos is not None:
                    unrealized_pct = (price / pos.avg_entry_price - 1.0) * 100.0
                    this_pair.update(
                        entry_price=round(pos.avg_entry_price, 4),
                        qty=round(pos.qty, 6),
                        current_price=round(price, 4),
                        unrealized_pnl_pct=round(unrealized_pct, 2),
                    )
                portfolio_state = {
                    "cash": round(wallet.cash, 2),
                    "open_positions": len(d.paper_trader.positions()),
                    "this_pair": this_pair,
                }

            ctx = AnalysisContext(
                pair=pair, timeframe=d.timeframe,
                indicators=snap,
                ohlcv_summary=OHLCVSummary.from_df(df, recent_n=20).model_dump(),
                news=relevant_news, memory_hits=memory_hits,
                recent_feedback=feedback,
                portfolio_state=portfolio_state,
            )
            t0 = time.monotonic()
            try:
                parsed = d.parser.analyze_with_retry(ctx)
            except LLMParseError as e:
                log.warning("llm_parse_failed", extra={"pair": pair, "error": str(e)})
                d.metrics.inc("llm_parse_failed")
                continue
            except LLMCallError as e:
                # Ollama unreachable / model missing / timeout. Degrade the cycle
                # (skip this pair, keep going) instead of letting it crash.
                notes.append(f"llm_unavailable: {e}")
                log.warning("llm_call_failed", extra={"pair": pair, "error": str(e)})
                d.metrics.inc("llm_call_failed")
                continue
            d.metrics.record_latency("llm", (time.monotonic() - t0) * 1000)

            delivered = parsed.signal.confidence >= d.min_confidence and parsed.signal.action != SignalAction.HOLD
            sig_id = d.storage.save_signal(
                cycle_id=cycle_id, pair=pair, timeframe=d.timeframe,
                signal=parsed.signal, price_at_signal=float(price),
                delivered=delivered,
            )
            d.storage.save_analysis_context(
                signal_id=sig_id,
                indicators=snap.model_dump(mode="json"),
                news=relevant_news, memory_hits=memory_hits,
                feedback_summary=feedback.get("summary", ""),
                prompt_rendered=d.prompt_builder.render(ctx, now=d.clock.now()),
                raw_llm_response=parsed.raw_text,
            )
            d.metrics.inc("signals_generated")
            signals_generated += 1

            if embedding is not None:
                entry_id = d.memory.add(
                    embedding=embedding, text=situation.as_text(),
                    metadata={
                        "pair": pair,
                        "action": parsed.signal.action.value,
                        "signal_id": str(sig_id),
                        "timestamp": d.clock.now().isoformat(),
                    },
                )
                d.storage.update_signal_memory_entry_id(signal_id=sig_id, memory_entry_id=entry_id)
                log.debug("memory_added", extra={"entry_id": entry_id, "signal_id": sig_id})

            d.outcomes.schedule_measurements(
                signal_id=sig_id, generated_at=d.clock.now(),
            )
            if delivered:
                d.notifier.deliver([DeliverableSignal(
                    pair=pair, signal=parsed.signal, price_at_signal=float(price),
                )])

            # Paper trading: ejecutamos sobre cualquier señal con confianza
            # suficiente (incluso si action == HOLD, el trader la ignora).
            # Nota: usamos confidence >= min_confidence como filtro paralelo al
            # de Telegram, así no operamos sobre señales con baja convicción.
            if d.paper_trader is not None and parsed.signal.confidence >= d.min_confidence:
                outcome = d.paper_trader.on_signal(
                    pair=pair, action=parsed.signal.action, price=float(price),
                    now=d.clock.now(),
                )
                # Solo notificamos las acciones interesantes (open/close/no-pos/bancarrota)
                d.notifier.deliver_paper_outcome(outcome)

        status = CycleStatus.OK if not notes else CycleStatus.DEGRADED
        note_str = "; ".join(notes) if notes else None
        d.storage.finish_cycle(
            cycle_id, status=status,
            pairs_analyzed=len(snapshots),
            pairs_passed_prefilter=len(passed),
            signals_generated=signals_generated,
            notes=note_str,
        )
        d.notifier.deliver_cycle_status(status=status, note=note_str)
        log.info("cycle_finished", extra={
            "cycle_id": cycle_id, "status": status.value,
            "signals_generated": signals_generated,
        })
        d.metrics.inc("cycles_ok" if status == CycleStatus.OK else "cycles_degraded")

        return CycleResult(
            cycle_id=cycle_id, status=status,
            pairs_analyzed=len(snapshots),
            pairs_passed_prefilter=len(passed),
            signals_generated=signals_generated, notes=note_str,
        )

    def _fetch_ohlcv(self) -> dict[str, Any]:
        d = self._deps
        out: dict[str, Any] = {}
        for pair in d.pairs:
            out[pair] = d.market.fetch_ohlcv(pair, d.timeframe, d.ohlcv_lookback)
        return out
