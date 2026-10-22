"""하루치 실행의 중복 방지: 다른 실행 중이거나 오늘 이미 성공했으면 건너뛴다."""

from datetime import datetime, timezone

import pytest

from app import run_daily


class FakeRepo:
    def __init__(self, locked=False, done=None):
        self.locked = locked
        self.done = done
        self.runs_started = 0

    def connect(self): return object()
    def try_run_lock(self, conn): return not self.locked
    def succeeded_today(self, conn, today): return self.done
    def active_products(self, conn): return []
    def start_run(self, conn):
        self.runs_started += 1
        return 1
    def finish_run(self, conn, *args): pass
    def daily_comparison(self, conn, on): return []


DONE = {"id": 7, "started_at": datetime(2026, 10, 22, 1, 57, tzinfo=timezone.utc), "succeeded": 41, "total": 41}


@pytest.fixture
def no_danawa(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("건너뛰어야 하는데 다나와에 요청함")
    monkeypatch.setattr(run_daily, "fetch_product_html", fail)
    monkeypatch.setattr(run_daily.notify, "send", lambda text: False)


def use(monkeypatch, repo):
    monkeypatch.setattr(run_daily, "repo", repo)
    return repo


def test_오늘_이미_성공했으면_아무것도_하지_않는다(monkeypatch, no_danawa, capsys):
    repo = use(monkeypatch, FakeRepo(done=DONE))
    assert run_daily.run() == 0
    assert repo.runs_started == 0
    assert "이미 끝났습니다" in capsys.readouterr().out


def test_다른_실행이_진행_중이면_건너뛴다(monkeypatch, no_danawa, capsys):
    repo = use(monkeypatch, FakeRepo(locked=True, done=None))
    assert run_daily.run() == 0
    assert repo.runs_started == 0
    assert "진행 중" in capsys.readouterr().out


def test_force면_오늘_이미_했어도_다시_수집한다(monkeypatch, no_danawa):
    repo = use(monkeypatch, FakeRepo(done=DONE))
    assert run_daily.run(force=True) == 0
    assert repo.runs_started == 1


def test_오늘_기록이_없으면_정상_실행(monkeypatch, no_danawa):
    repo = use(monkeypatch, FakeRepo(done=None))
    assert run_daily.run() == 0
    assert repo.runs_started == 1


def test_force여도_다른_실행_중이면_건너뛴다(monkeypatch, no_danawa):
    repo = use(monkeypatch, FakeRepo(locked=True, done=DONE))
    assert run_daily.run(force=True) == 0
    assert repo.runs_started == 0
