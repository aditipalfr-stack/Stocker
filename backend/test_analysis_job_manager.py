import time
from analysis_job_manager import AnalysisJobManager

def test_job_manager_flow():
    mgr = AnalysisJobManager()
    assert mgr.get_all_jobs() == []
    assert not mgr.is_symbol_running("TCS")

    # Start dummy task
    def dummy_task(progress_cb):
        progress_cb(25, "Step 1")
        time.sleep(0.05)
        progress_cb(75, "Step 2")
        time.sleep(0.05)
        return {"done": True}

    job = mgr.start_job("TCS", "Tata Consultancy Services", dummy_task)
    assert job.symbol == "TCS"
    assert job.status in ("running", "completed")
    assert mgr.is_symbol_running("TCS") or job.status == "completed"

    # Wait for completion
    time.sleep(0.2)
    completed_job = mgr.get_job_by_symbol("TCS")
    assert completed_job is not None
    assert completed_job.status == "completed"
    assert completed_job.progress_pct == 100
    assert not mgr.is_symbol_running("TCS")
    print("✓ AnalysisJobManager lifecycle test passed!")

if __name__ == "__main__":
    test_job_manager_flow()
