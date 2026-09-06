"""Agent run evaluator.

The evaluator combines deterministic validation with an LLM judge.

Deterministic checks handle hard failures cheaply. The LLM judge evaluates
semantic quality when a run produced a usable result.
"""

from __future__ import annotations

import json
from typing import Any

import neatlogs
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.agent_version import AgentVersion
from app.schemas.evaluation import EvaluationResult
from app.schemas.plan import ExecutionPlan
from app.schemas.run import Run
from app.services.llm import service as llm_service
from app.services.llm.base import ChatMessage, ChatRole, LLMProvider


class EvaluationError(Exception):
    """Base error for evaluator failures."""


class EvaluationJudgeOutput(BaseModel):
    """Validated response returned by the LLM judge."""

    model_config = ConfigDict(extra="forbid")

    task_completion: float = Field(ge=0.0, le=1.0)
    correctness: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    quality: float = Field(ge=0.0, le=1.0)
    passed: bool
    notes: str = Field(min_length=1, max_length=5000)


class AgentEvaluator:
    """Evaluate the outcome of an agent run."""

    PASS_THRESHOLD = 0.70

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @neatlogs.span(
        kind="AGENT",
        name="agent.evaluate",
    )
    async def evaluate(
        self,
        *,
        run: Run,
        agent_version: AgentVersion,
        task: str,
        plan: ExecutionPlan | None = None,
        execution_context: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        """Evaluate one completed or failed agent run."""

        deterministic = self._deterministic_checks(
            run=run,
            task=task,
        )

        # Hard runtime failures do not need an expensive LLM judge.
        if not deterministic["eligible_for_judging"]:
            return EvaluationResult(
                agent_id=run.agent_id,
                agent_version_id=run.agent_version_id,
                run_id=run.id,
                suite="runtime",
                metrics={
                    "task_completion": 0.0,
                    "correctness": 0.0,
                    "completeness": 0.0,
                    "quality": 0.0,
                },
                score=0.0,
                passed=False,
                evaluator="code",
                notes=deterministic["notes"],
            )

        judge_prompt = self._build_judge_prompt(
            task=task,
            run=run,
            plan=plan,
            execution_context=execution_context or {},
        )

        try:
            response = await llm_service.achat(
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content=self._judge_system_prompt(),
                    ),
                    ChatMessage(
                        role=ChatRole.USER,
                        content=judge_prompt,
                    ),
                ],
                provider=self._provider,
                model=agent_version.model,
                temperature=0.0,
                max_tokens=agent_version.max_tokens,
            )
        except Exception as exc:
            raise EvaluationError(
                f"Failed to evaluate agent run: {exc}"
            ) from exc

        judged = self._parse_judge_output(response.content)

        score = self._aggregate_score(
            judged
        )

        return EvaluationResult(
            agent_id=run.agent_id,
            agent_version_id=run.agent_version_id,
            run_id=run.id,
            suite="agent-run",
            metrics={
                "task_completion": judged.task_completion,
                "correctness": judged.correctness,
                "completeness": judged.completeness,
                "quality": judged.quality,
            },
            score=score,
            passed=(
                judged.passed
                and score >= self.PASS_THRESHOLD
            ),
            evaluator=f"llm:{response.model}",
            notes=judged.notes,
        )

    @staticmethod
    def _deterministic_checks(
        *,
        run: Run,
        task: str,
    ) -> dict[str, Any]:
        """Perform cheap checks before invoking the judge."""

        if not task.strip():
            return {
                "eligible_for_judging": False,
                "notes": "Evaluation skipped because the task was empty.",
            }

        if run.status.value in {
            "failed",
            "cancelled",
            "timed_out",
        }:
            message = (
                run.error.message
                if run.error is not None
                else f"Run ended with status '{run.status.value}'."
            )

            return {
                "eligible_for_judging": False,
                "notes": message,
            }

        if run.outputs is None:
            return {
                "eligible_for_judging": False,
                "notes": "Run succeeded but produced no outputs.",
            }

        return {
            "eligible_for_judging": True,
            "notes": "Run passed deterministic pre-evaluation checks.",
        }

    @staticmethod
    def _judge_system_prompt() -> str:
        return """You are Accord's independent agent evaluator.

Your job is to judge whether an agent actually completed the user's task.

Evaluate the RESULT, not the agent's intentions.

Rules:
1. Return ONLY valid JSON.
2. Do not return Markdown or code fences.
3. Do not reward an answer merely because it sounds confident.
4. Judge only evidence contained in the supplied task, plan, execution data,
   and final output.
5. Penalize unsupported claims, missing requirements, incorrect results,
   incomplete work, and irrelevant output.
6. Do not reveal chain-of-thought.
7. Scores must be between 0 and 1.

Return exactly:

{
  "task_completion": 0.0,
  "correctness": 0.0,
  "completeness": 0.0,
  "quality": 0.0,
  "passed": false,
  "notes": "Concise explanation of the judgment."
}

Definitions:
- task_completion: Did the agent accomplish the user's requested objective?
- correctness: Are the claims/results supported and accurate?
- completeness: Were the important requested parts addressed?
- quality: Is the result clear, useful, and appropriately presented?
- passed: Your overall binary judgment of whether the task was successful.
"""

    @classmethod
    def _build_judge_prompt(
        cls,
        *,
        task: str,
        run: Run,
        plan: ExecutionPlan | None,
        execution_context: dict[str, Any],
    ) -> str:
        payload = {
            "task": task,
            "run": {
                "status": run.status.value,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "error": (
                    run.error.model_dump()
                    if run.error
                    else None
                ),
                "usage": (
                    run.usage.model_dump()
                    if run.usage
                    else None
                ),
            },
            "plan": (
                plan.model_dump()
                if plan is not None
                else None
            ),
            "execution_context": execution_context,
        }

        return (
            "Evaluate the following completed agent run.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}"
        )

    @staticmethod
    def _parse_judge_output(
        content: str,
    ) -> EvaluationJudgeOutput:
        cleaned = content.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        try:
            raw = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise EvaluationError(
                f"Evaluator returned invalid JSON: {exc}"
            ) from exc

        try:
            return EvaluationJudgeOutput.model_validate(raw)
        except ValidationError as exc:
            raise EvaluationError(
                f"Evaluator returned an invalid evaluation: {exc}"
            ) from exc

    @staticmethod
    def _aggregate_score(
        result: EvaluationJudgeOutput,
    ) -> float:
        """Calculate the aggregate score from evaluation dimensions."""

        return round(
            (
                result.task_completion * 0.35
                + result.correctness * 0.30
                + result.completeness * 0.20
                + result.quality * 0.15
            ),
            4,
        )