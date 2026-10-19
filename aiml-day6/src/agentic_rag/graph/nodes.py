"""Nodes and routing functions of the Coordinator graph.

Flow of one question::

    start_turn -> load_memory -> plan --(clarify?)--> clarify -> plan
                                  |
                                  +--Send x N (parallel)--> run_step --> reflect --(more ready steps)--> run_step ...
                                                                           |--(gaps: replan)--> plan
                                                                           +--(done)--> [approve_actions -> execute_actions] -> synthesize
    synthesize -> judge --(below JUDGE_PASS_SCORE and retries left)--> plan (with the critique)
                    +--(pass or out of retries)--> finalize -> save_memory -> END

The Coordinator's own thinking (plan, reflect, synthesize) runs on ``OPENAI_MODEL`` at
``COORDINATOR_REASONING_EFFORT``; specialists run at low effort inside ``run_step``.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.store.base import BaseStore
from langgraph.types import Send, interrupt

from agentic_rag.agents.base import run_specialist, task_message
from agentic_rag.agents.registry import Specialist, roster
from agentic_rag.agents.reports import AgentReport, Evidence, ProposedAction
from agentic_rag.config import AgentSettings
from agentic_rag.evaluation.judge import ajudge_answer
from agentic_rag.graph import prompts
from agentic_rag.graph.state import CoordinatorState, Plan, Reflection, StepInput, UserFacts
from agentic_rag.llm import coordinator_llm, fast_llm, message_text, structured
from agentic_rag.mcp_client import CrmToolkit, tool_text
from agentic_rag.memory import recall_facts, remember_facts
from agentic_rag.skills_sync import skill_body

MAX_CLARIFICATIONS = 2
APPROVE_WORDS = {"approve", "approved", "yes", "y", "ok", "true", "accept", "edit"}


def _text(message: AnyMessage) -> str:
    """Plain text of a conversation message."""
    return message.text if isinstance(message.text, str) else str(message.content)


def _decision(value: Any) -> str:
    """Normalise a human decision (``approve``, ``yes``, ``True`` ...) to ``approved`` or ``rejected``."""
    return "approved" if str(value).strip().lower() in APPROVE_WORDS else "rejected"


class Coordinator:
    """Holds the team, the CRM write tools and the Coordinator's models; its methods are the graph nodes."""

    def __init__(self, settings: AgentSettings, team: dict[str, Specialist], crm: CrmToolkit) -> None:
        """Prepare the models (high-effort coordinator, fast memory extractor) and load the coordination skill."""
        self.settings = settings
        self.team = team
        self.crm = crm
        self.planner = structured(coordinator_llm(settings), Plan)
        self.reflector = structured(coordinator_llm(settings), Reflection)
        self.writer = coordinator_llm(settings)
        self.fact_extractor = structured(fast_llm(settings), UserFacts)
        self.coordination_skill = skill_body(settings.skills_dir / "coordination" / "SKILL.md")

    # ------------------------------------------------------------------ helpers
    def available(self) -> list[str]:
        """Names of the specialists that can run."""
        return [name for name, member in self.team.items() if member.available]

    def budget_left(self, state: CoordinatorState) -> int:
        """Specialist runs left for this question (``MAX_AGENT_CALLS``)."""
        return max(0, self.settings.max_agent_calls - state.get("agent_calls", 0))

    @staticmethod
    def pending(state: CoordinatorState) -> list[dict]:
        """Plan steps that have not run yet."""
        done = set(state.get("completed", []))
        return [s for s in state.get("plan", []) if s["id"] not in done]

    def ready(self, state: CoordinatorState) -> list[dict]:
        """Pending steps whose dependencies have all completed (cycles are broken by taking the first step)."""
        done = set(state.get("completed", []))
        ids = {s["id"] for s in state.get("plan", [])}
        pending = self.pending(state)
        ready = [s for s in pending if all(d in done for d in s.get("depends_on", []) if d in ids)]
        return ready or pending[:1]

    @staticmethod
    def reports(state: CoordinatorState) -> list[AgentReport]:
        """The specialist reports gathered this turn."""
        return [AgentReport.model_validate(r) for r in state.get("reports", [])]

    @classmethod
    def evidence_index(cls, state: CoordinatorState) -> list[tuple[str, AgentReport, Evidence]]:
        """All evidence of this turn numbered ``E1``, ``E2`` ... (used by synthesis and the judge)."""
        items = [(r, e) for r in cls.reports(state) for e in r.evidence]
        return [(f"E{i}", r, e) for i, (r, e) in enumerate(items, start=1)]

    @classmethod
    def evidence_text(cls, state: CoordinatorState, quote_chars: int = 500) -> str:
        """Evidence list for prompts: ``[E1] HR-POL-001-V3.0 p.2 (hr_policy): "quote"``."""
        lines = [f"[{eid}] {e.cite()} ({r.agent}{', ' + e.date if e.date else ''}): \"{e.quote[:quote_chars]}\""
                 for eid, r, e in cls.evidence_index(state)]
        return "\n".join(lines) or "(no evidence)"

    @classmethod
    def reports_digest(cls, state: CoordinatorState) -> str:
        """Compact view of every report: step, agent, goal, findings, confidence, gaps, evidence IDs."""
        ids: dict[str, list[str]] = {}
        for eid, report, _ in cls.evidence_index(state):
            ids.setdefault(report.step_id, []).append(eid)
        blocks = []
        for r in cls.reports(state):
            blocks.append(
                f"### {r.step_id} - {r.agent} (confidence {r.confidence:.2f}{', ERROR' if r.error else ''})\n"
                f"Goal: {r.goal}\nFindings: {r.findings}\n"
                f"Gaps: {'; '.join(r.gaps) or 'none'}\nEvidence: {', '.join(ids.get(r.step_id, [])) or 'none'}"
                + (f"\nProposed actions: {[a.tool + ' ' + json.dumps(a.arguments()) for a in r.proposed_actions]}"
                   if r.proposed_actions else ""))
        return "\n\n".join(blocks) or "(no reports yet)"

    @staticmethod
    def clarifications_text(state: CoordinatorState) -> str:
        """Clarifying questions asked this turn and the user's answers."""
        return "\n".join(f"Q: {c['question']}\nA: {c['answer']}" for c in state.get("clarifications", [])) or "(none)"

    @staticmethod
    def memories_text(state: CoordinatorState) -> str:
        """Long-term facts about the user as a bullet list."""
        return "\n".join(f"- {m}" for m in state.get("memories", [])) or "(nothing yet)"

    def undecided_actions(self, state: CoordinatorState) -> list[tuple[str, ProposedAction]]:
        """Proposed ticket actions that the human has not approved or rejected yet (deduplicated)."""
        decided = {a["signature"] for a in state.get("decided_actions", [])}
        seen: dict[str, tuple[str, ProposedAction]] = {}
        for report in self.reports(state):
            for action in report.proposed_actions:
                sig = action.signature()
                if sig not in decided and sig not in seen:
                    seen[sig] = (report.step_id, action)
        return list(seen.values())

    def notes_for(self, step: dict, state: CoordinatorState) -> str:
        """Findings of the steps this step depends on (what the specialist needs from earlier work)."""
        deps = set(step.get("depends_on", []))
        notes = [f"- {r.step_id} ({r.agent}): {r.findings}" for r in self.reports(state) if r.step_id in deps]
        return "\n".join(notes)

    def sends(self, state: CoordinatorState) -> list[Send]:
        """``Send`` one ``run_step`` per ready step, within the remaining budget - they run in parallel."""
        steps = self.ready(state)[: self.budget_left(state)]
        return [Send("run_step", StepInput(step=s, question=state["question"], notes=self.notes_for(s, state)))
                for s in steps]

    def to_answer(self, state: CoordinatorState) -> str:
        """Next node once the work is done: approval first if ticket actions are waiting."""
        return "approve_actions" if self.undecided_actions(state) else "synthesize"

    # -------------------------------------------------------------------- nodes
    async def start_turn(self, state: CoordinatorState) -> dict:
        """Start a new question: read it from the last user message and reset per-turn fields."""
        messages = state.get("messages", [])
        question = _text(messages[-1]) if messages else ""
        history = "\n".join(f"{'User' if m.type == 'human' else 'Assistant'}: {_text(m)[:600]}"
                            for m in messages[:-1][-6:])
        return {"question": question, "history": history or "(new conversation)",
                "user_id": state.get("user_id") or "anonymous", "clarifications": [], "clarifying_question": None,
                "plan": [], "plan_history": None, "reports": None, "completed": None, "agent_calls": None,
                "replans": 0, "reflection": {}, "decided_actions": None, "executed_actions": None,
                "draft_answer": "", "attempts": None,
                "judge_feedback": "", "final": {}}

    async def load_memory(self, state: CoordinatorState, *, store: BaseStore) -> dict:
        """Recall long-term facts about the user (Coordinator-owned memory)."""
        return {"memories": await recall_facts(store, state["user_id"])}

    async def plan(self, state: CoordinatorState) -> dict:
        """Plan (or replan) specialist steps - or decide that a clarifying question is needed."""
        history = state.get("plan_history", [])
        if state.get("reflection", {}).get("decision") == "replan":
            trigger = f"REPLAN after reflection. Gaps to close: {state['reflection'].get('gaps')}"
        elif state.get("judge_feedback") and state.get("attempts"):
            trigger = (f"RETRY after the quality review failed. Previous answer:\n{state.get('draft_answer', '')}\n\n"
                       f"Judge critique: {state['judge_feedback']}\nAdd steps only for the weak parts; return no "
                       "steps if only the answer writing must improve.")
        elif history:
            trigger = "Continue planning with the clarification above."
        else:
            trigger = "Initial plan for this question."
        system = prompts.PLAN_SYSTEM.format(coordination_skill=self.coordination_skill, roster=roster(self.team),
                                            budget=self.budget_left(state),
                                            clarifications_count=len(state.get("clarifications", [])),
                                            max_clarifications=MAX_CLARIFICATIONS)
        human = prompts.PLAN_HUMAN.format(question=state["question"], conversation=state.get("history", ""),
                                          memories=self.memories_text(state),
                                          clarifications=self.clarifications_text(state),
                                          work_done=self.reports_digest(state), trigger=trigger)
        plan: Plan = await self.planner.ainvoke([("system", system), ("human", human)])

        if plan.clarifying_question and len(state.get("clarifications", [])) < MAX_CLARIFICATIONS:
            return {"clarifying_question": plan.clarifying_question,
                    "plan_history": [{"round": len(history) + 1, "trigger": trigger.split("\n")[0],
                                      "reasoning": plan.reasoning, "clarifying_question": plan.clarifying_question,
                                      "steps": []}]}

        existing = {s["id"] for s in state.get("plan", [])}
        available = set(self.available())
        renamed: dict[str, str] = {}
        new_steps, dropped = [], []
        for step in plan.steps:
            if step.agent not in available:
                dropped.append(f"{step.id}: agent {step.agent!r} unavailable")
                continue
            new_id = step.id if step.id not in existing | set(renamed.values()) else f"{step.id}r{len(history) + 1}"
            renamed[step.id] = new_id
            new_steps.append(step.model_copy(update={"id": new_id}))
        steps = [s.model_copy(update={"depends_on": [renamed.get(d, d) for d in s.depends_on]}).model_dump()
                 for s in new_steps]
        return {"plan": state.get("plan", []) + steps, "clarifying_question": None,
                "plan_history": [{"round": len(history) + 1, "trigger": trigger.split("\n")[0],
                                  "reasoning": plan.reasoning, "steps": steps, "dropped": dropped}]}

    async def clarify(self, state: CoordinatorState) -> dict:
        """Pause the graph (interrupt) and ask the user the clarifying question; resume with their answer."""
        question = state["clarifying_question"]
        answer = interrupt({"type": "clarification", "question": question})
        return {"clarifications": state.get("clarifications", []) + [{"question": question, "answer": str(answer)}],
                "clarifying_question": None,
                "messages": [AIMessage(question), HumanMessage(str(answer))]}

    async def run_step(self, payload: StepInput) -> dict:
        """Run one specialist on one plan step and append its ``AgentReport``."""
        step = payload["step"]
        member = self.team[step["agent"]]
        message = task_message(payload["question"], step["id"], step["goal"], step.get("success_criteria", ""),
                               payload.get("notes", ""))
        report = await run_specialist(member.agent, step["agent"], step["id"], step["goal"], message)
        return {"reports": [report.model_dump()], "completed": [step["id"]], "agent_calls": 1}

    async def reflect(self, state: CoordinatorState) -> dict:
        """After a batch of steps: continue with ready steps, replan for important gaps, or move on to answer."""
        if self.pending(state) and self.budget_left(state):
            return {"reflection": {"decision": "continue", "reason": "planned steps remain"}}
        replans = state.get("replans", 0)
        if replans >= self.settings.max_replans or not self.budget_left(state):
            reason = "replan limit reached" if replans >= self.settings.max_replans else "agent-call budget used up"
            return {"reflection": {"decision": "synthesize", "reason": reason}}
        plan_text = "\n".join(f"- {s['id']} {s['agent']}: {s['goal']}" for s in state.get("plan", []))
        system = prompts.REFLECT_SYSTEM.format(replans_left=self.settings.max_replans - replans,
                                               budget=self.budget_left(state))
        human = prompts.REFLECT_HUMAN.format(question=state["question"], plan=plan_text,
                                             reports=self.reports_digest(state))
        result: Reflection = await self.reflector.ainvoke([("system", system), ("human", human)])
        update: dict[str, Any] = {"reflection": result.model_dump()}
        if result.decision == "replan":
            update["replans"] = replans + 1
        return update

    async def approve_actions(self, state: CoordinatorState) -> dict:
        """Pause for human approval of proposed ticket writes (approve, reject or edit each one)."""
        pending = self.undecided_actions(state)
        request = [{"id": i, "tool": a.tool, "arguments": a.arguments(), "reason": a.reason, "proposed_in": step_id}
                   for i, (step_id, a) in enumerate(pending)]
        value = interrupt({"type": "approval", "actions": request,
                           "how_to_answer": "'approve' or 'reject' for all, or {'decisions': [{'id': 0, "
                                            "'decision': 'approve'|'reject'|'edit', 'arguments': {...}}]}"})
        if isinstance(value, dict) and "decisions" in value:
            value = value["decisions"]
        per_id: dict[int, dict] = {}
        if isinstance(value, list):
            for i, item in enumerate(value):
                item = item if isinstance(item, dict) else {"id": i, "decision": item}
                per_id[int(item.get("id", i))] = item
        elif isinstance(value, dict):
            per_id = {int(k): (v if isinstance(v, dict) else {"decision": v}) for k, v in value.items()}
        decided = []
        for i, (_, action) in enumerate(pending):
            item = per_id.get(i, {"decision": value if isinstance(value, str | bool) else "reject"})
            arguments = {**action.arguments(), **(item.get("arguments") or {})}
            decided.append({"signature": action.signature(), "tool": action.tool, "arguments": arguments,
                            "reason": action.reason, "decision": _decision(item.get("decision", "reject"))})
        return {"decided_actions": decided}

    async def execute_actions(self, state: CoordinatorState) -> dict:
        """Call the MCP write tools for approved actions; record outcomes as evidence for the answer."""
        executed = set(state.get("executed_actions", []))
        evidence, findings, now_done = [], [], []
        started = time.time()
        for action in state.get("decided_actions", []):
            if action["signature"] in executed:
                continue
            now_done.append(action["signature"])
            if action["decision"] != "approved":
                findings.append(f"Rejected by the user: {action['tool']} {json.dumps(action['arguments'])}")
                continue
            tool = self.crm.ticket_write.get(action["tool"])
            if tool is None:
                findings.append(f"Could not run {action['tool']}: CRM write tool unavailable")
                continue
            output = tool_text(await tool.ainvoke(action["arguments"]))
            ticket = re.search(r"TKT-\d{6}", output)
            evidence.append(Evidence(kind="action", ref=ticket.group(0) if ticket else action["tool"],
                                     title=action["tool"], quote=output[:600]))
            findings.append(f"Executed {action['tool']}: {output[:300]}")
        report = AgentReport(findings="\n".join(findings) or "No ticket actions.", evidence=evidence, confidence=1.0,
                             agent="coordinator", step_id=f"actions-{len(executed) + 1}",
                             goal="Execute approved ticket actions", started_at=started, finished_at=time.time())
        return {"reports": [report.model_dump()], "executed_actions": now_done}

    async def synthesize(self, state: CoordinatorState) -> dict:
        """Write the final answer from the reports and numbered evidence (high reasoning effort)."""
        actions = "\n".join(f"- {a['decision'].upper()}: {a['tool']} {json.dumps(a['arguments'])}"
                            for a in state.get("decided_actions", [])) or "(none)"
        feedback = ""
        if state.get("judge_feedback"):
            feedback = (f"\n## Quality review of your previous answer (fix these issues)\n{state['judge_feedback']}\n"
                        f"Previous answer:\n{state.get('draft_answer', '')}")
        human = prompts.SYNTH_HUMAN.format(question=state["question"], conversation=state.get("history", ""),
                                           memories=self.memories_text(state),
                                           clarifications=self.clarifications_text(state),
                                           reports=self.reports_digest(state), evidence=self.evidence_text(state),
                                           actions=actions, feedback=feedback,
                                           unavailable="\n".join(f"- {m.spec.title}: {m.reason}"
                                                                 for m in self.team.values() if not m.available)
                                           or "(none)")
        reply = await self.writer.ainvoke([("system", prompts.SYNTH_SYSTEM), ("human", human)])
        return {"draft_answer": message_text(reply).strip()}

    async def judge(self, state: CoordinatorState) -> dict:
        """Score the draft with the judge model; on failure keep the critique for the retry."""
        question = state["question"]
        if state.get("clarifications"):
            question += "\n(Clarifications: " + "; ".join(c["answer"] for c in state["clarifications"]) + ")"
        verdict = await ajudge_answer(self.settings, question, state["draft_answer"], self.evidence_text(state),
                                      agents=self.available())
        attempt = {"attempt": len(state.get("attempts", [])) + 1, "answer": state["draft_answer"],
                   "overall": verdict.overall, "passed": verdict.passed, "scores": verdict.scores.model_dump(),
                   "summary": verdict.summary(), "agent_calls": state.get("agent_calls", 0)}
        update: dict[str, Any] = {"attempts": [attempt]}
        if not verdict.passed:
            update["judge_feedback"] = (f"Score {verdict.overall}/100 (pass mark {verdict.threshold}). "
                                        f"{verdict.scores.critique} Targets: {verdict.scores.targets}")
            update["replans"] = 0
            update["reflection"] = {}
        return update

    async def finalize(self, state: CoordinatorState) -> dict:
        """Pick the passing (or best) attempt, flag low confidence, and add the answer to the conversation."""
        attempts = state.get("attempts", [])
        best = next((a for a in attempts if a["passed"]), None) or max(attempts, key=lambda a: a["overall"])
        answer = best["answer"]
        low_confidence = not best["passed"]
        if low_confidence:
            answer = (f"**Low confidence:** this answer did not pass the quality review after {len(attempts)} "
                      f"attempt(s) (best score {best['overall']}/100, pass mark {self.settings.judge_pass_score}). "
                      f"Please verify the details.\n\n{answer}")
        evidence = [{"id": eid, "agent": r.agent, **e.model_dump()} for eid, r, e in self.evidence_index(state)]
        final = {"answer": answer, "score": best["overall"], "passed": best["passed"],
                 "low_confidence": low_confidence, "attempts": len(attempts), "best_attempt": best["attempt"],
                 "agent_calls": state.get("agent_calls", 0), "evidence": evidence}
        return {"final": final, "messages": [AIMessage(answer)]}

    async def save_memory(self, state: CoordinatorState, *, store: BaseStore) -> dict:
        """Extract durable user facts from this exchange and save them to the long-term store."""
        prompt = prompts.MEMORY_PROMPT.format(known=state.get("memories", []), question=state["question"],
                                              clarifications=self.clarifications_text(state),
                                              answer=state["final"]["answer"][:3000])
        facts: UserFacts = await self.fact_extractor.ainvoke(prompt)
        await remember_facts(store, state["user_id"], facts.facts)
        return {}

    # ------------------------------------------------------------------ routing
    def route_after_plan(self, state: CoordinatorState) -> str | list[Send]:
        """Clarify, dispatch ready steps in parallel, or go straight to answering."""
        if state.get("clarifying_question"):
            return "clarify"
        return self.sends(state) or self.to_answer(state)

    def route_after_reflect(self, state: CoordinatorState) -> str | list[Send]:
        """Dispatch the next ready steps, replan, or move on to approval/synthesis."""
        decision = state.get("reflection", {}).get("decision")
        if decision == "continue":
            return self.sends(state) or self.to_answer(state)
        if decision == "replan":
            return "plan"
        return self.to_answer(state)

    def route_after_judge(self, state: CoordinatorState) -> str:
        """Retry from planning while below the pass mark and retries remain; otherwise finalize."""
        attempts = state.get("attempts", [])
        if attempts and not attempts[-1]["passed"] and len(attempts) <= self.settings.judge_max_retries:
            return "plan"
        return "finalize"
