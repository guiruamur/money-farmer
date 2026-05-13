from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from crypto_farmer.llm.client import AnalysisContext


SYSTEM_MESSAGE = (
    "Eres un analista cuantitativo conservador. Tu objetivo es identificar "
    "oportunidades con relación riesgo/recompensa favorable. Solo emites BUY "
    "o SELL cuando los datos lo justifican; HOLD es perfectamente válido y "
    "preferible a operar con baja convicción. Respondes SIEMPRE con JSON "
    "válido según el schema proporcionado, sin texto adicional."
)


class PromptBuilder:
    def __init__(self, *, template_path: str | Path) -> None:
        path = Path(template_path)
        env = Environment(
            loader=FileSystemLoader(str(path.parent)),
            undefined=StrictUndefined,
            trim_blocks=False,
            lstrip_blocks=False,
        )
        self._template = env.get_template(path.name)

    def render(self, context: AnalysisContext, *, now: datetime) -> str:
        return self._template.render(
            pair=context.pair,
            timeframe=context.timeframe,
            now=now.strftime("%Y-%m-%d %H:%M UTC"),
            indicators=context.indicators,
            ohlcv_summary=context.ohlcv_summary,
            news=context.news,
            memory_hits=context.memory_hits,
            recent_feedback=context.recent_feedback,
        )

    def system_message(self) -> str:
        return SYSTEM_MESSAGE
