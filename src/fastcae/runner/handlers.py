"""What each kind of job does. A job's handler takes the job - to report progress and events on,
and to ask whether it was cancelled - and its spec, and returns what it made, briefly."""

from __future__ import annotations

from collections.abc import Callable

from ..simulate import campaign
from ..simulate import jobs as simulate_jobs

HANDLERS: dict[str, Callable] = {
    "campaign.solve": campaign.solve_campaign,
    "baseline.cudss": simulate_jobs.solve_deck,
}
