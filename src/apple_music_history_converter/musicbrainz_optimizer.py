#!/usr/bin/env python3
"""
MusicBrainz Optimizer - Minimal 3-Phase Approach for Low-End Hardware

Designed for constrained environments (t2.medium: 2 vCPUs, 4GB RAM).
Target: Complete optimization in under 5 minutes (ideally 2-3 minutes).

Key principles:
1. RAM-aware memory limits (tiered by system RAM)
2. NO parallel operations (thrashes 2-CPU systems)
3. Minimal table structure (one table, two indexes)
4. Atomic staging file swap (crash-safe)
5. Structured logging for diagnostics

Phases:
1. Import: CSV -> DuckDB table with lowercase columns
2. Index: Create indexes on title and artist columns
3. Finalize: Metadata + atomic swap
"""

import os
import sys
import json
import time
import hashlib
import platform
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import duckdb

try:
    from .logging_config import get_logger
    from .app_directories import get_user_data_dir
except ImportError:
    from logging_config import get_logger
    from app_directories import get_user_data_dir

logger = get_logger(__name__)

# Schema version - increment to force re-optimization
SCHEMA_VERSION = 4  # New minimal schema


class OptimizationLogger:
    """
    Structured logging for optimization diagnostics.
    Outputs machine-parseable JSON lines for easy debugging.
    """

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.start_time = time.time()
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _log(self, level: str, event: str, **kwargs):
        """Write structured log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "event": event,
            **kwargs
        }

        # Console output (human readable)
        elapsed = time.time() - self.start_time
        msg = f"[{elapsed:6.1f}s] [{level}] {event}"
        if kwargs:
            details = " ".join(f"{k}={v}" for k, v in kwargs.items() if k not in ("timestamp", "level", "event"))
            if details:
                msg += f" | {details}"
        logger.info(msg)

        # File output (JSON lines)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Don't fail optimization due to logging issues

    def info(self, event: str, **kwargs):
        self._log("info", event, **kwargs)

    def error(self, event: str, **kwargs):
        self._log("error", event, **kwargs)

    def warn(self, event: str, **kwargs):
        self._log("warn", event, **kwargs)


def get_system_info() -> Dict[str, Any]:
    """Get system information for diagnostics and RAM-based configuration."""
    info = {
        "platform": platform.system(),
        "arch": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
    }

    # Get RAM info
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_total_mb"] = int(mem.total / (1024 * 1024))
        info["ram_available_mb"] = int(mem.available / (1024 * 1024))
    except ImportError:
        # Fallback: try to read from /proc/meminfo (Linux)
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        info["ram_total_mb"] = kb // 1024
                    elif line.startswith("MemAvailable:"):
                        kb = int(line.split()[1])
                        info["ram_available_mb"] = kb // 1024
        except Exception:
            info["ram_total_mb"] = 4096  # Assume 4GB if unknown
            info["ram_available_mb"] = 2048

    return info


def get_duckdb_memory_limit(ram_total_mb: int) -> int:
    """
    Calculate DuckDB memory limit based on system RAM.

    Tiered approach from the plan:
    - <= 4GB RAM -> 1GB limit
    - 4-8GB RAM -> 2GB limit
    - > 8GB RAM -> 3GB limit (cap at 4GB max)

    Returns memory limit in MB.
    """
    ram_gb = ram_total_mb / 1024

    if ram_gb <= 4:
        return 1024  # 1GB
    elif ram_gb <= 8:
        return 2048  # 2GB
    else:
        return 3072  # 3GB (conservative, avoids swap)


def should_skip_indexing(ram_total_mb: int) -> bool:
    """
    Determine if indexing should be skipped based on RAM.

    On low-RAM systems (<=4GB), indexing 29M+ rows takes too long
    and may OOM. DuckDB's vectorized engine can table-scan efficiently.

    Trade-off:
    - With indexes: 1-5ms searches, 30+ min setup
    - Without indexes: 50-100ms searches, ~5 min setup
    """
    return ram_total_mb <= 4096  # Skip on 4GB or less


def get_musicbrainz_dir() -> Path:
    """Get MusicBrainz data directory."""
    return get_user_data_dir() / "musicbrainz"


def get_canonical_dir() -> Path:
    """Get directory for canonical MusicBrainz CSV."""
    return get_musicbrainz_dir() / "canonical"


def get_duckdb_dir() -> Path:
    """Get directory for DuckDB database."""
    return get_musicbrainz_dir() / "duckdb"


class MusicBrainzOptimizer:
    """
    Minimal 3-phase MusicBrainz optimizer for low-end hardware.

    Designed for t2.medium (2 vCPUs, 4GB RAM) to complete in under 5 minutes.
    """

    def __init__(self, csv_path: Optional[Path] = None):
        """
        Initialize optimizer.

        Args:
            csv_path: Path to MusicBrainz CSV file. If None, uses default location.
        """
        self.base_dir = get_musicbrainz_dir()
        self.canonical_dir = get_canonical_dir()
        self.duckdb_dir = get_duckdb_dir()

        # Ensure directories exist
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        self.duckdb_dir.mkdir(parents=True, exist_ok=True)

        # Find CSV file
        if csv_path:
            self.csv_file = Path(csv_path)
        else:
            self.csv_file = self._find_csv_file()

        # Database paths
        self.db_live = self.duckdb_dir / "mb.duckdb"
        self.db_staging = self.duckdb_dir / "mb_staging.duckdb"
        self.meta_file = self.base_dir / "mb_meta.json"

        # Optimization log
        self.opt_log = OptimizationLogger(self.base_dir / "musicbrainz_optimization.log")

        # State
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._system_info = get_system_info()
        self._memory_limit_mb = get_duckdb_memory_limit(self._system_info.get("ram_total_mb", 4096))
        self._skip_indexing = should_skip_indexing(self._system_info.get("ram_total_mb", 4096))

        # Cancellation support
        self._cancelled = False

    def _find_csv_file(self) -> Optional[Path]:
        """Find MusicBrainz CSV file in canonical directory."""
        for pattern in ["*.csv", "canonical_musicbrainz_data.csv"]:
            files = list(self.canonical_dir.glob(pattern))
            if files:
                # Return largest CSV (most likely the full dump)
                return max(files, key=lambda f: f.stat().st_size)
        return None

    def _compute_version(self) -> str:
        """Compute version hash from CSV file for change detection."""
        if not self.csv_file or not self.csv_file.exists():
            return ""

        try:
            stat = self.csv_file.stat()
            version_string = f"{stat.st_size}|{stat.st_mtime}|{self.csv_file.name}"
            return hashlib.sha256(version_string.encode()).hexdigest()[:16]
        except Exception:
            return ""

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from mb_meta.json."""
        try:
            if self.meta_file.exists():
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            self.opt_log.warn("metadata_load_failed", error=str(e))
        return {}

    def _save_metadata(self, version: str, track_count: int):
        """Save metadata to mb_meta.json."""
        metadata = {
            "version": version,
            "schema_version": SCHEMA_VERSION,
            "optimized_at": datetime.utcnow().isoformat() + "Z",
            "track_count": track_count,
            "platform": self._system_info.get("platform", "unknown"),
            "duckdb_path": str(self.db_live),
            "indexed": not self._skip_indexing,  # False on low-RAM systems
        }

        try:
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            self.opt_log.info("metadata_written", **metadata)
        except Exception as e:
            self.opt_log.error("metadata_save_failed", error=str(e))

    def needs_optimization(self) -> bool:
        """
        Check if optimization is needed.

        Returns True if:
        - CSV file doesn't exist
        - Database doesn't exist
        - Version mismatch (CSV changed)
        - Schema version mismatch
        """
        if not self.csv_file or not self.csv_file.exists():
            self.opt_log.info("optimization_check", result="needed", reason="csv_missing")
            return True

        if not self.db_live.exists():
            self.opt_log.info("optimization_check", result="needed", reason="db_missing")
            return True

        metadata = self._load_metadata()
        current_version = self._compute_version()

        if metadata.get("schema_version") != SCHEMA_VERSION:
            self.opt_log.info("optimization_check", result="needed",
                           reason="schema_mismatch",
                           stored=metadata.get("schema_version"),
                           expected=SCHEMA_VERSION)
            return True

        if metadata.get("version") != current_version:
            self.opt_log.info("optimization_check", result="needed",
                           reason="version_mismatch",
                           stored=metadata.get("version"),
                           current=current_version)
            return True

        # Validate database has required table
        if not self._validate_database():
            self.opt_log.info("optimization_check", result="needed", reason="db_invalid")
            return True

        self.opt_log.info("optimization_check", result="skipped", reason="db_valid")
        return False

    def _validate_database(self) -> bool:
        """Validate that database has required table with data."""
        try:
            conn = duckdb.connect(str(self.db_live), read_only=True)
            result = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'musicbrainz'"
            ).fetchone()
            if not result or result[0] == 0:
                conn.close()
                return False

            # Check table has data
            result = conn.execute("SELECT 1 FROM musicbrainz LIMIT 1").fetchone()
            conn.close()
            return result is not None
        except Exception:
            return False

    def cleanup_staging(self):
        """Clean up any stale staging files from interrupted optimization."""
        if self.db_staging.exists():
            try:
                self.db_staging.unlink()
                self.opt_log.info("cleanup", deleted="staging_db")
            except Exception as e:
                self.opt_log.warn("cleanup_failed", file="staging_db", error=str(e))

        # Also clean up DuckDB WAL files if present
        for wal_file in self.duckdb_dir.glob("mb_staging.duckdb.*"):
            try:
                wal_file.unlink()
            except Exception:
                pass

        # Clean up temp directory
        temp_dir = self.duckdb_dir / "temp"
        if temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.opt_log.info("cleanup", deleted="temp_dir")
            except Exception:
                pass

    def cancel(self):
        """Request cancellation of ongoing optimization."""
        self._cancelled = True

    def _check_cancelled(self):
        """Check if cancelled and raise if so."""
        if self._cancelled:
            raise RuntimeError("Optimization cancelled")

    def optimize(self, progress_callback: Optional[Callable[[str, float, float], None]] = None):
        """
        Run the 3-phase optimization.

        Args:
            progress_callback: Optional callback(message, percent, start_time)
        """
        self._cancelled = False
        start_time = time.time()

        def progress(message: str, percent: float):
            if progress_callback:
                progress_callback(message, percent, start_time)
            self.opt_log.info("progress", message=message, percent=percent)

        # Log start
        self.opt_log.info("optimization_start",
                        platform=self._system_info.get("platform"),
                        arch=self._system_info.get("arch"),
                        ram_total_mb=self._system_info.get("ram_total_mb"),
                        ram_limit_mb=self._memory_limit_mb,
                        cpu_count=self._system_info.get("cpu_count"),
                        csv_path=str(self.csv_file))

        logger.print_always(f"\n{'='*60}")
        logger.print_always("[>] MusicBrainz Optimization (3-Phase Minimal)")
        logger.print_always(f"{'='*60}")
        logger.print_always(f"   RAM: {self._system_info.get('ram_total_mb', '?')}MB total, {self._memory_limit_mb}MB limit")
        logger.print_always(f"   CPUs: {self._system_info.get('cpu_count', '?')}")
        logger.print_always(f"   CSV: {self.csv_file}")
        if self._skip_indexing:
            logger.print_always(f"   Mode: LOW-RAM (skipping indexes for speed)")
        logger.print_always(f"{'='*60}\n")

        try:
            # Cleanup any previous failed attempt
            self.cleanup_staging()

            # Phase 1: Import
            progress("Phase 1/3: Importing data...", 5)
            self._check_cancelled()
            phase1_start = time.time()
            track_count = self._phase1_import(progress)
            phase1_time = time.time() - phase1_start
            self.opt_log.info("phase_end", phase="import", duration_ms=int(phase1_time*1000), rows=track_count)
            logger.print_always(f"   [OK] Phase 1 (Import): {phase1_time:.1f}s - {track_count:,} tracks")

            # Phase 2: Index (SKIP on low-RAM systems)
            if self._skip_indexing:
                progress("Phase 2/3: Skipping indexes (low-RAM mode)...", 50)
                self.opt_log.info("phase_skipped", phase="indexing", reason="low_ram")
                logger.print_always(f"   [>] Phase 2 (Index): SKIPPED (low-RAM mode)")
                phase2_time = 0
            else:
                progress("Phase 2/3: Building indexes...", 50)
                self._check_cancelled()
                phase2_start = time.time()
                self._phase2_index(progress)
                phase2_time = time.time() - phase2_start
                self.opt_log.info("phase_end", phase="indexing", duration_ms=int(phase2_time*1000))
                logger.print_always(f"   [OK] Phase 2 (Index): {phase2_time:.1f}s")

            # Phase 3: Finalize
            progress("Phase 3/3: Finalizing...", 90)
            self._check_cancelled()
            phase3_start = time.time()
            self._phase3_finalize(track_count)
            phase3_time = time.time() - phase3_start
            self.opt_log.info("phase_end", phase="finalize", duration_ms=int(phase3_time*1000))
            logger.print_always(f"   [OK] Phase 3 (Finalize): {phase3_time:.1f}s")

            # Done
            total_time = time.time() - start_time
            progress("Done!", 100)

            self.opt_log.info("optimization_complete",
                            total_duration_ms=int(total_time*1000),
                            track_count=track_count)

            logger.print_always(f"\n{'='*60}")
            logger.print_always(f"[OK] OPTIMIZATION COMPLETE!")
            logger.print_always(f"   Total time: {total_time:.1f}s")
            logger.print_always(f"   Tracks: {track_count:,}")
            logger.print_always(f"{'='*60}\n")

        except Exception as e:
            self.opt_log.error("optimization_failed",
                            error_type=type(e).__name__,
                            error_message=str(e))
            logger.print_always(f"[X] Optimization failed: {e}")

            # Cleanup on failure
            self._close_connection()
            self.cleanup_staging()
            raise

    def _phase1_import(self, progress: Callable) -> int:
        """
        Phase 1: Import CSV into DuckDB with lowercase columns.

        Creates a single table 'musicbrainz' with:
        - Original columns
        - recording_lower (lowercase track name)
        - artist_lower (lowercase artist name)
        """
        self.opt_log.info("phase_start", phase="import")

        # Connect to staging database
        self._close_connection()
        self._conn = duckdb.connect(str(self.db_staging))

        # Configure for low memory with temp directory for spill
        self._conn.execute(f"SET memory_limit='{self._memory_limit_mb}MB'")
        self._conn.execute("SET preserve_insertion_order=false")

        # Enable temp directory for spill-to-disk (critical for low RAM)
        temp_dir = self.duckdb_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._conn.execute(f"SET temp_directory='{temp_dir}'")

        # Single thread on low-CPU systems to avoid thrashing
        threads = 1 if self._system_info.get("cpu_count", 2) <= 2 else 2
        self._conn.execute(f"SET threads TO {threads}")

        self.opt_log.info("duckdb_configured",
                        memory_limit_mb=self._memory_limit_mb,
                        threads=threads)

        progress("Phase 1/3: Reading CSV...", 10)

        # Create table with import - SINGLE pass, minimal processing
        # Only add lowercase columns for matching - no regex, no cleaning
        sql = f"""
            CREATE TABLE musicbrainz AS
            SELECT
                *,
                lower(recording_name) AS recording_lower,
                lower(artist_credit_name) AS artist_lower,
                lower(release_name) AS release_lower
            FROM read_csv_auto('{self.csv_file}', ignore_errors=true)
            WHERE
                recording_name IS NOT NULL AND length(recording_name) > 0 AND
                artist_credit_name IS NOT NULL AND length(artist_credit_name) > 0
        """

        progress("Phase 1/3: Creating table...", 20)
        self._conn.execute(sql)

        # Get row count
        result = self._conn.execute("SELECT COUNT(*) FROM musicbrainz").fetchone()
        track_count = result[0] if result else 0

        # CRITICAL: Checkpoint to flush to disk and free memory for indexing
        progress("Phase 1/3: Checkpointing...", 40)
        self._conn.execute("CHECKPOINT")

        progress("Phase 1/3: Import complete", 45)
        return track_count

    def _phase2_index(self, progress: Callable):
        """
        Phase 2: Create indexes for fast lookups.

        Creates two indexes:
        - idx_recording_lower (for track name searches)
        - idx_artist_lower (for artist filtering)

        NO parallel indexing - sequential is faster on 2 CPUs.
        """
        self.opt_log.info("phase_start", phase="indexing")

        # Index 1: Recording name
        progress("Phase 2/3: Indexing tracks...", 55)
        idx_start = time.time()
        self._conn.execute("CREATE INDEX idx_recording_lower ON musicbrainz(recording_lower)")
        self.opt_log.info("index_created", index="idx_recording_lower", duration_ms=int((time.time()-idx_start)*1000))

        self._check_cancelled()

        # Index 2: Artist name
        progress("Phase 2/3: Indexing artists...", 75)
        idx_start = time.time()
        self._conn.execute("CREATE INDEX idx_artist_lower ON musicbrainz(artist_lower)")
        self.opt_log.info("index_created", index="idx_artist_lower", duration_ms=int((time.time()-idx_start)*1000))

        progress("Phase 2/3: Indexes complete", 85)

    def _phase3_finalize(self, track_count: int):
        """
        Phase 3: Finalize database with atomic swap.

        Steps:
        1. Close connection to staging DB
        2. Atomic rename: staging -> live (with retry on Windows)
        3. Save metadata
        4. Cleanup
        """
        self.opt_log.info("phase_start", phase="finalize")

        # Close connection before rename
        self._close_connection()

        # Atomic swap with platform-specific retry
        self._atomic_swap()

        # Save metadata
        version = self._compute_version()
        self._save_metadata(version, track_count)

        self.opt_log.info("atomic_swap", status="success")

    def _atomic_swap(self):
        """
        Atomically swap staging DB to live DB.

        On Windows: May need retries due to file locking.
        On Unix: Single rename call.
        """
        max_retries = 3 if platform.system() == "Windows" else 1
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                # Remove old live DB if exists
                if self.db_live.exists():
                    self.db_live.unlink()

                # Rename staging to live
                self.db_staging.rename(self.db_live)

                # Also move any WAL files
                for wal_file in self.duckdb_dir.glob("mb_staging.duckdb.*"):
                    new_name = wal_file.name.replace("mb_staging", "mb")
                    try:
                        wal_file.rename(self.duckdb_dir / new_name)
                    except Exception:
                        wal_file.unlink()  # Just delete if can't rename

                self.opt_log.info("atomic_swap", status="success", attempt=attempt+1)
                return

            except Exception as e:
                self.opt_log.warn("atomic_swap_retry", attempt=attempt+1, error=str(e))
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(f"Failed to swap database after {max_retries} attempts: {e}")

    def _close_connection(self):
        """Close DuckDB connection if open."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


def run_optimization_with_progress(parent_window=None, csv_path: Optional[Path] = None):
    """
    Convenience function to run optimization.

    Args:
        parent_window: Optional Toga window for modal (not used in minimal version)
        csv_path: Optional path to CSV file

    Returns:
        MusicBrainzOptimizer instance after optimization
    """
    optimizer = MusicBrainzOptimizer(csv_path)

    if optimizer.needs_optimization():
        optimizer.optimize()
    else:
        logger.print_always("[OK] MusicBrainz database is up to date - skipping optimization")

    return optimizer


class MusicBrainzSearcher:
    """
    Simple search interface for the optimized MusicBrainz database.

    Designed for table-scan searches (no indexes) on low-RAM systems.
    Typical search times: 10-200ms for exact match, 50-500ms for contains.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize searcher.

        Args:
            db_path: Path to DuckDB file. If None, uses default location.
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = get_duckdb_dir() / "mb.duckdb"

        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self):
        """Connect to the database."""
        if self._conn:
            return

        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        self._conn = duckdb.connect(str(self.db_path), read_only=True)
        # Use 2 threads for parallel scan
        self._conn.execute("SET threads TO 2")

    def close(self):
        """Close the database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def search(self, track_name: str, artist_hint: Optional[str] = None,
               album_hint: Optional[str] = None, limit: int = 10) -> list:
        """
        Search for a track in the MusicBrainz database.

        IMPORTANT: Artist hint is used to BOOST results, NOT filter them out.
        This ensures tracks are found even when artist names differ (e.g.,
        "Joe Hisaishi" vs Japanese script version).

        Single table scan with computed match quality for ordering.
        On low-RAM systems (no indexes), each search takes ~500ms-2s.

        Args:
            track_name: Track name to search for
            artist_hint: Optional artist name to BOOST matching results (not filter)
            album_hint: Optional album name to BOOST matching results (not filter)
            limit: Maximum results to return

        Returns:
            List of dicts with keys: recording_name, artist_credit_name,
            release_name, recording_mbid, artist_mbids, release_mbid
        """
        self.connect()

        # Clean inputs and strip common suffixes that may not be in MusicBrainz
        track_lower = track_name.lower().strip()

        # Strip common suffixes that vary between sources
        import re
        track_lower = re.sub(r'\s*\((remaster(ed)?|remix|live|radio edit|single version|album version|mono|stereo)\)\s*$', '', track_lower, flags=re.IGNORECASE)
        track_lower = re.sub(r'\s*-\s*(remaster(ed)?|remix|live|radio edit)\s*$', '', track_lower, flags=re.IGNORECASE)

        artist_lower = artist_hint.lower().strip() if artist_hint else None
        album_lower = album_hint.lower().strip() if album_hint else None

        # Search by track name ONLY - artist/album used for BOOSTING not filtering
        # This ensures we find tracks even when artist names are in different scripts
        params = [f"%{track_lower}%"]

        # Build ORDER BY with parameterized artist/album boost
        # Priority scoring (lower = better):
        #   - Exact track match with artist match: 0 + 1 = 1
        #   - Exact track match, no artist: 100 + 1 = 101
        #   - Prefix track match with artist: 0 + 2 = 2
        #   - Contains track match with artist: 0 + 3 = 3
        #   - etc.

        # Priority order (lower value = better match):
        # 1. Exact track name match is MOST important
        # 2. Artist match boosts within same track match tier
        # 3. Score is only tiebreaker for identical matches
        #
        # This ensures "One Summer's Day" by Joe Hisaishi beats "One Summer's Day"
        # by random artists even if Joe Hisaishi's version has worse score.

        if artist_lower and album_lower:
            # Both artist and album hints
            order_clause = """
                CASE WHEN recording_lower = ? THEN 0 ELSE 1000 END +
                CASE WHEN recording_lower LIKE ? THEN 0 ELSE 500 END +
                CASE WHEN artist_lower LIKE ? THEN 0 ELSE 100 END +
                CASE WHEN release_lower LIKE ? THEN 0 ELSE 50 END,
                score ASC
            """
            params.extend([track_lower, f"{track_lower}%", f"%{artist_lower}%", f"%{album_lower}%"])
        elif artist_lower:
            # Artist hint only - exact track match + artist match = best
            order_clause = """
                CASE WHEN recording_lower = ? THEN 0 ELSE 1000 END +
                CASE WHEN recording_lower LIKE ? THEN 0 ELSE 500 END +
                CASE WHEN artist_lower LIKE ? THEN 0 ELSE 100 END,
                score ASC
            """
            params.extend([track_lower, f"{track_lower}%", f"%{artist_lower}%"])
        elif album_lower:
            # Album hint only
            order_clause = """
                CASE WHEN recording_lower = ? THEN 0 ELSE 1000 END +
                CASE WHEN recording_lower LIKE ? THEN 0 ELSE 500 END +
                CASE WHEN release_lower LIKE ? THEN 0 ELSE 50 END,
                score ASC
            """
            params.extend([track_lower, f"{track_lower}%", f"%{album_lower}%"])
        else:
            # No hints - just order by track match quality, then score
            order_clause = """
                CASE WHEN recording_lower = ? THEN 0 ELSE 1000 END +
                CASE WHEN recording_lower LIKE ? THEN 0 ELSE 500 END,
                score ASC
            """
            params.extend([track_lower, f"{track_lower}%"])

        # Single scan query - order by combined match quality
        sql = f"""
            SELECT recording_name, artist_credit_name, release_name,
                   recording_mbid, artist_mbids, release_mbid, score
            FROM musicbrainz
            WHERE recording_lower LIKE ?
            ORDER BY {order_clause}
            LIMIT {limit}
        """

        try:
            rows = self._conn.execute(sql, params).fetchall()

            return [
                {
                    "recording_name": row[0],
                    "artist_credit_name": row[1],
                    "release_name": row[2],
                    "recording_mbid": row[3],
                    "artist_mbids": row[4],
                    "release_mbid": row[5],
                    "score": row[6],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def is_ready(self) -> bool:
        """Check if the database is ready for searches."""
        return self.db_path.exists()


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MusicBrainz Optimizer")
    parser.add_argument("--csv", type=str, help="Path to MusicBrainz CSV file")
    parser.add_argument("--force", action="store_true", help="Force re-optimization")
    parser.add_argument("--search", type=str, help="Search for a track")
    parser.add_argument("--artist", type=str, help="Artist hint for search")
    args = parser.parse_args()

    if args.search:
        # Search mode
        searcher = MusicBrainzSearcher()
        if not searcher.is_ready():
            logger.print_always("[X] Database not found. Run optimization first.")
            sys.exit(1)

        import time
        start = time.time()
        results = searcher.search(args.search, artist_hint=args.artist)
        elapsed = (time.time() - start) * 1000

        logger.print_always(f"\nSearch: \"{args.search}\"" + (f" by \"{args.artist}\"" if args.artist else ""))
        logger.print_always(f"Found {len(results)} results in {elapsed:.0f}ms\n")

        for i, r in enumerate(results[:5], 1):
            logger.print_always(f"  {i}. {r['recording_name']} by {r['artist_credit_name']}")
            logger.print_always(f"     Album: {r['release_name']}")

        searcher.close()
    else:
        # Optimize mode
        csv_path = Path(args.csv) if args.csv else None
        optimizer = MusicBrainzOptimizer(csv_path)

        if args.force or optimizer.needs_optimization():
            optimizer.optimize()
        else:
            logger.print_always("[OK] Database is up to date. Use --force to re-optimize.")
