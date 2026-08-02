"""Execution Graph — DAG of tool calls with dependencies.

Constitution Amendment 2: The Planner builds a graph, not a list.
Parallel branches run concurrently. Some work waits. Some needs approval.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """A single tool call in the execution graph."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool: str = ""                       # "campaign_brain.analyse"
    input: dict[str, Any] = field(default_factory=dict)
    deps: list[str] = field(default_factory=list)      # node IDs that must complete first
    parallel_group: str | None = None   # nodes in same group run concurrently
    needs_approval: bool = False         # pause here for human approval
    approval_reason: str | None = None
    timeout_ms: int = 120_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "input": self.input,
            "deps": list(self.deps),
            "parallel_group": self.parallel_group,
            "needs_approval": self.needs_approval,
            "approval_reason": self.approval_reason,
            "timeout_ms": self.timeout_ms,
        }


@dataclass
class GraphEdge:
    """Dependency edge between nodes."""

    from_node: str  # node id
    to_node: str    # node id
    type: str = "dependency"  # "dependency" | "data_flow"


@dataclass
class ExecutionGraph:
    """A DAG of tool calls.

    The Execution Engine:
    1. Topological sorts the graph
    2. Runs nodes with no unmet deps (in parallel if same parallel_group)
    3. When a node completes, checks which dependents can now start
    4. At needs_approval nodes, emits approval.requested and pauses
    5. On approval.granted, resumes execution
    6. On cancel, terminates all running nodes
    """

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> str:
        self.nodes.append(node)
        for dep_id in node.deps:
            self.edges.append(GraphEdge(from_node=dep_id, to_node=node.id))
        return node.id

    def topological_order(self) -> list[list[str]]:
        """Return nodes grouped by execution level (Kahn's algorithm).

        Nodes in the same level can run in parallel.
        """
        # Build adjacency + in-degree
        in_degree: dict[str, int] = {n.id: 0 for n in self.nodes}
        adj: dict[str, list[str]] = {n.id: [] for n in self.nodes}

        for edge in self.edges:
            adj[edge.from_node].append(edge.to_node)
            in_degree[edge.to_node] += 1

        levels: list[list[str]] = []
        current: list[str] = [nid for nid, deg in in_degree.items() if deg == 0]

        while current:
            levels.append(current)
            next_level: list[str] = []
            for nid in current:
                for dependent in adj[nid]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_level.append(dependent)
            current = next_level

        return levels

    def get_node(self, node_id: str) -> GraphNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_ready_nodes(self, completed: set[str]) -> list[GraphNode]:
        """Nodes whose deps are all satisfied and haven't run yet."""
        ready: list[GraphNode] = []
        for node in self.nodes:
            if node.id in completed:
                continue
            if all(dep in completed for dep in node.deps):
                ready.append(node)
        return ready

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [
                {"from": e.from_node, "to": e.to_node, "type": e.type}
                for e in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionGraph":
        """Deserialize from dict (e.g. from Planner LLM output)."""
        graph = cls()
        node_map: dict[str, GraphNode] = {}

        for nd in data.get("nodes", []):
            node = GraphNode(
                id=nd.get("id", str(uuid.uuid4())),
                tool=nd.get("tool", ""),
                input=nd.get("input", {}),
                deps=nd.get("deps", []),
                parallel_group=nd.get("parallel_group"),
                needs_approval=nd.get("needs_approval", False),
                approval_reason=nd.get("approval_reason"),
                timeout_ms=nd.get("timeout_ms", 120_000),
            )
            graph.nodes.append(node)
            node_map[node.id] = node

        for nd in graph.nodes:
            for dep_id in nd.deps:
                graph.edges.append(GraphEdge(from_node=dep_id, to_node=nd.id))

        return graph
