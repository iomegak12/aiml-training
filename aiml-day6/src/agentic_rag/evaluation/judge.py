"""LLM-as-a-judge: scores a final answer against its evidence and gates the Coordinator.

The judge uses its own model and key (``JUDGE_OPENAI_MODEL`` / ``JUDGE_OPENAI_API_KEY``),
so the answer is never graded by the model that wrote it. Four criteria are scored 0-100
and combined with fixed weights into ``overall``; the answer passes when ``overall`` is at
least ``JUDGE_PASS_SCORE``. On a failure the ``critique`` and ``targets`` tell the
Coordinator which parts to redo (for example ``product_manuals`` or ``synthesis``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_rag.config import AgentSettings
from agentic_rag.llm import judge_llm, structured

WEIGHTS = {"groundedness": 0.35, "answer_relevance": 0.30, "completeness": 0.20, "context_relevance": 0.15}

JUDGE_PROMPT = """You are a strict evaluator of answers produced by an enterprise assistant.
Score each criterion from 0 to 100:
- context_relevance: is the EVIDENCE relevant to the question (right policy version, right product model, right customer)?
- groundedness: is every factual claim in the ANSWER supported by the EVIDENCE? Penalise invented numbers heavily.
- answer_relevance: does the ANSWER address what was asked, directly?
- completeness: are all parts of the question answered (or explicitly declared unknown)?
An honest "I don't know" for a question the evidence cannot answer is grounded and relevant; score it high on
groundedness and judge completeness by whether anything answerable was left out.
In `critique`, say concisely what is wrong or missing. In `targets`, list what should be redone, using these names
when they apply: {agents}, "synthesis" (answer writing), "planning" (wrong or missing agents)."""


class JudgeScores(BaseModel):
    """Per-criterion scores from the judge model."""

    context_relevance: int = Field(ge=0, le=100)
    groundedness: int = Field(ge=0, le=100)
    answer_relevance: int = Field(ge=0, le=100)
    completeness: int = Field(ge=0, le=100)
    critique: str = Field(description="What is wrong or missing; empty when the answer is excellent")
    targets: list[str] = Field(default_factory=list, description="Agents or steps to redo")


class JudgeVerdict(BaseModel):
    """Judge scores plus the weighted overall score and the pass/fail decision."""

    scores: JudgeScores
    overall: float
    threshold: int
    passed: bool
    judge_model: str

    def summary(self) -> str:
        """One-line summary such as ``86.5/100 PASS (ground 90, rel 85, compl 80, ctx 88)``."""
        s = self.scores
        return (f"{self.overall:.1f}/100 {'PASS' if self.passed else 'FAIL'} (ground {s.groundedness}, "
                f"rel {s.answer_relevance}, compl {s.completeness}, ctx {s.context_relevance})")


def weighted_overall(scores: JudgeScores) -> float:
    """Weighted mean of the four criteria (weights in ``WEIGHTS``)."""
    return round(sum(getattr(scores, name) * weight for name, weight in WEIGHTS.items()), 1)


def _messages(question: str, answer: str, evidence: str, agents: list[str] | None) -> list[tuple[str, str]]:
    """Build the judge prompt."""
    names = ", ".join(f'"{a}"' for a in (agents or [])) or '"retrieval"'
    return [("system", JUDGE_PROMPT.format(agents=names)),
            ("human", f"QUESTION:\n{question}\n\nEVIDENCE:\n{evidence or '(none)'}\n\nANSWER:\n{answer}")]


def _verdict(settings: AgentSettings, scores: JudgeScores, pass_score: int | None) -> JudgeVerdict:
    """Combine scores into a verdict."""
    threshold = settings.judge_pass_score if pass_score is None else pass_score
    overall = weighted_overall(scores)
    return JudgeVerdict(scores=scores, overall=overall, threshold=threshold, passed=overall >= threshold,
                        judge_model=settings.judge_model)


def judge_answer(settings: AgentSettings, question: str, answer: str, evidence: str,
                 agents: list[str] | None = None, pass_score: int | None = None) -> JudgeVerdict:
    """Score ``answer`` to ``question`` against ``evidence`` (synchronous)."""
    scores = structured(judge_llm(settings), JudgeScores).invoke(_messages(question, answer, evidence, agents))
    return _verdict(settings, scores, pass_score)


async def ajudge_answer(settings: AgentSettings, question: str, answer: str, evidence: str,
                        agents: list[str] | None = None, pass_score: int | None = None) -> JudgeVerdict:
    """Asynchronous variant of :func:`judge_answer`."""
    scores = await structured(judge_llm(settings), JudgeScores).ainvoke(_messages(question, answer, evidence, agents))
    return _verdict(settings, scores, pass_score)
