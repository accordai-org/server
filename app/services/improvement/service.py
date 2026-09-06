"""Agent improvement loop."""

from __future__ import annotations

from app.schemas.agent_version import AgentVersion
from app.schemas.evaluation import EvaluationResult
from app.schemas.strategy import LearnedStrategy
from app.schemas.enums import StrategyStatus


class ImprovementError(Exception):
    """Base improvement-loop error."""


class ImprovementService:
    """Turn learned strategies into candidate agent versions."""

    MIN_CONFIDENCE = 0.75
    MIN_SCORE_IMPROVEMENT = 0.02

    def create_candidate_version(
        self,
        *,
        source_version: AgentVersion,
        strategy: LearnedStrategy,
    ) -> AgentVersion:
        """Create a new version containing a validated strategy."""

        if strategy.status is not StrategyStatus.VALIDATED:
            raise ImprovementError(
                "Only validated strategies can create candidate versions."
            )

        prompt = (source_version.system_prompt or "").strip()

        strategy_block = (
            "\n\nLearned strategy:\n"
            f"{strategy.strategy_text.strip()}"
        )

        new_prompt = (
            f"{prompt}{strategy_block}"
            if prompt
            else strategy_block.strip()
        )

        major, minor, _ = (
            int(part)
            for part in source_version.version.split(".")
        )

        return AgentVersion(
            agent_id=source_version.agent_id,
            version=f"{major}.{minor + 1}.0",
            system_prompt=new_prompt,
            model=source_version.model,
            temperature=source_version.temperature,
            max_tokens=source_version.max_tokens,
            parent_version_id=source_version.id,
            changelog=f"Candidate improvement: {strategy.title}",
            created_by="improvement",
        )

    def should_promote(
        self,
        *,
        baseline: EvaluationResult,
        candidate: EvaluationResult,
        strategy: LearnedStrategy,
    ) -> bool:
        """Return whether a candidate materially improves the baseline."""

        if strategy.status is not StrategyStatus.VALIDATED:
            return False

        if strategy.confidence < 0.75:
            return False

        if baseline.score is None or candidate.score is None:
            return False

        if not candidate.passed:
            return False

        return (
            candidate.score - baseline.score
            >= self.MIN_SCORE_IMPROVEMENT
        )

    def promote(
        self,
        *,
        strategy: LearnedStrategy,
        candidate_version: AgentVersion,
        baseline: EvaluationResult,
        candidate: EvaluationResult,
    ) -> AgentVersion:
        """Mark a candidate as the adopted version."""

        if not self.should_promote(
            baseline=baseline,
            candidate=candidate,
            strategy=strategy,
        ):
            raise ImprovementError(
                "Candidate does not meet promotion criteria."
            )

        strategy.promoted_in_version_id = candidate_version.id

        if candidate.score and baseline.score is not None:
          strategy.metrics = {
              **strategy.metrics,
              "baseline_score": baseline.score,
              "candidate_score": candidate.score,
              "score_delta": round(
                  candidate.score - baseline.score,
                  4,
              ),
          }
        else:
          strategy.metrics = {
              **strategy.metrics,
              "baseline_score": baseline.score,
              "candidate_score": candidate.score,
              "score_delta": 0
          }

        

        return candidate_version