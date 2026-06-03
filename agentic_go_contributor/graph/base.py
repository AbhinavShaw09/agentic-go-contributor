from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agentic_go_contributor.graph.state import AgentState


@runtime_checkable
class GraphNode(Protocol):
    def __call__(self, state: AgentState) -> dict[str, Any]: ...
