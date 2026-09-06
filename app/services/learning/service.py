"""Learning and strategy extraction."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.schemas.agent_version import AgentVersion
from app.schemas.evaluation import EvaluationResult
from app.schemas.run import Run
from app.schemas.strategy import LearnedStrategy
from app.schemas.enums import StrategyStatus
from app.services.llm import service as llm_service
from app.services.llm.base import (
    ChatMessage,
    ChatRole,
    LLMProvider,
)


class LearningError(Exception):
    """Base learning error."""


class LearningService:
    """Extract reusable strategies from successful agent runs."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def learn_from_run(
        self,
        *,
        agent_version: AgentVersion,
        run: Run,
        evaluation: EvaluationResult,
        memories: list[Any] | None = None,
    ) -> LearnedStrategy | None:
        """Derive a strategy when a run provides meaningful evidence."""

        if not evaluation.passed:
            return None

        prompt = self._build_prompt(
            run=run,
            evaluation=evaluation,
            memories=memories or [],
        )

        try:
            response = await llm_service.achat(
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content=self._system_prompt(),
                    ),
                    ChatMessage(
                        role=ChatRole.USER,
                        content=prompt,
                    ),
                ],
                provider=self._provider,
                model=agent_version.model,
                temperature=0.1,
                max_tokens=agent_version.max_tokens,
            )
        except Exception as exc:
            raise LearningError(
                f"Failed to derive learning strategy: {exc}"
            ) from exc

        payload = self._parse(response.content)

        return LearnedStrategy(
            agent_id=run.agent_id,
            title=payload["title"],
            strategy_text=payload["strategy_text"],
            source_run_ids=[run.id],
            source_memory_ids=[
                memory.id
                for memory in (memories or [])
                if hasattr(memory, "id")
            ],
            confidence=payload["confidence"],
            status=StrategyStatus.CANDIDATE,
            metrics={
                "evaluation_score": evaluation.score,
                **evaluation.metrics,
            },
        )

    @staticmethod
    def _system_prompt() -> str:
        return """You are Accord's learning engine.

Analyze a successful agent run and extract ONE reusable strategy.

A strategy must:
- describe an actionable approach,
- generalize beyond this exact run,
- be supported by the supplied evidence,
- avoid storing sensitive transient details,
- not contain chain-of-thought.

Return ONLY JSON:

{
  "title": "short strategy name",
  "strategy_text": "actionable reusable guidance",
  "confidence": 0.0
}

Confidence must be between 0 and 1.
"""

    @staticmethod
    def _build_prompt(
        *,
        run: Run,
        evaluation: EvaluationResult,
        memories: list[Any],
    ) -> str:
        payload = {
            "run": {
                "inputs": run.inputs,
                "outputs": run.outputs,
            },
            "evaluation": evaluation.model_dump(),
            "relevant_memories": [
                memory.model_dump()
                if hasattr(memory, "model_dump")
                else memory
                for memory in memories
            ],
        }

        return (
            "Extract a reusable strategy from this successful run.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}"
        )

    @staticmethod
    def _parse(content: str) -> dict[str, Any]:
        cleaned = content.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LearningError(
                f"Learning engine returned invalid JSON: {exc}"
            ) from exc

        if not isinstance(result, dict):
            raise LearningError(
                "Learning engine response must be an object."
            )

        title = result.get("title")
        strategy_text = result.get("strategy_text")
        confidence = result.get("confidence")

        if not isinstance(title, str) or not title.strip():
            raise LearningError(
                "Learning engine returned an invalid title."
            )

        if (
            not isinstance(strategy_text, str)
            or not strategy_text.strip()
        ):
            raise LearningError(
                "Learning engine returned invalid strategy text."
            )

        if (
            not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise LearningError(
                "Learning engine returned invalid confidence."
            )

        return {
            "title": title.strip(),
            "strategy_text": strategy_text.strip(),
            "confidence": float(confidence),
        }