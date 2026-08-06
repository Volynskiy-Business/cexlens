from datetime import datetime

from cexlatency.campaign import CampaignProcessLock, build_schedule
from cexlatency.config import AppConfig, CampaignConfig


def test_schedule_preserves_local_windows_and_utc_metadata():
    config = AppConfig(campaign=CampaignConfig(name="test", timezone="Asia/Jerusalem", duration_days=2, windows_local=["00:00", "12:00"], window_grace_minutes=30))
    rows = build_schedule(config, datetime.fromisoformat("2026-08-06T08:00:00+03:00"))
    assert len(rows) == 4
    assert rows[0] == ("2026-08-05T21:00:00+00:00", "2026-08-06T00:00:00+03:00")
    assert rows[-1] == ("2026-08-07T09:00:00+00:00", "2026-08-07T12:00:00+03:00")


def test_schedule_accepts_explicit_future_local_date():
    from datetime import date
    config=AppConfig(campaign=CampaignConfig(timezone="Asia/Jerusalem",duration_days=1,windows_local=["00:00"]))
    assert build_schedule(config,date(2026,8,7))[0][1] == "2026-08-07T00:00:00+03:00"


def test_daemon_process_lock_rejects_duplicate(tmp_path):
    first=CampaignProcessLock(str(tmp_path/"data.db"),"campaign")
    second=CampaignProcessLock(str(tmp_path/"data.db"),"campaign")
    assert first.acquire()
    try: assert not second.acquire()
    finally: first.release()
    assert second.acquire(); second.release()
