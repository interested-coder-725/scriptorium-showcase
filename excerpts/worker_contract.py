"""Scriptorium worker wire contract — the head↔worker HTTP protocol.

This module is the **canonical** definition of the protocol every worker speaks
(manga, webnovel, torrent). It is deliberately self-contained: it imports only
``pydantic`` and the stdlib, no other Scriptorium code. That lets a worker living
in its own repo vendor this file verbatim (or pin a copy) without dragging in the
whole ``scriptorium`` package.

Wire types use plain strings for ``content_type`` (the head maps them to its
``ContentType`` enum); the only shared enum is :class:`WorkerJobState`, which the
head maps to its ``DownloadState``.

Endpoints (all JSON):

    GET  /health        -> HealthResponse        liveness + vendor reachability
    GET  /capabilities  -> Capabilities          what this worker can do
    POST /search        -> SearchResponse         discovery: find candidate releases
    POST /acquire       -> JobRef                 discovery: start getting one thing
    POST /sync          -> JobRef                 maintenance: update library / new chapters
    GET  /jobs          -> JobsResponse           all known job states (head polls this)
    GET  /jobs/{id}     -> JobDTO                  one job's state

Protocol version: bump ``PROTOCOL_VERSION`` on any breaking change; the head logs
a warning when a worker reports a different major version.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

PROTOCOL_VERSION = "1.0"


class WorkerJobState(str, Enum):
    """Lifecycle of a worker job. Maps 1:1 onto the head's ``DownloadState``."""

    QUEUED = "queued"          # accepted, not started
    RUNNING = "running"        # actively downloading/scraping
    COMPLETED = "completed"    # files present on disk, not yet in a library backend
    IMPORTED = "imported"      # worker placed it into its backend itself (e.g. Suwayomi->Komga)
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (
            WorkerJobState.COMPLETED,
            WorkerJobState.IMPORTED,
            WorkerJobState.FAILED,
            WorkerJobState.CANCELLED,
        )


class ReleaseDTO(BaseModel):
    """A candidate download surfaced by /search. Mirrors the head's ``Release``."""

    source: str                       # indexer/provider/source name
    title: str
    content_type: str
    magnet_or_url: str
    size_bytes: Optional[int] = None
    seeders: Optional[int] = None
    extension: Optional[str] = None
    info_url: Optional[str] = None


class ChapterResult(BaseModel):
    """A serialized chapter a job produced (manga/webnovel). Lets the head fill
    ``sc_chapters`` and advance the edition watermark without its own scrape."""

    number: float
    title: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    downloaded: bool = True


# --- requests --------------------------------------------------------------

class SearchRequest(BaseModel):
    content_type: str
    query: Optional[str] = None
    asin: Optional[str] = None
    isbn: Optional[str] = None


class AcquireRequest(BaseModel):
    """Start acquiring one thing. The head sends enough for the worker to act
    without any DB access, plus an opaque ``edition_ref`` it round-trips back so
    the head can correlate the resulting job to a catalog Edition."""

    content_type: str
    title: str = ""
    edition_ref: Optional[str] = None         # opaque, e.g. "ed:1234"
    # Discovery (books): the chosen release to grab.
    release: Optional[ReleaseDTO] = None
    # Serial (manga/webnovel): where to fetch + how far the catalog has gotten.
    provider: Optional[str] = None
    source_url: Optional[str] = None
    chapter_watermark: float = 0.0


class SyncRequest(BaseModel):
    """Library-wide maintenance: refresh and pull anything missing. ``scope`` is
    worker-defined (e.g. category ids, or 'missing'/'unread' for Suwayomi)."""

    content_type: Optional[str] = None
    scope: Optional[str] = None


# --- responses -------------------------------------------------------------

class SearchResponse(BaseModel):
    releases: list[ReleaseDTO] = Field(default_factory=list)


class JobRef(BaseModel):
    """Returned by /acquire and /sync — the handle the head stores in
    ``sc_downloads.client_hash`` and polls /jobs for."""

    job_id: str
    state: WorkerJobState = WorkerJobState.QUEUED


class JobDTO(BaseModel):
    job_id: str
    state: WorkerJobState
    kind: str = "acquire"                      # "acquire" | "sync"
    content_type: Optional[str] = None
    edition_ref: Optional[str] = None
    release_title: Optional[str] = None
    progress: float = 0.0                      # 0.0–1.0
    progress_current: int = 0
    progress_total: int = 0
    imported_path: Optional[str] = None
    chapters: list[ChapterResult] = Field(default_factory=list)
    error: Optional[str] = None


class JobsResponse(BaseModel):
    jobs: list[JobDTO] = Field(default_factory=list)


class Capabilities(BaseModel):
    vendor: str
    content_types: list[str] = Field(default_factory=list)
    supports: list[str] = Field(default_factory=list)   # subset of: search acquire sync
    protocol_version: str = PROTOCOL_VERSION


class HealthResponse(BaseModel):
    vendor: str
    vendor_reachable: bool
    protocol_version: str = PROTOCOL_VERSION
    version: Optional[str] = None
    detail: dict[str, Any] = Field(default_factory=dict)
