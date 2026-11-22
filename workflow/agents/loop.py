"""The agent loop: model -> tool -> model -> tool ... until the model stops.

Small on purpose (ADR-005, ADR-009):
  * old tool results are dropped from the conversation, so the prompt stays
    inside the free-tier token limits,
  * the loop stops on a step limit, a spent budget or a provider failure,
    and reports why instead of raising,
  * issue text is never given a role that can change the task: callers pass it
    inside the user message, marked as untrusted data (see prompts).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from llm import BudgetExceeded, LLMClient, LLMError, PromptTooLarge
from tools import ToolSet

KEEP_RECENT_TOOL_RESULTS = 4
DROPPED = "[old tool output dropped to save space]"


@dataclass
class AgentResult:
    final_text: str = ""
    steps: int = 0
    stopped: str = "finished"  # finished | max_steps | budget | prompt_too_large | error
    error: str = ""
    transcript: List[Dict[str, Any]] = field(default_factory=list)  # tool names only, no contents

    @property
    def ok(self) -> bool:
        return self.stopped == "finished"


def _trim(messages: List[Dict[str, Any]]) -> None:
    """Replace the content of all but the most recent tool results."""
    tool_idx = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    for i in tool_idx[:-KEEP_RECENT_TOOL_RESULTS]:
        messages[i]["content"] = DROPPED


def run_agent(
    client: LLMClient,
    system_prompt: str,
    task: str,
    tools: ToolSet,
    max_steps: int = 20,
) -> AgentResult:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    result = AgentResult()
    schemas = tools.schemas()

    for _ in range(max_steps):
        _trim(messages)
        try:
            reply = client.chat(messages, tools=schemas)
        except BudgetExceeded as exc:
            result.stopped, result.error = "budget", str(exc)
            return result
        except PromptTooLarge as exc:
            result.stopped, result.error = "prompt_too_large", str(exc)
            return result
        except LLMError as exc:
            result.stopped, result.error = "error", str(exc)
            return result

        result.steps += 1
        message = reply["message"]
        calls = message.get("tool_calls") or []
        assistant: Dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
        if calls:
            assistant["tool_calls"] = calls
        messages.append(assistant)

        if not calls:
            result.final_text = message.get("content") or ""
            return result

        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            output = tools.call(name, fn.get("arguments", "{}"))
            result.transcript.append({"step": result.steps, "tool": name, "failed": output.startswith("error:")})
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": output})

    result.stopped, result.error = "max_steps", f"no final answer after {max_steps} steps"
    return result


def transcript_summary(result: AgentResult) -> str:
    """Short, content-free summary for logs and artifacts."""
    return json.dumps(
        {"stopped": result.stopped, "steps": result.steps, "tools_used": [t["tool"] for t in result.transcript]}
    )
