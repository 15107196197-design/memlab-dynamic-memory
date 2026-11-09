"""S2 max_neighbors is a real expansion cap, not an accepted-but-unread parameter."""
import unittest

from memlab.store import GraphIndex


class GraphMaxNeighborsTests(unittest.TestCase):
    def _graph(self, degree=20):
        graph = GraphIndex("test")
        graph.add_node("seed")
        for index in range(degree):
            graph.link("seed", f"n{index:02d}")
        return graph

    def test_default_preserves_all_neighbors(self):
        graph = self._graph(20)
        expanded = graph.expand(["seed"], 1)
        self.assertEqual(len(expanded), 21)  # seed + 20 neighbours

    def test_cap_limits_each_frontier_node(self):
        graph = self._graph(20)
        expanded = graph.expand(["seed"], 1, max_neighbors=5)
        self.assertEqual(len(expanded), 6)  # seed + first five sorted neighbours
        self.assertEqual([node for node, _ in expanded[1:]], [f"n{i:02d}" for i in range(5)])

    def test_cap_applies_at_each_hop(self):
        graph = self._graph(20)
        # second hop from n00..n04 has no further edges, so the cap must not add nodes
        expanded = graph.expand(["seed"], 2, max_neighbors=5)
        self.assertEqual(len(expanded), 6)


if __name__ == "__main__":
    unittest.main()
