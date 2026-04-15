"""
Parse prerequisite expressions from UMD API into PrereqNode trees.

UMD API prerequisite format (from umd.io):
  - Top level is typically a dict with keys: "and", "or", "coreq", or course refs
  - Nested structure: {"and": [{"course": "CMSC131"}, {"or": [...]}]}
  - Can be null/empty for no prerequisites

PrereqNode format (target):
  - type: PrereqType (ALL, ANY, COREQ)
  - courses: list of course IDs (e.g., ["CMSC131", "MATH140"])
  - children: list of nested PrereqNode objects
"""

from __future__ import annotations

from typing import Any

from app.engine.course_graph import PrereqNode, PrereqType


def parse_prerequisite_expression(expr: dict | str | list | None) -> PrereqNode | None:
    """
    Parse a UMD API prerequisite expression into a PrereqNode tree.

    Args:
        expr: Raw prerequisite expression from umd.io API. Can be:
              - None: No prerequisites
              - dict: Complex expression with "and", "or", "coreq" keys
              - str: Simple course ID (e.g., "CMSC131")
              - list: List of prerequisites

    Returns:
        PrereqNode tree, or None if no prerequisites.

    Examples:
        >>> parse_prerequisite_expression(None)
        None

        >>> parse_prerequisite_expression("CMSC131")
        PrereqNode(type=ALL, courses=["CMSC131"], children=[])

        >>> parse_prerequisite_expression({"and": [{"course": "CMSC131"}, {"course": "MATH140"}]})
        PrereqNode(type=ALL, courses=["CMSC131", "MATH140"], children=[])

        >>> parse_prerequisite_expression({"or": [{"course": "CMSC131"}, {"course": "CMSC160"}]})
        PrereqNode(type=ANY, courses=["CMSC131", "CMSC160"], children=[])

        >>> parse_prerequisite_expression({"and": [{"course": "CMSC131"}, {"or": [...]}]})
        # Returns nested structure with children
    """
    # Handle null/empty
    if expr is None or expr == {} or expr == []:
        return None

    # Handle simple string course ID
    if isinstance(expr, str):
        course_id = expr.strip().upper()
        if course_id:
            return PrereqNode(type=PrereqType.ALL, courses=[course_id])
        return None

    # Handle list of prerequisites (usually AND logic)
    if isinstance(expr, list):
        if not expr:
            return None
        # Parse each item and collect courses and children
        courses = []
        children = []
        for item in expr:
            parsed = _parse_item(item)
            if parsed:
                if isinstance(parsed, tuple):  # (courses_list, children_list)
                    courses.extend(parsed[0])
                    children.extend(parsed[1])
                else:  # PrereqNode
                    children.append(parsed)
        if courses or children:
            return PrereqNode(type=PrereqType.ALL, courses=courses, children=children)
        return None

    # Handle dict expressions
    if isinstance(expr, dict):
        if not expr:
            return None
        return _parse_dict(expr)

    # Unknown format
    return None


def _parse_dict(expr: dict) -> PrereqNode | None:
    """Parse a dict-based prerequisite expression."""
    # Check for explicit logic operators
    if "and" in expr:
        return _parse_logic_group(expr["and"], PrereqType.ALL)

    if "or" in expr:
        return _parse_logic_group(expr["or"], PrereqType.ANY)

    if "coreq" in expr:
        return _parse_logic_group(expr["coreq"], PrereqType.COREQ)

    # Check for single course reference
    if "course" in expr:
        course_id = expr["course"]
        if isinstance(course_id, str):
            course_id = course_id.strip().upper()
            if course_id:
                return PrereqNode(type=PrereqType.ALL, courses=[course_id])

    # Check for other common keys that might indicate course info
    if "name" in expr and "course_id" not in expr:
        # This might be a course info dict with a "course" field we missed
        pass

    # If the dict has multiple keys, treat them as separate requirements (AND)
    # This handles cases like {"course": "CMSC131", "coreq": [...]} (rare)
    all_courses = []
    all_children = []

    for key, value in expr.items():
        if key in ("and", "or", "coreq", "course"):
            continue

        # Try to parse as a course reference
        if isinstance(value, str):
            parsed_course = value.strip().upper()
            if parsed_course and len(parsed_course) > 0:
                all_courses.append(parsed_course)

    if all_courses:
        return PrereqNode(type=PrereqType.ALL, courses=all_courses)

    return None


def _parse_logic_group(
    group: list | dict | str | None, logic_type: PrereqType
) -> PrereqNode | None:
    """Parse a group of prerequisites under a single logical operator (AND/OR/COREQ)."""
    if not group:
        return None

    courses = []
    children = []

    # Handle list of items
    if isinstance(group, list):
        for item in group:
            parsed = _parse_item(item)
            if parsed:
                if isinstance(parsed, tuple):  # (courses_list, children_list)
                    courses.extend(parsed[0])
                    children.extend(parsed[1])
                else:  # PrereqNode
                    children.append(parsed)

    # Handle single item
    else:
        parsed = _parse_item(group)
        if parsed:
            if isinstance(parsed, tuple):
                courses.extend(parsed[0])
                children.extend(parsed[1])
            else:
                children.append(parsed)

    # Create the node if we found anything
    if courses or children:
        return PrereqNode(type=logic_type, courses=courses, children=children)

    return None


def _parse_item(item: Any) -> PrereqNode | tuple[list[str], list[PrereqNode]] | None:
    """
    Parse a single prerequisite item.

    Returns:
        - PrereqNode: For complex nested structures
        - tuple: (courses_list, children_list) for simple course lists
        - None: If nothing parsed
    """
    if item is None:
        return None

    # Simple string course ID
    if isinstance(item, str):
        course_id = item.strip().upper()
        if course_id:
            return (
                [course_id],
                [],
            )  # Return as tuple so caller can extend lists
        return None

    # Dict item
    if isinstance(item, dict):
        # Check for "course" key with course ID
        if "course" in item:
            course_value = item["course"]
            if isinstance(course_value, str):
                course_id = course_value.strip().upper()
                if course_id:
                    return ([course_id], [])
            elif isinstance(course_value, dict):
                # Sometimes it might be nested
                nested = _parse_item(course_value)
                if nested:
                    return nested

        # Check for nested logic operators
        if "and" in item:
            node = _parse_logic_group(item["and"], PrereqType.ALL)
            return node if node else None

        if "or" in item:
            node = _parse_logic_group(item["or"], PrereqType.ANY)
            return node if node else None

        if "coreq" in item:
            node = _parse_logic_group(item["coreq"], PrereqType.COREQ)
            return node if node else None

    # List item (rare, but possible)
    if isinstance(item, list):
        # Parse list as AND group
        node = _parse_logic_group(item, PrereqType.ALL)
        return node if node else None

    return None
