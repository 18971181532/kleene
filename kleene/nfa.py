"""NFA state model, graph export and layered layout for visualization."""

from collections import deque


class State:
    __slots__ = ("id", "edges", "ops", "accept", "note")

    def __init__(self, sid: int):
        self.id = sid
        self.edges = []      # list of (label, target_id); label None == epsilon
        self.ops = []        # list of ("save", slot) or ("assert", kind)
        self.accept = False
        self.note = ""       # human hint for rendering

    def add_epsilon(self, target: int):
        self.edges.append((None, target))

    def add_char(self, charset, target: int):
        self.edges.append((charset, target))

    def to_dict(self):
        return {
            "id": self.id,
            "accept": self.accept,
            "ops": self.ops,
            "note": self.note,
            "edges": [
                {"label": lbl.describe() if lbl is not None else None,
                 "target": tgt}
                for lbl, tgt in self.edges
            ],
        }


class NFA:
    def __init__(self):
        self.states = []
        self.start = 0

    def new_state(self, note=""):
        sid = len(self.states)
        st = State(sid)
        st.note = note
        self.states.append(st)
        return sid

    def __len__(self):
        return len(self.states)

    def edges(self):
        for st in self.states:
            for lbl, tgt in st.edges:
                yield st.id, lbl, tgt

    # -------------------------------------------------- graph export ----
    def to_graph(self):
        nodes = []
        edges = []
        for st in self.states:
            nodes.append({
                "id": st.id,
                "x": 0, "y": 0,
                "accept": st.accept,
                "start": st.id == self.start,
                "ops": [{"op": op, "value": val} for op, val in st.ops],
                "note": st.note,
            })
            for lbl, tgt in st.edges:
                edges.append({
                    "from": st.id,
                    "to": tgt,
                    "label": lbl.describe() if lbl is not None else "eps",
                    "epsilon": lbl is None,
                })
        layout_nodes(nodes, edges)
        return {"nodes": nodes, "edges": edges, "start": self.start}


def layout_nodes(nodes, edges):
    """Assign x/y by BFS depth (column) and a stable per-column row."""
    id2node = {n["id"]: n for n in nodes}
    adj = {n["id"]: [] for n in nodes}
    for e in edges:
        if e["to"] in adj:
            adj[e["from"]].append(e["to"])
    depth = {n["id"]: None for n in nodes}
    start_ids = [n["id"] for n in nodes if n.get("start")]
    root = start_ids[0] if start_ids else nodes[0]["id"]
    depth[root] = 0
    q = deque([root])
    while q:
        cur = q.popleft()
        for tgt in adj[cur]:
            if depth[tgt] is None:
                depth[tgt] = depth[cur] + 1
                q.append(tgt)
    # states not reachable via forward edges (loops) -> stack at end
    fallback = (max(d for d in depth.values() if d is not None) + 1
                if any(d is not None for d in depth.values()) else 0)
    for sid, d in depth.items():
        if d is None:
            depth[sid] = fallback
    columns = {}
    for n in nodes:
        columns.setdefault(depth[n["id"]], []).append(n["id"])
    col_gap = 150
    row_gap = 78
    for col, ids in columns.items():
        for row, sid in enumerate(ids):
            id2node[sid]["x"] = col * col_gap
            id2node[sid]["y"] = row * row_gap
    # report extents
    widths = {c: len(ids) for c, ids in columns.items()}
    return {"cols": len(columns), "max_rows": max(widths.values()) if widths else 0}
