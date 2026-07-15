from __future__ import annotations

import pytest

from prachar_workers import loop


@pytest.fixture(autouse=True)
def eager_celery():
    prev = loop.celery_app.conf.task_always_eager
    prev_propagates = loop.celery_app.conf.task_eager_propagates
    loop.celery_app.conf.task_always_eager = True
    loop.celery_app.conf.task_eager_propagates = True
    yield
    loop.celery_app.conf.task_always_eager = prev
    loop.celery_app.conf.task_eager_propagates = prev_propagates


def test_dispatch_due_is_task():
    assert hasattr(loop.dispatch_due, "delay")
    assert loop.dispatch_due.name == "prachar_workers.loop.dispatch_due"


def test_run_weekly_loop_has_seven_steps():
    chain = loop.run_weekly_loop("brand-123")
    tasks = list(chain.tasks)
    assert len(tasks) == 7
    names = [t.name for t in tasks]
    assert names == [
        "prachar_workers.loop.measure",
        "prachar_workers.loop.diagnose",
        "prachar_workers.loop.regenerate",
        "prachar_workers.loop.policy_check",
        "prachar_workers.loop.publish",
        "prachar_workers.loop.budget_realloc",
        "prachar_workers.loop.report",
    ]


def test_each_step_returns_dict_with_stage():
    steps = [
        loop.measure,
        loop.diagnose,
        loop.regenerate,
        loop.policy_check,
        loop.publish,
        loop.budget_realloc,
        loop.report,
    ]
    prev = loop.measure.apply(args=("brand-123",)).get()
    assert isinstance(prev, dict)
    assert "stage" in prev
    for task in steps[1:]:
        res = task.apply(args=(prev,)).get()
        assert isinstance(res, dict)
        assert "stage" in res
        assert res["stage"] == task.name.split(".")[-1]
