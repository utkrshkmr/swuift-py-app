"""JobRunner: QThread that executes queued SWUIFT simulations sequentially."""

from __future__ import annotations

import io
import os
import sys
import threading
import traceback
from datetime import datetime
from typing import List

from PySide6.QtCore import QThread, Signal

from .job_queue import JobConfig, STATUS_DONE, STATUS_FAILED, STATUS_RUNNING


class _JobCancelledError(Exception):
    """Raised inside the simulation loop when the current job is cancelled."""


class _QtTqdm:
    """Drop-in tqdm replacement that emits Qt signals and supports cancellation."""

    def __init__(self, iterable, *, desc: str = "", unit: str = "",
                 signal=None, runner=None, **kwargs):
        self._iter = list(iterable)
        self._total = len(self._iter)
        self._n = 0
        self._signal = signal
        self._runner: JobRunner | None = runner

    def __iter__(self):
        for item in self._iter:
            # Check for cancellation of this specific job.
            if self._runner is not None and self._runner._cancel_current:
                raise _JobCancelledError()
            # Check for full queue cancellation.
            if self._runner is not None and self._runner.isInterruptionRequested():
                raise _JobCancelledError()
            yield item
            self._n += 1
            if self._signal is not None:
                self._signal(self._n, self._total)

    def __len__(self):
        return self._total


class _StreamRedirect(io.TextIOBase):
    """Redirects write() calls to a callable (used for live log output)."""

    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def write(self, s: str) -> int:
        if s:
            self._cb(s)
        return len(s)

    def flush(self):
        pass


