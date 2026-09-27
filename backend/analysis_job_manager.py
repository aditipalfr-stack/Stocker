from typing import Dict, List, Optional, Any, Callable
import threading
import uuid
import time
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class AnalysisJobStatus(BaseModel):
    job_id: str
    symbol: str
    company_name: str
    status: str = Field(description="queued | running | completed | failed")
    progress_pct: int = 0
    stage_message: str = "Initialized"
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None

class AnalysisJobManager:
    """
    Thread-safe in-memory background job manager for live AI fundamental analyses.
    Allows long-running document extractions to proceed asynchronously without
    blocking HTTP requests or frontend navigation.
    """
    def __init__(self):
        self._jobs: Dict[str, AnalysisJobStatus] = {}
        self._symbol_latest: Dict[str, str] = {}
        self._lock = threading.Lock()

    def get_job(self, job_id: str) -> Optional[AnalysisJobStatus]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_job_by_symbol(self, symbol: str) -> Optional[AnalysisJobStatus]:
        clean_sym = symbol.upper().strip()
        with self._lock:
            job_id = self._symbol_latest.get(clean_sym)
            if not job_id:
                return None
            return self._jobs.get(job_id)

    def get_all_jobs(self) -> List[AnalysisJobStatus]:
        with self._lock:
            # Return active jobs plus recent jobs (sorted by started_at desc)
            jobs = list(self._jobs.values())
            jobs.sort(key=lambda j: j.started_at, reverse=True)
            return jobs[:20]

    def is_symbol_running(self, symbol: str) -> bool:
        job = self.get_job_by_symbol(symbol)
        return bool(job and job.status in ("queued", "running"))

    def start_job(
        self,
        symbol: str,
        company_name: str,
        task_fn: Callable[[Callable[[int, str], None]], Any]
    ) -> AnalysisJobStatus:
        clean_sym = symbol.upper().strip()
        with self._lock:
            # Check if active job already running
            existing_id = self._symbol_latest.get(clean_sym)
            if existing_id:
                existing_job = self._jobs.get(existing_id)
                if existing_job and existing_job.status in ("queued", "running"):
                    return existing_job

            job_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            job = AnalysisJobStatus(
                job_id=job_id,
                symbol=clean_sym,
                company_name=company_name,
                status="running",
                progress_pct=5,
                stage_message="Starting AI analysis pipeline...",
                started_at=now_iso
            )
            self._jobs[job_id] = job
            self._symbol_latest[clean_sym] = job_id

        def _worker():
            def _progress_cb(pct: int, msg: str):
                with self._lock:
                    if job.status == "running":
                        job.progress_pct = max(0, min(100, pct))
                        job.stage_message = msg

            try:
                task_fn(_progress_cb)
                with self._lock:
                    job.status = "completed"
                    job.progress_pct = 100
                    job.stage_message = f"AI Analysis complete for {company_name} ({clean_sym})"
                    job.completed_at = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                with self._lock:
                    job.status = "failed"
                    job.error = str(e)
                    job.stage_message = f"Analysis error: {str(e)}"
                    job.completed_at = datetime.now(timezone.utc).isoformat()

        thread = threading.Thread(target=_worker, name=f"AIAnalysis-{clean_sym}", daemon=True)
        thread.start()
        return job

# Singleton job manager instance
job_manager = AnalysisJobManager()
