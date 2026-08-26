"""Discovery orchestrator.

Runs the full pipeline: deterministic query generation → source fetching
(isolated per source) → normalization → dedupe/upsert → cheap prefilter →
prioritized LLM scoring (cache-aware, capped) → qualification (>=85) →
transactional Draft import → run persistence → batched notification.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Callable

from cv_optimizer import db
from cv_optimizer.config import settings
from cv_optimizer.discovery.activity import (
    absence_transition,
    is_ats_source,
    source_active_state,
)
from cv_optimizer.discovery.config import DiscoveryConfig, load_config
from cv_optimizer.discovery.dedupe import (
    canonical_url_for,
    descriptions_match,
    job_fingerprint,
)
from cv_optimizer.discovery.filters import prefilter
from cv_optimizer.discovery.importer import DraftImporter
from cv_optimizer.discovery.models import (
    DiscoveredJob,
    DiscoveryQuery,
    DiscoveryRunResult,
)
from cv_optimizer.discovery import notify as notify_mod
from cv_optimizer.discovery.sources import (
    AshbySource,
    GreenhouseSource,
    LeverSource,
    RateLimited,
    SerpApiSource,
    SourceError,
)
from cv_optimizer.matching import MatchService, jd_hash, normalize_jd_for_hash

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


def _quiet_progress(message: str) -> None:
    pass


class DiscoveryService:
    """Domain-level orchestration of one discovery run."""

    def __init__(
        self,
        *,
        config: DiscoveryConfig | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.config = config if config is not None else load_config()
        self.progress = progress or _quiet_progress
        self.importer = DraftImporter(self.config)

    # ── Query / source construction ──────────────────────────────────────────

    def build_queries(self) -> list[DiscoveryQuery]:
        """Deterministic, bounded query generation. Searches by ROLE, not
        framework. No LLM is used to generate queries."""
        queries: list[DiscoveryQuery] = []
        locations = self.config.locations
        for role in self.config.roles:
            if locations.warsaw.onsite or locations.warsaw.hybrid:
                queries.append(
                    DiscoveryQuery(q=role, location="Warsaw, Poland", meta={"scope": "warsaw"})
                )
            remote = locations.remote
            if remote.poland:
                queries.append(
                    DiscoveryQuery(q=f"{role} remote", location="Poland", remote=True, meta={"scope": "poland"})
                )
            if remote.europe or remote.eu or remote.eea:
                queries.append(
                    DiscoveryQuery(q=f"{role} remote Europe", remote=True, meta={"scope": "europe"})
                )
            elif remote.emea:
                queries.append(
                    DiscoveryQuery(q=f"{role} remote EMEA", remote=True, meta={"scope": "emea"})
                )
            if remote.worldwide:
                queries.append(
                    DiscoveryQuery(q=f"{role} remote", remote=True, meta={"scope": "worldwide"})
                )
        return queries

    def build_sources(self, source_filter: list[str] | None = None) -> list:
        allowed = {s.strip().lower() for s in source_filter} if source_filter else None
        sources = []
        if (allowed is None or "serpapi" in allowed) and self.config.source_enabled("serpapi"):
            sources.append(
                SerpApiSource(max_pages_per_query=self.config.serpapi().max_pages_per_query)
            )
        if (allowed is None or "lever" in allowed) and self.config.source_enabled("lever"):
            sources.append(LeverSource.from_config(self.config))
        if (allowed is None or "ashby" in allowed) and self.config.source_enabled("ashby"):
            sources.append(AshbySource.from_config(self.config))
        if (allowed is None or "greenhouse" in allowed) and self.config.source_enabled("greenhouse"):
            sources.append(GreenhouseSource.from_config(self.config))
        return sources

    # ── Main entrypoint ──────────────────────────────────────────────────────

    def run(
        self,
        *,
        sources: list[str] | None = None,
        import_matches: bool = True,
        preview: bool = False,
        force_rescore: bool = False,
        max_scores: int | None = None,
    ) -> DiscoveryRunResult:
        if not self.config.enabled:
            return DiscoveryRunResult(run_id=-1, status="disabled", errors=["discovery disabled in config"])

        run_id = db.create_discovery_run()
        result = DiscoveryRunResult(run_id=run_id, status="running")
        errors: list[str] = []
        source_stats: dict[str, dict] = {}
        run_started_at = datetime.now(timezone.utc)

        logger.info("Discovery run #%s started", run_id)
        try:
            queries = self.build_queries()
            enabled_sources = self.build_sources(sources)
            fetch_cap = self.config.max_fetch_per_run

            # ── Fetch phase ────────────────────────────────────────────────
            # Query-driven sources (SerpApi) iterate every query; board ATS
            # sources ignore the query, so they are fetched ONCE per run.
            fetched_jobs: list[DiscoveredJob] = []
            completed_sources: set[str] = set()
            self.progress("Fetching…")
            for source in enabled_sources:
                stats = {"requests": 0, "fetched": 0, "new": 0, "errors": 0}
                source_stats[source.name] = stats
                source_ok = True
                source_queries = (
                    [queries[0]] if is_ats_source(source.name) and queries else queries
                )
                for query in source_queries:
                    if not source_ok:
                        break
                    stats["requests"] += 1
                    try:
                        jobs = source.fetch(query)
                        stats["fetched"] += len(jobs)
                        fetched_jobs.extend(jobs)
                    except RateLimited as exc:
                        stats["errors"] += 1
                        errors.append(str(exc))
                        source_ok = False
                        logger.warning("%s", exc)
                    except (SourceError, Exception) as exc:  # noqa: BLE001 — isolation boundary
                        stats["errors"] += 1
                        errors.append(f"{source.name}: {exc}")
                        logger.exception("Discovery source %s failed for query %r", source.name, query.q)
                        if isinstance(exc, SourceError):
                            source_ok = False
                    # Per-run global fetch cap (spec §9): stop ingesting raw
                    # results beyond the budget; later queries are skipped.
                    if fetch_cap is not None and len(fetched_jobs) >= fetch_cap:
                        break
                if source_ok:
                    completed_sources.add(source.name)
                if fetch_cap is not None and len(fetched_jobs) >= fetch_cap:
                    logger.warning(
                        "Global fetch cap (%d) reached; stopping fetch phase", fetch_cap
                    )
                    break
            fetched_jobs = fetched_jobs[:fetch_cap] if fetch_cap is not None else fetched_jobs
            result.fetched = len(fetched_jobs)
            logger.info(
                "%d raw results from %d source(s)", result.fetched, len(enabled_sources)
            )
            self.progress("Normalizing…")

            # ── Normalize + upsert/dedupe phase ─────────────────────────────
            touched_ids: set[int] = set()
            for job in fetched_jobs:
                posting_id, is_new, _changed = self._upsert_job(job)
                touched_ids.add(posting_id)
                if is_new:
                    result.new += 1
                    stats = source_stats.setdefault(job.source, {})
                    stats["new"] = stats.get("new", 0) + 1
                else:
                    result.updated += 1
            result.normalized = result.new + result.updated

            # ── Prefilter phase ─────────────────────────────────────────────
            self.progress("Filtering…")
            for posting_id in touched_ids:
                job_row = db.get_job_posting(posting_id)
                if job_row is None:
                    continue
                decision = prefilter(self._to_discovered_job(job_row), self.config)
                db.set_job_prefilter(posting_id, decision.state, decision.reason)
                if decision.state == "fail":
                    result.filtered += 1

            # ── ATS absence sweep — only for sources that completed cleanly ─
            if not preview:
                self._sweep_ats_absences(completed_sources, run_started_at)

            if preview:
                status = "completed" if not errors else "completed_with_errors"
                db.finish_discovery_run(
                    run_id,
                    status,
                    source_stats_json=json.dumps(source_stats),
                    errors_json=json.dumps(errors),
                )
                result.status = status
                result.errors = errors
                logger.info(
                    "Discovery run #%s %s (preview): %d fetched, %d new, %d filtered",
                    run_id, status, result.fetched, result.new, result.filtered,
                )
                self._update_counts(run_id, result)
                return result

            # ── Scoring + import phase ──────────────────────────────────────
            self.progress("Scoring…")
            budget = max_scores if max_scores is not None else self.config.max_scores_per_run
            candidates = self._prioritize(touched_ids, force_rescore=force_rescore)

            processed: list[tuple[dict, dict]] = []
            llm_budget_used = 0
            for job_row in candidates:
                needs_llm = job_row["match_state"] in ("pending", "error") or force_rescore
                if not needs_llm:
                    # Cache-ready row: only free when the cache identity still
                    # matches. A cache miss (new CV/version/model) MUST count
                    # against the budget.
                    if not self._has_cached_match(job_row):
                        if llm_budget_used >= budget:
                            db.set_job_match_state(job_row["id"], "pending")
                            continue
                        needs_llm = True
                if needs_llm:
                    if llm_budget_used >= budget:
                        continue  # remains pending for the next run
                    llm_budget_used += 1
                self.progress(f"Scoring {len(processed) + 1}/{budget}…")
                try:
                    score_result = MatchService().score_job_posting(
                        job_row["id"], force=force_rescore
                    )
                except Exception as exc:  # noqa: BLE001 — one LLM failure must not stop the run
                    errors.append(f"scoring job #{job_row['id']}: {exc}")
                    logger.exception("LLM scoring failed for job posting #%s", job_row["id"])
                    continue
                result.scored += 1
                processed.append((job_row, score_result))
                if self._qualifies(job_row, score_result["score"]):
                    result.qualified += 1
                    if import_matches and self.config.auto_import:
                        self._import_qualified(job_row, score_result, result, errors)

            # ── Import backlog: previously scored qualifying jobs ──────────
            if import_matches and self.config.auto_import:
                for job_row in db.get_pending_import_jobs():
                    assessment = db.get_latest_job_match(job_row["id"])
                    if assessment and assessment["score"] >= self.config.minimum_match_score:
                        self._import_qualified(
                            job_row,
                            {"score": assessment["score"], "label": assessment["label"], "cached": True},
                            result,
                            errors,
                        )

            status = "completed" if not errors else "completed_with_errors"
            db.finish_discovery_run(
                run_id,
                status,
                source_stats_json=json.dumps(source_stats),
                errors_json=json.dumps(errors),
            )
            self._update_counts(run_id, result)
            result.status = status
            result.errors = errors

            logger.info(
                "Discovery run #%s %s: %d fetched, %d new, %d updated, %d filtered, "
                "%d scored, %d qualified, %d imported, %d linked-existing",
                run_id, status, result.fetched, result.new, result.updated,
                result.filtered, result.scored, result.qualified, result.imported,
                result.linked_existing,
            )

            if result.imported > 0:
                notify_mod.notify_new_imports(result.imported_applications)
            return result
        except Exception as exc:  # noqa: BLE001 — top-level safety net
            logger.exception("Discovery run #%s failed", run_id)
            errors.append(str(exc))
            try:
                db.finish_discovery_run(
                    run_id,
                    "failed",
                    source_stats_json=json.dumps(source_stats),
                    errors_json=json.dumps(errors),
                )
                self._update_counts(run_id, result)
            except Exception:
                logger.exception("Could not persist failed run state")
            result.status = "failed"
            result.errors = errors
            return result

    # ── Upsert / dedupe ─────────────────────────────────────────────────────

    def _upsert_job(self, job: DiscoveredJob) -> tuple[int, bool, bool]:
        """Staged dedupe. Returns (job_posting_id, is_new, changed).

        Also applies the source-aware activity model (aggregator vs ATS)
        and title-derived seniority classification before persistence.
        """
        state, confidence = source_active_state(job, self.config)
        job.active_state = state
        job.active_confidence = confidence
        if job.seniority == "unknown":
            from cv_optimizer.discovery.sources.base import classify_seniority_title

            job.seniority = classify_seniority_title(job.role) or "unknown"

        canonical_url = canonical_url_for(job)
        fp = job_fingerprint(job)
        jd_hash_value = jd_hash(job.description)

        # Level 1 — exact source identity.
        existing = db.get_job_posting_by_source_id(job.source, job.external_id)
        if existing is not None:
            db.insert_job_source_ref(
                existing["id"], job.source, job.external_id,
                source_url=job.source_url, apply_url=job.apply_url,
                raw_json=json.dumps(job.raw_payload, ensure_ascii=False) if job.raw_payload else None,
                active_state=job.active_state,
            )
            changed = self._maybe_update_description(existing, job)
            db.update_job_posting_seen(
                existing["id"],
                active_state=job.active_state,
                active_confidence=self._merge_confidence(existing, job),
                consecutive_absences=0,
            )
            return existing["id"], False, changed

        # Level 2 — normalized canonical URL.
        if canonical_url:
            existing = db.get_job_posting_by_canonical_url(canonical_url)
            if existing is not None:
                return self._attach_to_existing(existing, job, canonical_url)

        # Level 3 — cross-source fingerprint + description similarity.
        for candidate in db.find_job_postings_by_fingerprint(*fp):
            if descriptions_match(candidate["description"], job.description):
                return self._attach_to_existing(candidate, job, canonical_url)

        # New canonical posting.
        posting_id = db.insert_job_posting(
            company=job.company,
            role=job.role,
            description=job.description,
            description_hash=jd_hash_value,
            canonical_url=canonical_url,
            location_text=job.location_text,
            work_model=job.work_model,
            remote_scope=job.remote_scope,
            seniority=job.seniority,
            employment_type=job.employment_type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            salary_period=job.salary_period,
            salary_raw=job.salary_raw,
            posted_at=job.posted_at_iso(),
            active_state=job.active_state,
            active_confidence=job.active_confidence,
            company_norm=fp[0],
            role_norm=fp[1],
            location_norm=fp[2],
        )
        db.insert_job_source_ref(
            posting_id, job.source, job.external_id,
            source_url=job.source_url, apply_url=job.apply_url,
            raw_json=json.dumps(job.raw_payload, ensure_ascii=False) if job.raw_payload else None,
            active_state=job.active_state,
        )
        return posting_id, True, True

    def _attach_to_existing(
        self, existing: dict, job: DiscoveredJob, canonical_url: str | None
    ) -> tuple[int, bool, bool]:
        db.insert_job_source_ref(
            existing["id"], job.source, job.external_id,
            source_url=job.source_url, apply_url=job.apply_url,
            raw_json=json.dumps(job.raw_payload, ensure_ascii=False) if job.raw_payload else None,
            active_state=job.active_state,
        )
        changed = self._maybe_update_description(existing, job)
        updates: dict = {
            "active_state": job.active_state,
            "active_confidence": self._merge_confidence(existing, job),
            "consecutive_absences": 0,
        }
        if canonical_url and not existing["canonical_url"]:
            updates["canonical_url"] = canonical_url
        db.update_job_posting_seen(existing["id"], **updates)
        return existing["id"], False, changed

    def _merge_confidence(self, existing: dict, job: DiscoveredJob) -> str:
        """A direct ATS confirmation upgrades aggregator confidence."""
        if is_ats_source(job.source) and job.active_state == "active":
            return "high"
        rank = {"high": 3, "medium": 2, "low": 1}
        return existing["active_confidence"] if rank.get(existing["active_confidence"], 0) >= rank.get(job.active_confidence, 0) else job.active_confidence

    def _maybe_update_description(self, existing: dict, job: DiscoveredJob) -> bool:
        """If the JD changed, update it and reset match state to pending.

        A new text that is merely a truncation of the stored one (e.g. an
        aggregator snippet vs a full ATS JD) does NOT replace the richer
        copy; any other change does (spec §44).
        """
        new_hash = jd_hash(job.description)
        if new_hash == existing["description_hash"]:
            return False
        old_norm = normalize_jd_for_hash(existing["description"])
        new_norm = normalize_jd_for_hash(job.description)
        if new_norm and new_norm in old_norm:
            return False  # snippet of the stored JD — keep the richer text
        db.update_job_posting_seen(
            existing["id"],
            description=job.description,
            description_hash=new_hash,
            reset_match=True,
        )
        return True

    # ── Activity sweep ──────────────────────────────────────────────────────

    def _sweep_ats_absences(self, completed_sources: set[str], run_started_at) -> None:
        """Postings from ATS sources that completed cleanly but did not see
        this posting accumulate absence; two consecutive absences → inactive.

        Sources that failed (network/429) are EXCLUDED: provider outages are
        not evidence that a posting disappeared (spec §42).
        """
        ats_names = {
            name for name in completed_sources if is_ats_source(name)
        }
        if not ats_names:
            return
        conn = db.connect()
        try:
            conn.row_factory = None
            placeholders = ",".join("?" for _ in ats_names)
            rows = conn.execute(
                f"SELECT DISTINCT p.id, p.consecutive_absences FROM job_postings p "
                f"JOIN job_source_refs r ON r.job_posting_id = p.id "
                f"WHERE r.source IN ({placeholders}) AND r.last_seen_at < ?",
                (*ats_names, run_started_at.strftime("%Y-%m-%d %H:%M:%S")),
            ).fetchall()
        finally:
            conn.close()
        for posting_id, _current in rows:
            new_absences = db.bump_job_posting_absence(posting_id)
            new_state = absence_transition(new_absences)
            if new_state == "inactive":
                db.update_job_posting_seen(posting_id, active_state="inactive")
                logger.info("Job posting #%s marked inactive after %d absences", posting_id, new_absences)

    # ── Scoring queue ───────────────────────────────────────────────────────

    def _prioritize(self, touched_ids: set[int], *, force_rescore: bool) -> list[dict]:
        """Spec §31 ordering: newest posted_at → active confidence → role
        relevance → geography certainty → previously unseen."""
        rows = []
        for posting_id in touched_ids:
            row = db.get_job_posting(posting_id)
            if row is None:
                continue
            if row["prefilter_state"] == "fail":
                continue
            if row["active_state"] == "inactive":
                continue
            if row["user_state"] == "dismissed":
                continue
            if row["application_id"] is not None:
                continue  # already imported / linked
            rows.append(row)

        confidence_rank = {"high": 0, "medium": 1, "low": 2}
        prefilter_rank = {"pass": 0, "review": 1}

        def sort_key(row: dict):
            posted = row["posted_at"] or ""
            return (
                posted,                                        # newest first
                -confidence_rank.get(row["active_confidence"], 3),  # high confidence first
                -prefilter_rank.get(row["prefilter_state"], 2),     # pass before review
                row["first_seen_at"] or "",                    # unseen first
            )

        rows.sort(key=sort_key, reverse=True)
        return rows

    def _has_cached_match(self, job_row: dict) -> bool:
        """True when the posting's scoring identity matches an existing
        cached assessment (free to reuse, no LLM call needed)."""
        from cv_optimizer.matching import (
            MatchService,
            jd_hash as _jd_hash,
        )

        try:
            service = MatchService()
            _master_cv, _profile, candidate_hash = service._load_profile(None)
        except Exception:  # noqa: BLE001 — unreadable CV means no cache identity
            return False
        return (
            db.find_cached_job_match(
                job_row["id"],
                candidate_hash,
                _jd_hash(job_row["description"]),
                settings.match_scoring_version,
                settings.match_prompt_version,
                settings.model_name,
            )
            is not None
        )

    def _qualifies(self, job_row: dict, score: int) -> bool:
        return (
            job_row["active_state"] != "inactive"
            and job_row["prefilter_state"] != "fail"
            and score >= self.config.minimum_match_score
        )

    def _import_qualified(
        self,
        job_row: dict,
        score_result: dict,
        result: DiscoveryRunResult,
        errors: list[str],
    ) -> None:
        try:
            import_result = self.importer.import_job(job_row["id"])
            if import_result["linked_existing"]:
                result.linked_existing += 1
                return
            result.imported += 1
            result.imported_applications.append(
                {
                    "score": score_result["score"],
                    "company": job_row["company"],
                    "role": job_row["role"],
                    "url": job_row["canonical_url"],
                    "application_id": import_result["application_id"],
                    "linked_existing": False,
                }
            )
        except Exception as exc:  # noqa: BLE001 — one import failure must not stop the run
            errors.append(f"import job #{job_row['id']}: {exc}")
            logger.exception("Import failed for job posting #%s", job_row["id"])

    # ── Run bookkeeping ─────────────────────────────────────────────────────

    def _update_counts(self, run_id: int, result: DiscoveryRunResult) -> None:
        db.update_discovery_run(
            run_id,
            fetched_count=result.fetched,
            normalized_count=result.normalized,
            new_count=result.new,
            updated_count=result.updated,
            filtered_count=result.filtered,
            scored_count=result.scored,
            qualified_count=result.qualified,
            imported_count=result.imported,
        )

    @staticmethod
    def _to_discovered_job(row: dict) -> DiscoveredJob:
        """Reconstructs a DiscoveredJob for re-running the prefilter."""
        from datetime import datetime as _dt

        posted = None
        if row.get("posted_at"):
            try:
                posted = _dt.fromisoformat(row["posted_at"])
            except ValueError:
                posted = None
        return DiscoveredJob(
            source="stored",
            external_id=str(row["id"]),
            company=row["company"],
            role=row["role"],
            description=row["description"],
            canonical_url=row["canonical_url"],
            location_text=row["location_text"],
            work_model=row["work_model"],
            remote_scope=row["remote_scope"],
            seniority=row["seniority"],
            employment_type=row["employment_type"],
            posted_at=posted,
            active_state=row["active_state"],
            active_confidence=row["active_confidence"],
        )