class JobRunner(QThread):
    """Runs a list of JobConfig objects sequentially in a background thread.

    Cancel behaviour
    ----------------
    - ``requestInterruption()``  → cancel everything (current job + all remaining).
    - ``cancel_current_job()``   → cancel only the currently-running job; the runner
      then emits ``ask_continue(job_id)`` and pauses.  Call ``resume_queue()`` or
      ``stop_queue()`` from the main thread to decide what happens next.

    Signals
    -------
    job_started(job_id)
    job_phase(job_id, phase_name)
    job_progress(job_id, current_step, total_steps)
    job_log(job_id, text)
    job_finished(job_id, success, message)
    ask_continue(job_id)          -- emitted after a single-job cancel if more jobs remain
    all_done()
    """

    job_started = Signal(int)
    job_phase = Signal(int, str)
    job_progress = Signal(int, int, int)
    job_log = Signal(int, str)
    job_finished = Signal(int, bool, str)
    ask_continue = Signal(int)   # main thread must call resume_queue() or stop_queue()
    all_done = Signal()

    def __init__(self, jobs: List[JobConfig], parent=None) -> None:
        super().__init__(parent)
        self._jobs = jobs
        # Single-job cancel state
        self._cancel_current: bool = False
        self._stop_after_current: bool = False
        self._continue_event = threading.Event()
        self._user_wants_continue: bool = False

    # ------------------------------------------------------------------
    # Public control methods (called from main thread)
    # ------------------------------------------------------------------

    def cancel_current_job(self) -> None:
        """Cancel only the currently executing job; ask user about the rest."""
        self._cancel_current = True

    def resume_queue(self) -> None:
        """Called by main thread when user chose to continue after single-job cancel."""
        self._user_wants_continue = True
        self._continue_event.set()

    def stop_queue(self) -> None:
        """Called by main thread when user chose to stop after single-job cancel."""
        self._user_wants_continue = False
        self._continue_event.set()

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        for job in self._jobs:
            if self.isInterruptionRequested() or self._stop_after_current:
                break
            self._run_one(job)
        self.all_done.emit()

    def _run_one(self, job: JobConfig) -> None:
        self._cancel_current = False   # reset for each new job
        self.job_started.emit(job.job_id)

        try:
            import swuift.simulation as sim_module
            from swuift.config import build_config
            from swuift.data_loader import load_all_extracted
            from swuift.simulation import run_simulation
        except ImportError as exc:
            self.job_finished.emit(job.job_id, False, f"Import error: {exc}")
            return

        job_id = job.job_id

        def _progress(n: int, total: int):
            self.job_progress.emit(job_id, n, total)

        orig_tqdm = sim_module.tqdm
        runner_ref = self

        class _BoundTqdm(_QtTqdm):
            def __init__(self, iterable, **kwargs):
                super().__init__(iterable, signal=_progress, runner=runner_ref, **kwargs)

        sim_module.tqdm = _BoundTqdm

        def _log_cb(text: str):
            self.job_log.emit(job_id, text)

        redir = _StreamRedirect(_log_cb)
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = redir
        sys.stderr = redir

        try:
            self.job_phase.emit(job_id, "Loading data")
            data = load_all_extracted(
                wildland_fire_matrix_file=job.wildland_fire_matrix,
                domain_matrix_file=job.domain_matrix,
                binary_cover_file=job.binary_cover,
                homes_matrix_file=job.homes_matrix,
                latitude_file=job.latitude,
                longitude_file=job.longitude,
                radiation_matrix_file=job.radiation_matrix,
                spotting_matrix_file=job.spotting_matrix,
                water_matrix_file=job.water_matrix,
                wind_file=job.wind_file,
                preload_wind=not job.lazy_wind,
            )

            self.job_phase.emit(job_id, "Building config")
            cfg = build_config(
                None,
                t_start=job.t_start,
                t_end=job.t_end,
                maxstep=job.maxstep,
                hardening_rad=job.hardening_rad,
                hardening_spo=job.hardening_spo,
                rad_energy_ig=job.rad_energy_ig,
                rad_rf=job.rad_rf,
                fb_wind_coef=job.fb_wind_coef,
                fb_wind_sd=job.fb_wind_sd,
                fb_wind_sd_transverse=job.fb_wind_sd_transverse,
                seed_hardening=job.seed_hardening,
                seed_spread=job.seed_spread,
            )

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(job.output_dir, f"run_{stamp}")
            base = out_dir
            suffix = 2
            while os.path.exists(out_dir):
                out_dir = f"{base}-{suffix}"
                suffix += 1
            os.makedirs(out_dir, exist_ok=True)

            if self.isInterruptionRequested() or self._cancel_current:
                data.close()
                self.job_finished.emit(job_id, False, "Cancelled before simulation.")
                self._handle_post_cancel(job_id)
                return

            self.job_phase.emit(job_id, "Simulating")

            def _phase_cb(phase: str):
                self.job_phase.emit(job_id, phase)

            run_simulation(
                cfg,
                data,
                out_dir,
                dpi=150,
                dpi_hires=job.dpi_hires,
                make_video=job.make_video,
                dump_interval=job.dump_interval,
                dump_csv=job.dump_csv,
                dump_radiation_csv=job.dump_radiation_csv,
                dump_spotting_csv=job.dump_spotting_csv,
                phase_callback=_phase_cb,
            )
            data.close()

            self.job_phase.emit(job_id, "Done")
            self.job_finished.emit(job_id, True, "")

        except _JobCancelledError:
            self.job_finished.emit(job_id, False, "Cancelled by user.")
            self._handle_post_cancel(job_id)

        except Exception:
            tb = traceback.format_exc()
            self.job_finished.emit(job_id, False, tb)

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sim_module.tqdm = orig_tqdm

    def _handle_post_cancel(self, job_id: int) -> None:
        """After a single-job cancel, ask main thread whether to continue."""
        remaining = [j for j in self._jobs
                     if j.status not in ("Done", "Failed", "Running")]
        if remaining and not self.isInterruptionRequested():
            # Pause and ask the user via main-thread signal.
            self._continue_event.clear()
            self.ask_continue.emit(job_id)
            self._continue_event.wait()        # block until main thread responds
            if not self._user_wants_continue:
                self._stop_after_current = True
        else:
            self._stop_after_current = True
