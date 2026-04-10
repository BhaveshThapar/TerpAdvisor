"""
Interval tree for O(log n) time conflict detection.

Used by the schedule solver to efficiently detect overlapping class times.
Instead of O(n²) pairwise comparison, an interval tree allows O(log n + k)
queries where k is the number of overlapping intervals.

Implementation: Augmented BST where each node stores the max endpoint in its subtree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimeInterval:
    """A time interval representing a class meeting time.

    Times are stored as minutes from midnight for easy comparison.
    E.g., 9:30 AM = 570, 10:45 AM = 645
    """
    start: int  # minutes from midnight
    end: int    # minutes from midnight
    day: str    # "M", "T", "W", "Th", "F"
    label: str = ""  # e.g., "CMSC131 Section 0101"

    @staticmethod
    def from_time_str(start_str: str, end_str: str, day: str, label: str = "") -> TimeInterval:
        """Create from time strings like '09:30' and '10:45'."""
        def parse(t: str) -> int:
            h, m = t.split(":")
            return int(h) * 60 + int(m)
        return TimeInterval(start=parse(start_str), end=parse(end_str), day=day, label=label)

    def overlaps(self, other: TimeInterval) -> bool:
        """Check if this interval overlaps with another on the same day."""
        if self.day != other.day:
            return False
        return self.start < other.end and other.start < self.end

    def __repr__(self) -> str:
        sh, sm = divmod(self.start, 60)
        eh, em = divmod(self.end, 60)
        return f"{self.day} {sh:02d}:{sm:02d}-{eh:02d}:{em:02d} [{self.label}]"


@dataclass
class _Node:
    """Internal node of the interval tree (augmented BST)."""
    interval: TimeInterval
    max_end: int  # Maximum end value in this subtree
    left: Optional[_Node] = None
    right: Optional[_Node] = None
    height: int = 1  # For AVL balancing


class IntervalTree:
    """Augmented BST interval tree with AVL balancing for O(log n) operations.

    Supports:
    - insert(interval): Add an interval, O(log n)
    - query_overlaps(interval): Find all overlapping intervals, O(log n + k)
    - has_conflict(interval): Check if any overlap exists, O(log n)
    - remove(interval): Remove an interval, O(log n)
    """

    def __init__(self):
        self._root: Optional[_Node] = None
        self._size: int = 0

    @property
    def size(self) -> int:
        return self._size

    def insert(self, interval: TimeInterval) -> None:
        """Insert an interval into the tree."""
        self._root = self._insert(self._root, interval)
        self._size += 1

    def has_conflict(self, interval: TimeInterval) -> bool:
        """Check if any existing interval overlaps with the given one. O(log n)."""
        return self._has_overlap(self._root, interval)

    def query_overlaps(self, interval: TimeInterval) -> list[TimeInterval]:
        """Find all intervals that overlap with the given one. O(log n + k)."""
        results: list[TimeInterval] = []
        self._find_all_overlaps(self._root, interval, results)
        return results

    def get_all_intervals(self) -> list[TimeInterval]:
        """Return all intervals in the tree (in-order traversal)."""
        result: list[TimeInterval] = []
        self._inorder(self._root, result)
        return result

    def remove(self, interval: TimeInterval) -> bool:
        """Remove an interval from the tree. Returns True if found and removed."""
        self._root, removed = self._remove(self._root, interval)
        if removed:
            self._size -= 1
        return removed

    # ──────────────────────────────────────────────
    # Internal BST operations with AVL balancing
    # ──────────────────────────────────────────────

    def _insert(self, node: Optional[_Node], interval: TimeInterval) -> _Node:
        if node is None:
            return _Node(interval=interval, max_end=interval.end)

        if (interval.day, interval.start) <= (node.interval.day, node.interval.start):
            node.left = self._insert(node.left, interval)
        else:
            node.right = self._insert(node.right, interval)

        # Update max_end
        node.max_end = max(node.interval.end, interval.end)
        if node.left:
            node.max_end = max(node.max_end, node.left.max_end)
        if node.right:
            node.max_end = max(node.max_end, node.right.max_end)

        return self._balance(node)

    def _has_overlap(self, node: Optional[_Node], interval: TimeInterval) -> bool:
        if node is None:
            return False

        if node.interval.overlaps(interval):
            return True

        # If left subtree's max_end > interval.start and same day could have overlap,
        # search left first
        if node.left and node.left.max_end > interval.start:
            if self._has_overlap(node.left, interval):
                return True

        return self._has_overlap(node.right, interval)

    def _find_all_overlaps(
        self, node: Optional[_Node], interval: TimeInterval, results: list[TimeInterval]
    ) -> None:
        if node is None:
            return

        if node.interval.overlaps(interval):
            results.append(node.interval)

        if node.left and node.left.max_end > interval.start:
            self._find_all_overlaps(node.left, interval, results)

        self._find_all_overlaps(node.right, interval, results)

    def _remove(self, node: Optional[_Node], interval: TimeInterval) -> tuple[Optional[_Node], bool]:
        if node is None:
            return None, False

        removed = False
        if (interval.day, interval.start, interval.end, interval.label) == (
            node.interval.day, node.interval.start, node.interval.end, node.interval.label
        ):
            removed = True
            if node.left is None:
                return node.right, True
            if node.right is None:
                return node.left, True
            # Find in-order successor
            successor = self._min_node(node.right)
            node.interval = successor.interval
            node.right, _ = self._remove(node.right, successor.interval)
        elif (interval.day, interval.start) <= (node.interval.day, node.interval.start):
            node.left, removed = self._remove(node.left, interval)
        else:
            node.right, removed = self._remove(node.right, interval)

        if removed:
            self._update_max(node)
            node = self._balance(node)

        return node, removed

    def _min_node(self, node: _Node) -> _Node:
        while node.left:
            node = node.left
        return node

    def _inorder(self, node: Optional[_Node], result: list[TimeInterval]) -> None:
        if node is None:
            return
        self._inorder(node.left, result)
        result.append(node.interval)
        self._inorder(node.right, result)

    # ──────────────────────────────────────────────
    # AVL Balancing
    # ──────────────────────────────────────────────

    def _height(self, node: Optional[_Node]) -> int:
        return node.height if node else 0

    def _balance_factor(self, node: _Node) -> int:
        return self._height(node.left) - self._height(node.right)

    def _update_height(self, node: _Node) -> None:
        node.height = 1 + max(self._height(node.left), self._height(node.right))

    def _update_max(self, node: _Node) -> None:
        node.max_end = node.interval.end
        if node.left:
            node.max_end = max(node.max_end, node.left.max_end)
        if node.right:
            node.max_end = max(node.max_end, node.right.max_end)

    def _balance(self, node: _Node) -> _Node:
        self._update_height(node)
        self._update_max(node)
        bf = self._balance_factor(node)

        if bf > 1:
            if self._balance_factor(node.left) < 0:
                node.left = self._rotate_left(node.left)
            return self._rotate_right(node)

        if bf < -1:
            if self._balance_factor(node.right) > 0:
                node.right = self._rotate_right(node.right)
            return self._rotate_left(node)

        return node

    def _rotate_left(self, node: _Node) -> _Node:
        right = node.right
        node.right = right.left
        right.left = node
        self._update_height(node)
        self._update_max(node)
        self._update_height(right)
        self._update_max(right)
        return right

    def _rotate_right(self, node: _Node) -> _Node:
        left = node.left
        node.left = left.right
        left.right = node
        self._update_height(node)
        self._update_max(node)
        self._update_height(left)
        self._update_max(left)
        return left
