"""Architecture Freeze guards (ADR-0007).

These tests enforce the v1 architecture freeze by detecting duplicate
abstractions and unapproved top-level packages. If any of these tests fail,
it means someone has introduced a new core abstraction that violates the
freeze. See ADR-0007 for the full rules.

Run: pytest apps/api/prachar_api/tests/test_architecture_freeze.py -v
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ─── Paths ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
API_DIR = REPO_ROOT / "apps" / "api" / "prachar_api"
SHARED_DIR = REPO_ROOT / "packages" / "shared" / "prachar_shared"


# ─── 1. No duplicate Runtime / Planner / Composer ───────────────────────────


class TestNoDuplicateRuntime:
    """There must be exactly one Runtime, Planner, and Composer.

    ADR-0001 declares the Runtime architecture frozen. No second runtime,
    planner, or composer may be introduced.
    """

    FORBIDDEN_PATTERNS = [
        "class.*Runtime.*:",
        "class.*Planner.*:",
        "class.*Composer.*:",
    ]

    ALLOWED_FILES = {
        "runtime/runtime.py",
        "runtime/planner.py",
        "runtime/composer.py",
        "runtime/__init__.py",
    }

    def test_no_duplicate_runtime_classes(self) -> None:
        """No file outside the runtime package may define a Runtime/Planner/Composer class."""
        import re

        violations: list[str] = []
        for py_file in API_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(API_DIR)
            if str(rel) in self.ALLOWED_FILES:
                continue
            if rel.parts[0] == "tests":
                continue
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for pattern in self.FORBIDDEN_PATTERNS:
                        if re.match(pattern, node.name):
                            violations.append(f"{rel}: class {node.name}")
        assert not violations, (
            f"Duplicate Runtime/Planner/Composer classes found (ADR-0001 violation):\n"
            f"{chr(10).join(violations)}\n"
            f"These must only exist in the runtime/ package."
        )


# ─── 2. No duplicate Tool Registry ──────────────────────────────────────────


class TestNoDuplicateToolRegistry:
    """There must be exactly one Tool Registry.

    ADR-0002 declares the Tool Registry frozen. No second registry may be
    introduced.
    """

    def test_no_duplicate_tool_registry(self) -> None:
        violations: list[str] = []
        for py_file in API_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(API_DIR)
            if rel.parts[0] == "tests":
                continue
            if rel.name in ("tools.py", "tools_phase2.py", "tool_registry.py", "registry.py"):
                continue
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and "ToolRegistry" in node.name:
                    violations.append(f"{rel}: class {node.name}")
        assert not violations, (
            f"Duplicate ToolRegistry class found (ADR-0002 violation):\n"
            f"{chr(10).join(violations)}"
        )


# ─── 3. No duplicate Context Builder ────────────────────────────────────────


class TestNoDuplicateContextBuilder:
    """There must be exactly one Context Builder.

    ADR-0003 declares the Context Builder frozen. No second context-loading
    mechanism may be introduced.
    """

    def test_no_duplicate_context_builder(self) -> None:
        violations: list[str] = []
        for py_file in API_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(API_DIR)
            if rel.parts[0] == "tests":
                continue
            if rel.name in ("context_builder.py",):
                continue
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and "ContextBuilder" in node.name:
                    violations.append(f"{rel}: class {node.name}")
        assert not violations, (
            f"Duplicate ContextBuilder class found (ADR-0003 violation):\n"
            f"{chr(10).join(violations)}"
        )


# ─── 4. No duplicate Event Bus ──────────────────────────────────────────────


class TestNoDuplicateEventBus:
    """There must be exactly one Event Bus.

    ADR-0006 declares the Event Bus frozen. No second event bus may be
    introduced.
    """

    ALLOWED_FILES = {"runtime/event_bus.py", "runtime/events.py"}

    def test_no_duplicate_event_bus(self) -> None:
        violations: list[str] = []
        for py_file in API_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(API_DIR)
            if rel.parts[0] == "tests":
                continue
            if str(rel) in self.ALLOWED_FILES:
                continue
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and "EventBus" in node.name:
                    violations.append(f"{rel}: class {node.name}")
        assert not violations, (
            f"Duplicate EventBus class found (ADR-0006 violation):\n"
            f"{chr(10).join(violations)}"
        )


# ─── 5. No shared → api imports ─────────────────────────────────────────────


class TestNoSharedToApiImports:
    """The shared package must never import from the API app.

    This is a pre-existing invariant from the Architecture Stabilisation Sprint.
    Repeated here for the freeze guard suite.
    """

    def test_no_prachar_api_imports_in_shared(self) -> None:
        # Pre-existing violations that pre-date the freeze (grandfathered)
        GRANDFATHERED_VIOLATIONS = {
            "packages/shared/prachar_shared/marketing_intelligence/proactive_engine.py",
            "packages/shared/prachar_shared/marketing_intelligence/brain.py",
            "packages/shared/prachar_shared/marketing_intelligence/performance_engine.py",
            "packages/shared/prachar_shared/tests/test_knowledge_hub.py",
            "packages/shared/prachar_shared/domain_packs/tests/test_architecture.py",
        }

        violations: list[str] = []
        for py_file in SHARED_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel_path = str(py_file.relative_to(REPO_ROOT))
            if rel_path in GRANDFATHERED_VIOLATIONS:
                continue
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "prachar_api" in node.module:
                    violations.append(f"{rel_path}: from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "prachar_api" in alias.name:
                            violations.append(f"{rel_path}: import {alias.name}")
        assert not violations, (
            f"shared package imports from API app (dependency inversion violation):\n"
            f"{chr(10).join(violations)}"
        )


# ─── 6. No new top-level packages without approval ──────────────────────────


class TestNoUnapprovedTopLevelPackages:
    """No new top-level packages may be introduced in the API app.

    The approved top-level packages are listed below. Adding a new one
    requires ADR approval (ADR-0007 §v2 Admission Rule).
    """

    APPROVED_API_PACKAGES = {
        "__pycache__",
        "__init__.py",
        "main.py",
        "db.py",
        "middleware.py",
        "routers",
        "runtime",
        "models",
        "infrastructure",
        "tests",
        "agency_council",
        "config.py",
        "audit.py",
        "deps.py",
        "email_service.py",
        "rate_limit.py",
        "schemas.py",
        "security.py",
    }

    def test_no_new_top_level_packages(self) -> None:
        existing = set()
        for item in API_DIR.iterdir():
            if item.name.startswith("."):
                continue
            existing.add(item.name)

        unapproved = existing - self.APPROVED_API_PACKAGES
        # Filter out __init__.py and .pyc files
        unapproved = {p for p in unapproved if not p.endswith(".pyc") and p != "__init__.py"}

        # Known additions that pre-date the freeze (grandfathered)
        GRANDFATHERED = set()

        unapproved = unapproved - GRANDFATHERED

        assert not unapproved, (
            f"Unapproved top-level packages in API app (ADR-0007 violation):\n"
            f"{chr(10).join(sorted(unapproved))}\n"
            f"Adding a new top-level package requires ADR approval. "
            f"See ADR-0007 §v2 Admission Rule."
        )


# ─── 7. No duplicate Workflow Engine ────────────────────────────────────────


class TestNoDuplicateWorkflowEngine:
    """There must be exactly one Workflow Engine.

    ADR-0006 declares the Workflow Engine frozen.
    """

    ALLOWED_FILES = {"runtime/automation.py", "runtime/workflow.py"}

    def test_no_duplicate_workflow_engine(self) -> None:
        violations: list[str] = []
        for py_file in API_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(API_DIR)
            if rel.parts[0] == "tests":
                continue
            if str(rel) in self.ALLOWED_FILES:
                continue
            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and "WorkflowEngine" in node.name:
                    violations.append(f"{rel}: class {node.name}")
        assert not violations, (
            f"Duplicate WorkflowEngine class found (ADR-0006 violation):\n"
            f"{chr(10).join(violations)}"
        )
