from unittest.mock import MagicMock

from crypto_farmer.scheduler import CycleScheduler


def test_scheduler_starts_and_runs_job():
    job_fn = MagicMock()
    sched = CycleScheduler(
        interval_minutes=15, timezone="UTC", cycle_callable=job_fn,
        outcomes_callable=MagicMock(),
    )
    sched.start()
    assert sched.is_running()
    jobs = sched._scheduler.get_jobs()
    assert any("cycle" in j.id for j in jobs)
    sched.stop()


def test_scheduler_pause_and_resume():
    sched = CycleScheduler(
        interval_minutes=15, timezone="UTC",
        cycle_callable=lambda: None, outcomes_callable=lambda: None,
    )
    sched.start()
    sched.pause()
    assert sched.is_paused()
    sched.resume()
    assert not sched.is_paused()
    sched.stop()


def test_scheduler_max_instances_is_one():
    sched = CycleScheduler(
        interval_minutes=15, timezone="UTC",
        cycle_callable=lambda: None, outcomes_callable=lambda: None,
    )
    sched.start()
    cycle_job = next(j for j in sched._scheduler.get_jobs() if j.id == "cycle")
    assert cycle_job.max_instances == 1
    assert cycle_job.coalesce is True
    sched.stop()
