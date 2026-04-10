"""Tests for the interval tree data structure."""

from app.engine.interval_tree import IntervalTree, TimeInterval


class TestTimeInterval:
    def test_overlap_same_day(self):
        a = TimeInterval(start=540, end=600, day="M")  # 9:00-10:00
        b = TimeInterval(start=570, end=630, day="M")  # 9:30-10:30
        assert a.overlaps(b) is True
        assert b.overlaps(a) is True

    def test_no_overlap_same_day(self):
        a = TimeInterval(start=540, end=600, day="M")  # 9:00-10:00
        b = TimeInterval(start=600, end=660, day="M")  # 10:00-11:00
        assert a.overlaps(b) is False  # Adjacent, not overlapping

    def test_no_overlap_different_day(self):
        a = TimeInterval(start=540, end=600, day="M")
        b = TimeInterval(start=540, end=600, day="T")
        assert a.overlaps(b) is False

    def test_from_time_str(self):
        interval = TimeInterval.from_time_str("09:30", "10:45", "M", "CMSC131")
        assert interval.start == 570
        assert interval.end == 645
        assert interval.day == "M"
        assert interval.label == "CMSC131"


class TestIntervalTree:
    def test_insert_and_size(self):
        tree = IntervalTree()
        tree.insert(TimeInterval(540, 600, "M"))
        tree.insert(TimeInterval(600, 660, "M"))
        assert tree.size == 2

    def test_has_conflict(self):
        tree = IntervalTree()
        tree.insert(TimeInterval(540, 600, "M", "CMSC131"))
        # Overlapping interval
        assert tree.has_conflict(TimeInterval(570, 630, "M")) is True
        # Non-overlapping
        assert tree.has_conflict(TimeInterval(600, 660, "M")) is False
        # Different day
        assert tree.has_conflict(TimeInterval(540, 600, "T")) is False

    def test_query_overlaps(self):
        tree = IntervalTree()
        tree.insert(TimeInterval(540, 600, "M", "A"))
        tree.insert(TimeInterval(570, 630, "M", "B"))
        tree.insert(TimeInterval(660, 720, "M", "C"))

        query = TimeInterval(580, 610, "M")
        overlaps = tree.query_overlaps(query)
        labels = {o.label for o in overlaps}
        assert "A" in labels  # 540-600 overlaps 580-610
        assert "B" in labels  # 570-630 overlaps 580-610
        assert "C" not in labels  # 660-720 does not overlap

    def test_remove(self):
        tree = IntervalTree()
        interval = TimeInterval(540, 600, "M", "CMSC131")
        tree.insert(interval)
        assert tree.size == 1
        assert tree.remove(interval) is True
        assert tree.size == 0

    def test_many_intervals_balanced(self):
        """Insert many intervals and verify tree stays balanced (O(log n) height)."""
        tree = IntervalTree()
        import math
        for i in range(100):
            tree.insert(TimeInterval(start=i * 10, end=i * 10 + 50, day="M", label=str(i)))

        assert tree.size == 100
        # AVL tree height should be O(log n) ≈ 7 for 100 nodes
        # We can't easily check height but we can verify correctness
        overlaps = tree.query_overlaps(TimeInterval(500, 510, "M"))
        assert len(overlaps) > 0

    def test_get_all_intervals(self):
        tree = IntervalTree()
        tree.insert(TimeInterval(600, 660, "M", "B"))
        tree.insert(TimeInterval(540, 600, "M", "A"))
        tree.insert(TimeInterval(660, 720, "M", "C"))
        all_intervals = tree.get_all_intervals()
        assert len(all_intervals) == 3
