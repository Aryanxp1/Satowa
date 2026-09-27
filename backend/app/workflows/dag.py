"""Directed Acyclic Graph (DAG) representation, cycle detection, and topological sorting for SETOWA workflows."""
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple
from app.workflows.models import WorkflowDefinition


class CycleError(Exception):
    """Raised when a circular dependency is detected in the workflow DAG."""
    def __init__(self, message: str, cycle_nodes: Optional[List[str]] = None):
        super().__init__(message)
        self.cycle_nodes = cycle_nodes or []


class DAGGraph:
    """Represents a directed graph of workflow nodes and dependencies."""

    def __init__(self, node_ids: Optional[List[str]] = None):
        self.nodes: Set[str] = set(node_ids or [])
        # source -> set of target nodes
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
        # target -> set of source nodes
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)

    @classmethod
    def from_workflow(cls, workflow: WorkflowDefinition) -> "DAGGraph":
        """Build a DAG from a WorkflowDefinition, extracting dependencies from both explicit edges
        and implicit $node.<source_node>.<output> input expressions.
        """
        graph = cls([node.id for node in workflow.nodes])

        # 1. Add explicit edges
        for edge in workflow.edges:
            if edge.source_node in graph.nodes and edge.target_node in graph.nodes:
                graph.add_edge(edge.source_node, edge.target_node)

        # 2. Add implicit edges from input references like $node.before_meta.secure_url
        for node in workflow.nodes:
            for val in node.inputs.values():
                if isinstance(val, str) and val.startswith("$node."):
                    parts = val[6:].split(".")
                    if len(parts) >= 2:
                        src_id = parts[0]
                        if src_id in graph.nodes:
                            graph.add_edge(src_id, node.id)

        return graph

    def add_edge(self, source: str, target: str) -> None:
        """Add a directed edge from source node to target node."""
        self.nodes.add(source)
        self.nodes.add(target)
        self.adjacency[source].add(target)
        self.dependencies[target].add(source)

    def has_self_loop(self) -> Tuple[bool, Optional[str]]:
        """Check for direct self-loops (node depending on itself)."""
        for node in self.nodes:
            if node in self.adjacency[node]:
                return True, node
        return False, None

    def find_cycle(self) -> Optional[List[str]]:
        """Detect circular dependencies using DFS graph coloring.
        Returns a list of node IDs forming a cycle if found, or None if acyclic.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self.nodes}
        parent = {}
        cycle = []

        def dfs(u: str) -> bool:
            color[u] = GRAY
            # Sort neighbors for deterministic cycle traversal
            for v in sorted(self.adjacency[u]):
                if color[v] == GRAY:
                    # Cycle found! Reconstruct cycle path
                    cur = u
                    cycle.append(v)
                    while cur != v and cur in parent:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(v)
                    cycle.reverse()
                    return True
                if color[v] == WHITE:
                    parent[v] = u
                    if dfs(v):
                        return True
            color[u] = BLACK
            return False

        for node in sorted(self.nodes):
            if color[node] == WHITE:
                if dfs(node):
                    return cycle
        return None

    def topological_sort(self) -> List[str]:
        """Compute the deterministic topological execution order using Kahn's algorithm.
        Raises CycleError if graph has a cycle.
        """
        # Self-loop check
        has_loop, loop_node = self.has_self_loop()
        if has_loop:
            raise CycleError(f"Self-loop detected: node '{loop_node}' depends on itself.", [loop_node, loop_node])

        # Cycle check
        cycle = self.find_cycle()
        if cycle:
            cycle_str = " -> ".join(cycle)
            raise CycleError(f"Circular dependency detected: {cycle_str}", cycle)

        in_degree = {node: len(self.dependencies[node]) for node in self.nodes}
        # Use sorted deque for deterministic execution ordering
        queue = deque(sorted([node for node in self.nodes if in_degree[node] == 0]))
        order = []

        while queue:
            u = queue.popleft()
            order.append(u)
            for v in sorted(self.adjacency[u]):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        if len(order) != len(self.nodes):
            unresolved = sorted(list(self.nodes - set(order)))
            raise CycleError(f"Unresolvable cycle among nodes: {unresolved}", unresolved)

        return order

    def get_upstream_dependencies(self, node_id: str) -> Set[str]:
        """Get immediate upstream dependencies for a node."""
        return set(self.dependencies.get(node_id, set()))

    def get_all_upstream(self, node_id: str) -> Set[str]:
        """Get all transitive upstream dependencies for a node."""
        all_upstream = set()
        queue = deque(self.dependencies.get(node_id, set()))
        while queue:
            curr = queue.popleft()
            if curr not in all_upstream:
                all_upstream.add(curr)
                queue.extend(self.dependencies.get(curr, set()))
        return all_upstream
