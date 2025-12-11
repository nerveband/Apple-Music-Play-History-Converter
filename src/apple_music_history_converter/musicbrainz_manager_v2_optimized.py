#!/usr/bin/env python3
"""
MusicBrainz Manager V2 - ULTRA-OPTIMIZED VERSION
Comprehensive implementation with:
- Hardware-adaptive optimization (Performance vs Efficiency mode)
- Staging + atomic swap for crash safety
- Parallel index creation
- Dynamic memory allocation
- Hot/cold table architecture
- LRU search caching
- Pre-computed text cleaning
- Compressed storage
- Platform-specific optimizations
- Golden-set testing for accuracy verification

Target: 60-75% faster optimization, 10-100x faster searches
Accuracy: Preserve 94%+ matching accuracy across all modes
"""

import os
import json
import time
import hashlib
import threading
import unicodedata
import re
import shutil
import platform
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple, Union, Any
from dataclasses import dataclass, field
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
import logging
import duckdb

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# =============================================================================
# HARDWARE PROBE & MODE SELECTION
# =============================================================================

class OptimizationMode(Enum):
    """Optimization mode based on hardware capabilities."""
    PERFORMANCE = "performance"  # Full optimization with all indexes
    EFFICIENCY = "efficiency"    # Minimal optimization for low-RAM systems


@dataclass
class HardwareProfile:
    """System hardware profile for optimization decisions."""
    platform: str
    arch: str
    cpu_count: int
    ram_total_mb: int
    ram_available_mb: int
    disk_speed_score: float  # 0-1, higher = faster
    recommended_mode: OptimizationMode
    memory_limit_mb: int
    thread_count: int
    skip_cold_indexes: bool  # Skip expensive COLD table indexes on slow systems


def probe_hardware() -> HardwareProfile:
    """
    Probe system hardware to determine optimal optimization strategy.

    This runs a quick benchmark (< 2 seconds) to assess system capabilities
    and recommends either Performance or Efficiency mode.

    Returns:
        HardwareProfile with system info and recommendations
    """
    # Basic system info
    system = platform.system()
    arch = platform.machine()
    cpu_count = os.cpu_count() or 2

    # RAM detection
    if PSUTIL_AVAILABLE:
        mem = psutil.virtual_memory()
        ram_total_mb = int(mem.total / (1024 * 1024))
        ram_available_mb = int(mem.available / (1024 * 1024))
    else:
        # Fallback: try /proc/meminfo (Linux) or assume 4GB
        ram_total_mb = 4096
        ram_available_mb = 2048
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        ram_total_mb = int(line.split()[1]) // 1024
                    elif line.startswith("MemAvailable:"):
                        ram_available_mb = int(line.split()[1]) // 1024
        except Exception:
            pass

    # Quick disk benchmark (optional, defaults to medium)
    disk_speed_score = _benchmark_disk_speed()

    # Determine mode based on hardware
    ram_gb = ram_total_mb / 1024

    # Mode selection logic from plan:
    # - Performance: >= 8GB RAM and fast disk
    # - Efficiency: < 8GB RAM or slow disk
    if ram_gb >= 8 and disk_speed_score >= 0.5:
        mode = OptimizationMode.PERFORMANCE
    else:
        mode = OptimizationMode.EFFICIENCY

    # Memory limit (tiered approach from plan)
    if ram_gb <= 4:
        memory_limit_mb = 1024  # 1GB
    elif ram_gb <= 8:
        memory_limit_mb = 2048  # 2GB
    elif ram_gb <= 16:
        memory_limit_mb = 4096  # 4GB
    else:
        memory_limit_mb = 6144  # 6GB max to leave room for OS

    # Thread count based on CPU and mode
    if mode == OptimizationMode.EFFICIENCY:
        # Conservative threading for efficiency mode
        thread_count = min(cpu_count, 2)
    else:
        # More aggressive for performance mode
        if system == "Windows":
            thread_count = min(cpu_count, 4)  # Windows has thread overhead
        else:
            thread_count = min(cpu_count, 8)

    # Skip COLD indexes on very slow systems
    skip_cold_indexes = (ram_gb <= 4) or (disk_speed_score < 0.3)

    return HardwareProfile(
        platform=system,
        arch=arch,
        cpu_count=cpu_count,
        ram_total_mb=ram_total_mb,
        ram_available_mb=ram_available_mb,
        disk_speed_score=disk_speed_score,
        recommended_mode=mode,
        memory_limit_mb=memory_limit_mb,
        thread_count=thread_count,
        skip_cold_indexes=skip_cold_indexes
    )


def _benchmark_disk_speed() -> float:
    """
    Quick disk speed benchmark using DuckDB.

    Returns:
        Score from 0-1 (higher = faster)
        - 1.0: SSD-class performance (< 0.5s for 10MB)
        - 0.5: Medium performance (0.5-2s)
        - 0.0: Slow disk (> 2s)
    """
    try:
        import tempfile

        # Create temp file for benchmark
        with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
            temp_path = f.name

        try:
            start = time.time()

            # Quick benchmark: create small table and query
            conn = duckdb.connect(temp_path)
            conn.execute("SET memory_limit='256MB'")

            # Create 100K rows (simulates small portion of real workload)
            conn.execute("""
                CREATE TABLE bench AS
                SELECT
                    i AS id,
                    'test_recording_' || i AS recording,
                    'test_artist_' || (i % 1000) AS artist
                FROM range(100000) t(i)
            """)

            # Force flush
            conn.execute("CHECKPOINT")

            elapsed = time.time() - start
            conn.close()

            # Score based on elapsed time
            if elapsed < 0.5:
                return 1.0
            elif elapsed < 1.0:
                return 0.8
            elif elapsed < 2.0:
                return 0.5
            elif elapsed < 4.0:
                return 0.3
            else:
                return 0.1

        finally:
            # Cleanup
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    except Exception:
        # On any error, assume medium speed
        return 0.5

try:
    from .trace_utils import TRACE_ENABLED, trace_call, trace_log
    from .app_directories import get_log_path
    from .logging_config import get_logger
except ImportError:
    from trace_utils import TRACE_ENABLED, trace_call, trace_log
    from app_directories import get_log_path
    from logging_config import get_logger

logger = get_logger(__name__)

if not PSUTIL_AVAILABLE:
    logger.warning("[!]  psutil not available - using default 2GB memory limit")

# Increment schema version to force re-optimization
SCHEMA_VERSION = 3

# Optimized constants
SEARCH_ROW_LIMIT = 10  # Reduced from 25 for faster queries
LRU_CACHE_SIZE = 10000  # 10k entries ~ 2MB RAM

# SmartLogger handles file logging automatically

# Try to import rapidfuzz for optional fuzzy matching
try:
    from rapidfuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    fuzz = None


# Unicode normalization mappings
UNICODE_APOSTROPHE_MAP = {
    '\u2018': "'",  # LEFT SINGLE QUOTATION MARK
    '\u2019': "'",  # RIGHT SINGLE QUOTATION MARK
    '\u02BC': "'",  # MODIFIER LETTER APOSTROPHE
    '\u02B9': "'",  # MODIFIER LETTER PRIME
    '\u0060': "'",  # GRAVE ACCENT
    '\u00B4': "'",  # ACUTE ACCENT
}

UNICODE_QUOTE_MAP = {
    '\u201C': '"',  # LEFT DOUBLE QUOTATION MARK
    '\u201D': '"',  # RIGHT DOUBLE QUOTATION MARK
    '\u201E': '"',  # DOUBLE LOW-9 QUOTATION MARK
    '\u201F': '"',  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
}


@dataclass
class MatchingConfig:
    """Configuration for matching algorithm tunables."""

    # Table split
    hot_percentile: float = 0.15  # Top 15% = HOT table
    search_row_limit: int = 10  # Candidates per query
    high_accuracy_row_limit: int = 20  # More candidates in high accuracy mode

    # Confidence thresholds
    min_confidence_margin: float = 500_000  # Minimum gap between top 2 candidates
    min_absolute_score: float = 1_000_000  # Minimum score to accept match
    low_confidence_escalation_threshold: float = 300_000  # Auto-escalate below this

    # Edge case handling
    min_effective_title_length: int = 3  # Titles shorter = require hints
    generic_titles: frozenset = field(default_factory=lambda: frozenset([
        # Standard generic titles
        "intro", "interlude", "outro", "untitled", "instrumental",
        "prelude", "skit", "intermission", "prologue", "epilogue",
        "introduction", "overture", "finale",
        # Soundtrack/score additions
        "main theme", "end credits", "opening", "closing",
        "theme", "reprise", "scene", "act", "part",
        "credits", "title", "movement", "coda", "cadenza",
        # Common filler/placeholder titles
        "track", "bonus", "hidden track", "bonus track",
        "acoustic", "demo", "live", "remix", "version",
        # Single-word ambiguous titles
        "home", "love", "fire", "rain", "water", "time",
        "alone", "stay", "go", "run", "fly", "dream", "hope"
    ]))

    # Regex patterns for structurally ambiguous titles (numbered scenes, roman numerals, etc.)
    ambiguous_patterns: tuple = field(default_factory=lambda: (
        r'^(scene|act|part|track|chapter|movement)\s*\d+$',  # "Scene 3", "Track 12"
        r'^(scene|act|part|track|chapter|movement)\s+[ivxlcdm]+$',  # "Act II", "Movement IV"
        r'^\d+$',  # Just numbers: "17", "1"
        r'^#\d+$',  # Hash numbers: "#1", "#17"
        r'^[ivxlcdm]+$',  # Roman numerals only: "iv", "xii"
        r'^no\.\s*\d+$',  # "No. 5", "No. 12"
        r'^opus\s*\d+$',  # "Opus 40"
        r'^op\.\s*\d+$',  # "Op. 40"
    ))

    # High-frequency title threshold (candidates count)
    high_frequency_threshold: int = 50  # Titles with 50+ candidates = common

    # Scoring weights
    artist_exact_bonus: int = 5_000_000
    artist_partial_bonus: int = 4_000_000
    artist_fuzzy_bonus: int = 3_000_000  # New: bonus for fuzzy artist match
    album_exact_bonus: int = 5_000_000
    album_partial_bonus: int = 3_000_000
    title_exact_bonus: int = 1_500_000
    title_contains_bonus: int = 750_000
    release_penalty: int = 600_000
    artist_penalty: int = 400_000

    # Fuzzy matching
    fuzzy_enabled: bool = False
    fuzzy_threshold: float = 0.7  # Minimum similarity score
    fuzzy_artist_threshold: float = 0.85  # Higher threshold for artist fuzzy matching
    fuzzy_artist_enabled: bool = True  # Enable fuzzy artist matching even in normal mode

    # Tiered fuzzy artist matching (Phase 1.3: refined obscure artist policy)
    fuzzy_artist_high_threshold: float = 0.90  # High confidence threshold
    fuzzy_artist_medium_threshold: float = 0.75  # Medium confidence threshold
    fuzzy_artist_high_multiplier: float = 0.8  # 80% of fuzzy bonus for high similarity
    fuzzy_artist_medium_multiplier: float = 0.3  # 30% of fuzzy bonus for medium similarity

    # Token-level similarity (Jaccard)
    token_similarity_enabled: bool = True  # Enable Jaccard token similarity
    token_similarity_threshold: float = 0.5  # Minimum token overlap
    token_similarity_weight: float = 0.4  # Weight in hybrid score (Jaccard contribution)
    edit_distance_weight: float = 0.6  # Weight in hybrid score (Levenshtein contribution)

    # Hybrid similarity bonus (combined token + edit distance)
    hybrid_similarity_bonus: int = 2_000_000  # Bonus for high hybrid similarity

    # Full-Text Search (FTS) for COLD table (Phase 4 optimization)
    fts_enabled: bool = True  # Enable FTS for COLD table searches
    fts_fallback_to_like: bool = True  # Fall back to LIKE if FTS fails

    # Phonetic matching (Phase 5: Soundex-based pre-filtering)
    phonetic_enabled: bool = True  # Enable phonetic matching for fuzzy searches
    phonetic_artist_threshold: float = 0.8  # Minimum phonetic match score
    phonetic_title_threshold: float = 0.7  # Minimum phonetic match for titles
    phonetic_boost_similar: float = 1.2  # Boost score multiplier for phonetic matches
    phonetic_cache_size: int = 10000  # LRU cache size for phonetic codes

    # Mode: "normal" or "high_accuracy"
    mode: str = "normal"

    # Dynamic mode escalation
    auto_escalate_on_low_confidence: bool = True  # Auto-escalate to high accuracy

    # Behavior flags
    match_short_titles_without_hints: bool = False
    strict_cold_matching: bool = True


@dataclass
class CandidateResult:
    """Result from candidate scoring."""
    artist_name: str
    release_name: str
    score: float  # Computed weight score
    mb_score: float  # Original MusicBrainz score
    artist_match: Optional[str]  # "exact", "partial", or None
    album_match: bool
    confidence: str = "pending"  # "high", "low", or "pending"


@dataclass
class MatchResult:
    """Final match result with confidence info."""
    artist_name: Optional[str]
    confidence: str  # "high", "low", or "no_match"
    margin: float  # Gap between top 2 candidates
    top_candidates: List[CandidateResult]
    reason: str  # Why this result was chosen/rejected


class MusicBrainzManagerV2Optimized:
    """
    Ultra-optimized MusicBrainz implementation with:
    - 60-75% faster optimization
    - 10-100x faster searches (with caching)
    - 50-70% smaller database files
    - Cross-platform optimizations
    """

    def __init__(self, data_dir: str, config: Optional[MatchingConfig] = None):
        """Initialize with persistent file structure.

        Args:
            data_dir: Base directory for MusicBrainz data
            config: Optional matching configuration (uses defaults if not provided)
        """
        logger.debug("Initializing MusicBrainzManagerV2Optimized with data_dir=%s", data_dir)
        logger.print_always("[>] Initializing ULTRA-OPTIMIZED MusicBrainz Manager V2")

        # Store configuration (use defaults if not provided)
        self.config = config or MatchingConfig()

        self.data_dir = Path(data_dir) / "musicbrainz"
        self.canonical_dir = self.data_dir / "canonical"
        self.duckdb_dir = self.data_dir / "duckdb"
        self.meta_file = self.data_dir / "mb_meta.json"

        # Create directories
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        self.duckdb_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.csv_path = self.canonical_dir / "canonical_musicbrainz_data.csv"
        self.csv_file = self.csv_path
        self.duckdb_path = self.duckdb_dir / "mb.duckdb"
        self.duckdb_file = self.duckdb_path

        # Staging paths for crash-safe optimization
        self.duckdb_staging_path = self.duckdb_dir / "mb_staging.duckdb"
        self.temp_dir = self.duckdb_dir / "temp"

        # Hardware profile and optimization mode
        self._hardware_profile: Optional[HardwareProfile] = None
        self._optimization_mode: OptimizationMode = OptimizationMode.PERFORMANCE

        # State
        self._optimization_complete = False
        self._optimization_in_progress = False
        self._ready = False
        self._cancellation_requested = False
        self._conn = None
        self._reverse_length_ratio = 2.0
        self._metadata = {}

        # Simple schema mode (fast optimizer creates single 'musicbrainz' table)
        # When True, uses simplified search instead of complex hot/cold cascade
        self._use_simple_schema = False

        # OPTIMIZATION: LRU search cache (10k entries)
        self._search_cache: Dict[Tuple[str, str, str], Optional[str]] = {}
        self._cache_access_order: deque = deque()
        self._cache_hits = 0
        self._cache_misses = 0

        # OPTIMIZATION: Pre-cached artist popularity scores
        self._artist_score_cache: Dict[str, float] = {}

        # Phase 4: FTS availability flag
        self._fts_available: bool = False

        # Text cleaning patterns (compiled once)
        self._paren_pattern = re.compile(r'\s*[\(\[].*?[\)\]]')
        self._feat_conservative = re.compile(r'\bfeat(?:\.|uring)?\b.*', re.IGNORECASE)
        self._feat_aggressive = re.compile(r'feat(?:\.|uring)?.*', re.IGNORECASE)
        self._punct_pattern = re.compile(r'[^\w\s]', re.UNICODE)

        # Collaboration separator pattern for artist tokenization
        self._collab_pattern = re.compile(
            r'\s+(?:feat\.?|featuring|ft\.?|with|&|and|vs\.?|versus|x)\s+',
            re.IGNORECASE
        )

        # Cache for title frequency lookups
        self._title_frequency_cache: Dict[str, int] = {}

        # Cache for phonetic codes (Phase 5: Soundex-based matching)
        self._phonetic_cache: Dict[str, str] = {}

        # Migrate legacy data
        self._migrate_legacy_paths()

        # Load metadata
        self._metadata = self._load_metadata()

        # Check existing optimization (also connects to DuckDB if needed)
        self._check_existing_optimization(metadata=self._metadata)

        # Verify ready status after check
        if self._optimization_complete and not self._ready:
            logger.debug("Optimization marked complete but not ready - connecting to verify")
            if not self._conn:
                self._connect_to_duckdb()
            if self._conn and self._duckdb_has_required_tables():
                self._ready = True
                logger.info("Database validated - marking as ready")

        logger.print_always(f"[OK] Manager initialized - CSV: {self.csv_file.exists()}, Ready: {self._ready}")

    def _migrate_legacy_paths(self):
        """Move legacy MusicBrainz assets into the V2 directory layout."""
        try:
            # Promote legacy CSV
            if not self.csv_file.exists():
                candidates = []
                legacy_root_csv = self.data_dir / "canonical_musicbrainz_data.csv"
                if legacy_root_csv.exists():
                    candidates.append(legacy_root_csv)

                for candidate in self.data_dir.glob("**/canonical_musicbrainz_data.csv"):
                    try:
                        if candidate.resolve() == self.csv_file.resolve():
                            continue
                    except FileNotFoundError:
                        continue
                    if self.canonical_dir in candidate.parents:
                        continue
                    candidates.append(candidate)

                if candidates:
                    candidates.sort(key=lambda p: (p.stat().st_size, -len(p.parts)), reverse=True)
                    source_csv = candidates[0]
                    self.canonical_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("Migrating legacy CSV from %s", source_csv)
                    shutil.move(str(source_csv), str(self.csv_file))

            # Promote legacy DuckDB
            if not self.duckdb_file.exists():
                legacy_duckdb = self.data_dir / "mb.duckdb"
                if legacy_duckdb.exists():
                    self.duckdb_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("Migrating legacy DuckDB from %s", legacy_duckdb)
                    shutil.move(str(legacy_duckdb), str(self.duckdb_file))

            # Convert legacy metadata
            legacy_meta = self.data_dir / "metadata.json"
            if legacy_meta.exists() and not self.meta_file.exists():
                try:
                    with open(legacy_meta, "r", encoding="utf-8") as f:
                        legacy_data = json.load(f)
                except Exception:
                    legacy_data = {}

                version = self._compute_version()
                optimized_at = legacy_data.get("last_updated") or legacy_data.get("created") or "Unknown"
                migrated_metadata = {
                    "version": version,
                    "optimized_at": optimized_at,
                    "duckdb_path": str(self.duckdb_file),
                    "schema_version": SCHEMA_VERSION
                }

                try:
                    with open(self.meta_file, "w", encoding="utf-8") as f:
                        json.dump(migrated_metadata, f, indent=2)
                    logger.info("Migrated legacy metadata")
                except Exception:
                    pass

                try:
                    legacy_meta.unlink()
                except OSError:
                    pass

        except Exception as exc:
            logger.warning("Legacy migration failed: %s", exc)

    def _load_metadata(self) -> Dict:
        """Load metadata from mb_meta.json."""
        metadata: Dict = {}
        try:
            if self.meta_file.exists():
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    logger.debug("Loaded metadata: %s", metadata)
        except Exception as e:
            logger.warning(f"Error loading metadata: {e}")
        self._metadata = metadata
        return metadata

    def _save_metadata(self, version: str, optimized_at: str, track_count: Optional[int] = None):
        """Save metadata to mb_meta.json."""
        try:
            metadata = {
                "version": version,
                "optimized_at": optimized_at,
                "duckdb_path": str(self.duckdb_file),
                "schema_version": SCHEMA_VERSION,
                "optimization_mode": self._optimization_mode.value if self._optimization_mode else "unknown",
            }
            if track_count is not None:
                metadata["track_count"] = int(track_count)

            # Add hardware profile info if available
            if self._hardware_profile:
                metadata["hardware"] = {
                    "platform": self._hardware_profile.platform,
                    "ram_total_mb": self._hardware_profile.ram_total_mb,
                    "cpu_count": self._hardware_profile.cpu_count,
                    "disk_speed_score": round(self._hardware_profile.disk_speed_score, 2),
                }

            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            logger.info(f"Metadata saved: {metadata}")
            self._metadata = metadata

        except Exception as e:
            logger.error(f"Error saving metadata: {e}")

    def _compute_version(self) -> str:
        """Compute version hash from CSV file."""
        if not self.csv_file.exists():
            return ""

        try:
            stat = self.csv_file.stat()
            version_string = f"{stat.st_size}|{stat.st_mtime}|{self.csv_file.name}"
            version_hash = hashlib.sha256(version_string.encode()).hexdigest()[:16]
            return version_hash
        except Exception:
            return ""

    # =========================================================================
    # HARDWARE PROBE & MODE SELECTION
    # =========================================================================

    def _probe_hardware_and_select_mode(self) -> HardwareProfile:
        """
        Probe hardware and select optimization mode.

        This runs automatically before optimization to choose between
        Performance and Efficiency modes based on system capabilities.

        Returns:
            HardwareProfile with system info and recommendations
        """
        logger.print_always("\n[>] Probing system hardware...")

        profile = probe_hardware()
        self._hardware_profile = profile
        self._optimization_mode = profile.recommended_mode

        # Log hardware info
        logger.print_always(f"   Platform: {profile.platform} ({profile.arch})")
        logger.print_always(f"   RAM: {profile.ram_total_mb}MB total, {profile.ram_available_mb}MB available")
        logger.print_always(f"   CPUs: {profile.cpu_count}")
        logger.print_always(f"   Disk speed: {profile.disk_speed_score:.2f} (1.0 = SSD)")
        logger.print_always(f"   --> Mode: {profile.recommended_mode.value.upper()}")
        logger.print_always(f"   --> Memory limit: {profile.memory_limit_mb}MB")
        logger.print_always(f"   --> Threads: {profile.thread_count}")

        if profile.skip_cold_indexes:
            logger.print_always(f"   --> [!] Skipping COLD indexes (low-RAM/slow-disk optimization)")

        return profile

    # =========================================================================
    # STAGING & ATOMIC SWAP
    # =========================================================================

    def _cleanup_staging(self):
        """
        Clean up any stale staging files from interrupted optimization.

        Safe to call at any time - removes staging DB and temp files.
        """
        # Remove staging database
        if self.duckdb_staging_path.exists():
            try:
                self.duckdb_staging_path.unlink()
                logger.info(f"Cleaned up staging database: {self.duckdb_staging_path}")
            except Exception as e:
                logger.warning(f"Failed to clean staging DB: {e}")

        # Remove DuckDB WAL files for staging
        for wal_file in self.duckdb_dir.glob("mb_staging.duckdb.*"):
            try:
                wal_file.unlink()
            except Exception:
                pass

        # Clean up temp directory
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info("Cleaned up temp directory")
            except Exception:
                pass

    def _atomic_swap_staging_to_live(self):
        """
        Atomically swap staging database to live database.

        This is the crash-safe activation step:
        1. Close all connections
        2. Remove old live DB (if exists)
        3. Rename staging to live
        4. Clean up WAL files

        On Windows, may need retries due to file locking.
        """
        max_retries = 5 if platform.system() == "Windows" else 1
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                # Ensure connection is closed
                if self._conn:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                    self._conn = None

                # Small delay to let OS release file handles
                if attempt > 0:
                    time.sleep(retry_delay)

                # Remove old live DB if exists
                if self.duckdb_path.exists():
                    self.duckdb_path.unlink()

                # Rename staging to live (atomic on POSIX, nearly atomic on Windows)
                self.duckdb_staging_path.rename(self.duckdb_path)

                # Clean up staging WAL files
                for wal_file in self.duckdb_dir.glob("mb_staging.duckdb.*"):
                    try:
                        new_name = wal_file.name.replace("mb_staging", "mb")
                        wal_file.rename(self.duckdb_dir / new_name)
                    except Exception:
                        try:
                            wal_file.unlink()
                        except Exception:
                            pass

                logger.print_always(f"   [OK] Database activated (staging -> live)")
                logger.info(f"Atomic swap successful on attempt {attempt + 1}")
                return

            except Exception as e:
                logger.warning(f"Atomic swap attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f"Failed to activate database after {max_retries} attempts: {e}")

    def _connect_to_staging(self, profile: HardwareProfile):
        """
        Connect to staging database with hardware-appropriate settings.

        Args:
            profile: Hardware profile for configuration
        """
        # Ensure temp directory exists for spill-to-disk
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Connecting to staging database: {self.duckdb_staging_path}")
        self._conn = duckdb.connect(str(self.duckdb_staging_path))

        # Configure based on hardware profile
        self._conn.execute(f"SET memory_limit='{profile.memory_limit_mb}MB'")
        self._conn.execute("SET preserve_insertion_order=false")
        self._conn.execute(f"SET temp_directory='{self.temp_dir}'")
        self._conn.execute(f"SET threads TO {profile.thread_count}")

        # Enable compression
        try:
            self._conn.execute("PRAGMA enable_compression")
            self._conn.execute("SET compression='auto'")
        except Exception:
            pass

        # Platform-specific settings
        self._configure_platform_specific()

        logger.print_always(f"   [OK] Staging database connected")
        logger.print_always(f"       Memory: {profile.memory_limit_mb}MB, Threads: {profile.thread_count}")

    def _check_existing_optimization(self, metadata: Optional[Dict] = None):
        """Check if optimization is already complete for current CSV version."""
        logger.debug(f"_check_existing_optimization called - CSV exists: {self.csv_file.exists()}, DuckDB exists: {self.duckdb_file.exists()}")

        if not self.csv_file.exists() or not self.duckdb_file.exists():
            logger.debug("CSV or DuckDB missing - optimization required")
            return

        current_version = self._compute_version()
        if metadata is None:
            metadata = self._load_metadata()

        logger.debug(f"Current version: {current_version}, Metadata version: {metadata.get('version')}")
        logger.debug(f"Current schema: {SCHEMA_VERSION}, Metadata schema: {metadata.get('schema_version')}")

        metadata_schema = metadata.get("schema_version")
        # Accept both old schema (3) and new simple schema (4)
        # Schema 4 = fast optimizer (single table, no indexes on low-RAM)
        accepted_schemas = {SCHEMA_VERSION, 4}
        if metadata_schema not in accepted_schemas:
            logger.info(
                "Schema version mismatch (stored=%s, accepted=%s) - forcing re-optimization",
                metadata_schema, accepted_schemas
            )
            self._optimization_complete = False
            self._ready = False
            return

        if metadata.get("version") == current_version:
            logger.info("Metadata matches - validating DuckDB")
            logger.debug("   [?] Validating existing database...")
            self._connect_to_duckdb()

            if self._duckdb_has_required_tables():
                logger.info("DuckDB validation succeeded - reusing optimization")
                logger.print_always("   [OK] Database validated - ready to use!")
                self._optimization_complete = True
                self._ready = True
                return

            logger.warning("DuckDB missing tables - forcing re-optimization")
            logger.warning("   [!]  Database incomplete - re-optimization needed")
            self._optimization_complete = False
            self._ready = False
        else:
            logger.info(f"Version mismatch: current={current_version}, metadata={metadata.get('version')}")
            logger.warning(f"   [!]  Database version mismatch - re-optimization needed")

    def _connect_to_duckdb(self):
        """Connect to persistent DuckDB with OPTIMIZATIONS."""
        try:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass

            logger.debug("Connecting to DuckDB at %s", self.duckdb_file)
            logger.info(f"   [~] Connecting to DuckDB: {self.duckdb_file}")
            self._conn = duckdb.connect(str(self.duckdb_file))
            logger.print_always(f"   [OK] DuckDB connection established")

            # OPTIMIZATION 1: Dynamic memory allocation (40% of system RAM, 2GB min, 12GB max)
            # Increased from 25% to 40% to handle large operations
            if PSUTIL_AVAILABLE:
                total_ram_gb = psutil.virtual_memory().total / (1024**3)
                memory_limit = min(max(int(total_ram_gb * 0.4), 2), 12)
                logger.info(f"[>] OPTIMIZATION: Dynamic RAM allocation = {memory_limit}GB (was 2GB)")
                logger.print_always(f"   [>] RAM: {memory_limit}GB (40% of system RAM)")
            else:
                memory_limit = 4  # Increased default
                logger.warning(f"   [!]  RAM: {memory_limit}GB (psutil not available)")

            self._conn.execute(f"SET memory_limit='{memory_limit}GB'")

            # Disable insertion order preservation for memory efficiency
            self._conn.execute("SET preserve_insertion_order=false")
            logger.print_always(f"   [>] Memory optimization: preserve_insertion_order=false")

            # OPTIMIZATION 2: More threads for parallelism (was 4, now 8)
            self._conn.execute("SET threads TO 8")
            logger.info("[>] OPTIMIZATION: Thread count = 8 (was 4)")
            logger.print_always(f"   [>] Threads: 8 (was 4)")

            # OPTIMIZATION 3: Enable compression (50-70% smaller files)
            try:
                self._conn.execute("PRAGMA enable_compression")
                self._conn.execute("SET compression='auto'")
                logger.info("[>] OPTIMIZATION: Compression enabled (50-70% smaller DB)")
                logger.print_always(f"   [>] Compression: Enabled")
            except Exception as e:
                logger.warning(f"Compression not available: {e}")
                logger.warning(f"   [!]  Compression: Not available")

            # OPTIMIZATION 4: Platform-specific optimizations
            self._configure_platform_specific()

            # Enable object cache
            try:
                self._conn.execute("PRAGMA enable_object_cache")
            except Exception:
                pass

            logger.info(f"Connected to DuckDB with {memory_limit}GB RAM, 8 threads, compression")
            logger.print_always(f"   [OK] DuckDB configured successfully")

        except Exception as e:
            logger.error(f"Error connecting to DuckDB: {e}")
            logger.error(f"   [X] DuckDB connection error: {e}")
            import traceback
            traceback.print_exc()
            self._conn = None
            raise

    def _configure_platform_specific(self):
        """OPTIMIZATION: Platform-specific DuckDB configuration."""
        system = platform.system()
        machine = platform.machine()

        if system == "Darwin":  # macOS
            logger.info("[>] OPTIMIZATION: Applying macOS-specific settings")
            # Use system allocator (faster on macOS)
            try:
                self._conn.execute("SET allocator='system'")
            except Exception:
                pass

            # Enable SIMD on Apple Silicon
            if machine == "arm64":
                try:
                    self._conn.execute("SET enable_simd_vectorization=true")
                    logger.info("[>] OPTIMIZATION: Apple Silicon SIMD enabled")
                except Exception:
                    pass

        elif system == "Windows":
            logger.info("[>] OPTIMIZATION: Applying Windows-specific settings")
            # Larger page size for Windows
            try:
                self._conn.execute("SET page_size='16KB'")
            except Exception:
                pass

            # Disable fsync for speed (optimize for performance)
            try:
                self._conn.execute("PRAGMA synchronous=OFF")
            except Exception:
                pass

            # Windows-specific: Reduce thread count to avoid system overload
            # 8 threads on limited-RAM Windows systems causes severe slowdown
            try:
                self._conn.execute("SET threads TO 4")
                logger.print_always("   [>] Windows: Reduced threads to 4 (prevents system overload)")
            except Exception:
                pass

        elif system == "Linux":
            logger.info("[>] OPTIMIZATION: Applying Linux-specific settings")
            # Linux can handle more aggressive threading
            cpu_count = os.cpu_count() or 4
            try:
                self._conn.execute(f"SET threads TO {cpu_count}")
                logger.info(f"[>] OPTIMIZATION: Linux thread count = {cpu_count}")
            except Exception:
                pass

            # Enable mmap for large files
            try:
                self._conn.execute("PRAGMA mmap_size=2147483648")  # 2GB
            except Exception:
                pass

    def _duckdb_has_required_tables(self) -> bool:
        """Verify that DuckDB contains the expected tables."""
        if not self._conn:
            return False

        try:
            rows = self._conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            existing = {row[0].lower() for row in rows}

            # Check for simple schema first (fast optimizer - single 'musicbrainz' table)
            if "musicbrainz" in existing:
                # Verify it has data
                sample = self._conn.execute("SELECT 1 FROM musicbrainz LIMIT 1").fetchone()
                if sample is not None:
                    # Check if this is simple schema (no hot/cold tables)
                    if "musicbrainz_hot" not in existing:
                        self._use_simple_schema = True
                        logger.info("[>] Simple schema detected (fast optimizer)")
                        logger.print_always("   [>] Using SIMPLE SCHEMA (fast optimizer mode)")
                        return True

            # Check for complex schema (old optimizer - multiple tables)
            required_tables = {"musicbrainz_basic", "musicbrainz_fuzzy",
                              "musicbrainz_hot", "musicbrainz_cold",
                              "artist_popularity"}

            if not required_tables.issubset(existing):
                logger.debug("Missing tables: required=%s, existing=%s", required_tables, existing)
                return False

            # Validate tables have data
            for table in required_tables:
                try:
                    sample = self._conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                    if sample is None:
                        logger.debug("Table %s exists but is empty", table)
                        return False
                except Exception as exc:
                    logger.debug("Validation failed for %s: %s", table, exc)
                    return False

            self._use_simple_schema = False
            return True

        except Exception as exc:
            logger.debug("DuckDB validation error: %s", exc)
            return False

    def normalize_base(self, text: str) -> str:
        """Base normalization applied to ALL text before comparison.

        Steps:
        1. Convert to lowercase
        2. Trim whitespace
        3. Collapse internal whitespace
        4. Normalize Unicode punctuation (apostrophes, quotes)
        """
        if not text:
            return ''

        text = text.lower().strip()

        # Normalize Unicode apostrophes
        for unicode_char, ascii_char in UNICODE_APOSTROPHE_MAP.items():
            text = text.replace(unicode_char, ascii_char)

        # Normalize Unicode quotes
        for unicode_char, ascii_char in UNICODE_QUOTE_MAP.items():
            text = text.replace(unicode_char, ascii_char)

        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def normalize_for_matching(self, text: str) -> str:
        """Extended normalization for matching (handles stylized chars).

        Used for artist names like A$AP Rocky -> asap rocky
        """
        text = self.normalize_base(text)

        # Handle stylized characters in word context
        # Only apply $ -> s when surrounded by letters
        result = []
        chars = list(text)
        for i, char in enumerate(chars):
            if char == '$':
                # Check if surrounded by letters (A$AP pattern)
                prev_is_letter = i > 0 and chars[i-1].isalpha()
                next_is_letter = i < len(chars) - 1 and chars[i+1].isalpha()
                if prev_is_letter and next_is_letter:
                    result.append('s')
                    continue
            result.append(char)

        return ''.join(result)

    def clean_text_conservative(self, text: str) -> str:
        """Conservative text cleaning - preserves more semantic content."""
        if not text:
            return ''

        # Apply base normalization first
        text = self.normalize_base(text)

        text = unicodedata.normalize('NFKC', text)
        text = self._paren_pattern.sub('', text)
        text = self._feat_conservative.sub('', text)
        text = self._punct_pattern.sub(' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def clean_text_aggressive(self, text: str) -> str:
        """Aggressive text cleaning - strips more for fuzzy matching.

        Uses NFC normalization to match SQL fuzzy table cleaning.
        Preserves Unicode letters, numbers, and accents.
        """
        if not text:
            return ''

        # Apply base normalization first
        text = self.normalize_base(text)

        # Use NFC to match SQL (was NFKC before Unicode fix)
        text = unicodedata.normalize('NFC', text)
        text = self._paren_pattern.sub('', text)
        text = self._feat_aggressive.sub('', text)
        text = self._punct_pattern.sub('', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def tokenize_artist_credit(self, artist_credit: str) -> set:
        """Split artist credit into normalized tokens for matching.

        Handles various formats:
        - "Rihanna feat. Calvin Harris" -> {"rihanna", "calvin harris"}
        - "A$AP Rocky & Tyler, The Creator" -> {"asap rocky", "tyler the creator"}
        - "Artist (feat. Guest)" -> {"artist", "guest"}
        - "Artist (With Guest Artist)" -> {"artist", "guest artist"}
        """
        if not artist_credit:
            return set()

        # First extract any parenthetical collaborators
        # Pattern: (feat. X), (with X), (ft. X), (featuring X)
        paren_collab_pattern = re.compile(
            r'\((?:feat\.?|featuring|ft\.?|with)\s+([^)]+)\)',
            re.IGNORECASE
        )

        paren_matches = paren_collab_pattern.findall(artist_credit)

        # Remove parenthetical content for main artist extraction
        main_credit = paren_collab_pattern.sub('', artist_credit)

        # Normalize main credit
        normalized = self.normalize_for_matching(main_credit)

        # Split on collaboration indicators
        parts = self._collab_pattern.split(normalized)

        # Clean each part
        tokens = set()
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                # Remove "the" prefix if present
                if cleaned.startswith("the "):
                    cleaned = cleaned[4:]
                tokens.add(cleaned)

        # Add extracted parenthetical collaborators
        for match in paren_matches:
            cleaned = self.normalize_for_matching(match.strip())
            if cleaned:
                if cleaned.startswith("the "):
                    cleaned = cleaned[4:]
                tokens.add(cleaned)

        return tokens

    def artist_tokens_match(self, artist_hint: str, artist_credit: str) -> Tuple[Optional[str], Optional[str]]:
        """Check if artist hint matches any token in artist credit.

        Returns: (match_type, matched_token)
            match_type: "exact", "partial", "fuzzy", or None
            matched_token: The token that matched (if any)
        """
        if not artist_hint or not artist_credit:
            return (None, None)

        hint_normalized = self.normalize_for_matching(artist_hint)
        credit_tokens = self.tokenize_artist_credit(artist_credit)

        # Check for exact match
        if hint_normalized in credit_tokens:
            return ("exact", hint_normalized)

        # Check for partial match (hint is substring or contains token)
        for token in credit_tokens:
            if hint_normalized in token or token in hint_normalized:
                return ("partial", token)

        # Check for fuzzy match if enabled (handles typos like "Beyonce" vs "Beyonce")
        if self.config.fuzzy_artist_enabled and FUZZY_AVAILABLE:
            best_ratio = 0.0
            best_token = None
            for token in credit_tokens:
                ratio = fuzz.ratio(hint_normalized, token) / 100.0
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_token = token

            if best_ratio >= self.config.fuzzy_artist_threshold:
                return ("fuzzy", best_token)

        return (None, None)

    def fuzzy_artist_similarity(self, artist_hint: str, artist_credit: str) -> float:
        """Calculate fuzzy similarity between artist hint and credit.

        Returns score 0-1 where 1 is exact match.
        Used for scoring even when basic matching already succeeded.
        """
        if not FUZZY_AVAILABLE:
            # Fallback: exact match = 1.0, partial = 0.5, none = 0.0
            hint = self.normalize_for_matching(artist_hint) if artist_hint else ""
            credit = self.normalize_for_matching(artist_credit) if artist_credit else ""
            if not hint or not credit:
                return 0.0
            if hint == credit:
                return 1.0
            if hint in credit or credit in hint:
                return 0.5
            return 0.0

        hint_clean = self.normalize_for_matching(artist_hint) if artist_hint else ""
        credit_tokens = self.tokenize_artist_credit(artist_credit)

        if not hint_clean or not credit_tokens:
            return 0.0

        # Find best matching token
        best_ratio = 0.0
        for token in credit_tokens:
            ratio = fuzz.ratio(hint_clean, token) / 100.0
            if ratio > best_ratio:
                best_ratio = ratio

        return best_ratio

    # ========== Token Similarity Methods ==========

    def jaccard_token_similarity(self, s1: str, s2: str) -> float:
        """Calculate Jaccard similarity between token sets of two strings.

        Jaccard = |intersection| / |union|

        Useful for matching titles with extra/missing words:
        - "Song (Remix)" vs "Song" -> high similarity despite extra token
        - "The Song" vs "Song" -> high similarity
        """
        if not s1 or not s2:
            return 0.0

        tokens1 = set(self.clean_text_conservative(s1).lower().split())
        tokens2 = set(self.clean_text_conservative(s2).lower().split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def hybrid_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate hybrid similarity combining token overlap and edit distance.

        Combines:
        - Jaccard token similarity (robust to extra words)
        - Levenshtein edit distance (catches typos/variations)

        Returns weighted combination based on config.
        """
        if not title1 or not title2:
            return 0.0

        # Token-level similarity (Jaccard)
        jaccard = self.jaccard_token_similarity(title1, title2)

        # Character-level similarity (Levenshtein)
        if FUZZY_AVAILABLE:
            clean1 = self.clean_text_conservative(title1).lower()
            clean2 = self.clean_text_conservative(title2).lower()
            levenshtein = fuzz.ratio(clean1, clean2) / 100.0
        else:
            # Fallback: simple character overlap
            clean1 = self.clean_text_conservative(title1).lower()
            clean2 = self.clean_text_conservative(title2).lower()
            if clean1 == clean2:
                levenshtein = 1.0
            elif clean1 in clean2 or clean2 in clean1:
                levenshtein = len(min(clean1, clean2, key=len)) / len(max(clean1, clean2, key=len))
            else:
                levenshtein = 0.0

        # Weighted combination
        hybrid = (
            self.config.token_similarity_weight * jaccard +
            self.config.edit_distance_weight * levenshtein
        )

        return hybrid

    def title_tokens_overlap(self, query_title: str, candidate_title: str) -> tuple:
        """Check how well query tokens are covered by candidate.

        Returns (overlap_ratio, matching_tokens, missing_tokens)

        Used to prefer candidates that contain all query words.
        """
        if not query_title or not candidate_title:
            return (0.0, set(), set())

        query_tokens = set(self.clean_text_conservative(query_title).lower().split())
        candidate_tokens = set(self.clean_text_conservative(candidate_title).lower().split())

        if not query_tokens:
            return (0.0, set(), set())

        matching = query_tokens & candidate_tokens
        missing = query_tokens - candidate_tokens

        overlap_ratio = len(matching) / len(query_tokens)

        return (overlap_ratio, matching, missing)

    # ========== Edge Case Detection Methods ==========

    def is_short_title(self, title: str) -> bool:
        """Check if title is too short to match reliably without hints."""
        cleaned = self.clean_text_conservative(title)
        return len(cleaned) < self.config.min_effective_title_length

    def is_generic_title(self, title: str) -> bool:
        """Check if title is in the generic/boilerplate list."""
        cleaned = self.clean_text_conservative(title)
        return cleaned in self.config.generic_titles

    def is_numeric_title(self, title: str) -> bool:
        """Check if title is purely numeric (e.g., "17", "#1")."""
        cleaned = self.clean_text_conservative(title)
        # Remove # and check if remaining is numeric
        cleaned = cleaned.replace('#', '').strip()
        return cleaned.isdigit() if cleaned else False

    def matches_ambiguous_pattern(self, title: str) -> bool:
        """Check if title matches structurally ambiguous patterns (scenes, numbered tracks, etc.)."""
        cleaned = self.clean_text_conservative(title).lower()
        for pattern in self.config.ambiguous_patterns:
            if re.match(pattern, cleaned, re.IGNORECASE):
                return True
        return False

    def is_ambiguous_title(self, title: str) -> bool:
        """Check if title requires hints for reliable matching.

        Returns True for titles that are:
        - Too short (< min_effective_title_length)
        - In the generic/boilerplate list
        - Purely numeric
        - Matching structural patterns (Scene 3, Act II, etc.)
        """
        return (
            self.is_short_title(title) or
            self.is_generic_title(title) or
            self.is_numeric_title(title) or
            self.matches_ambiguous_pattern(title)
        )

    def is_high_frequency_title(self, title: str, album_hint: Optional[str] = None) -> bool:
        """Check if title has too many candidates to match without strong hints.

        For titles with 50+ candidates, we require BOTH artist AND album hints
        to avoid false positives.
        """
        clean_title = self.clean_text_conservative(title)
        count = self.get_title_candidate_count(clean_title)
        return count >= self.config.high_frequency_threshold

    def get_title_candidate_count(self, clean_title: str) -> int:
        """Get approximate count of candidates for a title.

        Used to detect high-frequency/common titles.
        """
        # Check cache first
        if clean_title in self._title_frequency_cache:
            return self._title_frequency_cache[clean_title]

        if not self._conn:
            return 0

        try:
            # Check both tables
            hot_count = self._conn.execute(
                "SELECT COUNT(*) FROM musicbrainz_hot WHERE recording_clean = ?",
                [clean_title]
            ).fetchone()[0]

            cold_count = self._conn.execute(
                "SELECT COUNT(*) FROM musicbrainz_cold WHERE recording_clean = ?",
                [clean_title]
            ).fetchone()[0]

            count = hot_count + cold_count
            self._title_frequency_cache[clean_title] = count
            return count
        except Exception:
            return 0

    def is_common_title(self, title: str) -> bool:
        """Check if title appears frequently in database."""
        clean_title = self.clean_text_conservative(title)
        count = self.get_title_candidate_count(clean_title)
        return count >= self.config.high_frequency_threshold

    # ========== Fuzzy Matching Methods ==========

    def fuzzy_title_similarity(self, source: str, candidate: str) -> float:
        """Calculate fuzzy similarity between titles.

        Returns score 0-1 where 1 is exact match.
        """
        if not FUZZY_AVAILABLE or not self.config.fuzzy_enabled:
            return 1.0 if source == candidate else 0.0

        source_clean = self.clean_text_conservative(source)
        candidate_clean = self.clean_text_conservative(candidate)

        if not source_clean or not candidate_clean:
            return 0.0

        # Use token_sort_ratio for better matching of reordered words
        ratio = fuzz.token_sort_ratio(source_clean, candidate_clean) / 100.0

        return ratio

    # ========== Phonetic Matching Methods (Phase 5) ==========

    def soundex(self, text: str) -> str:
        """Compute Soundex phonetic code for a string.

        Soundex encodes similar-sounding names identically, useful for matching
        misspelled artist names (e.g., "Brittany Spears" -> "Britney Spears").

        Algorithm:
        1. Keep the first letter
        2. Map remaining consonants to digits based on phonetic groups
        3. Remove vowels and H/W (not useful for sound)
        4. Collapse consecutive identical digits
        5. Pad/truncate to 4 characters

        Returns 4-character Soundex code (letter + 3 digits).
        """
        if not text:
            return "0000"

        # Soundex character mappings
        mapping = {
            'B': '1', 'F': '1', 'P': '1', 'V': '1',
            'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
            'D': '3', 'T': '3',
            'L': '4',
            'M': '5', 'N': '5',
            'R': '6',
            # A, E, I, O, U, H, W, Y are ignored (mapped to '')
        }

        # Clean and uppercase
        text = ''.join(c for c in text.upper() if c.isalpha())
        if not text:
            return "0000"

        # Keep first letter
        first_letter = text[0]
        code = [first_letter]

        # Previous digit (for collapsing duplicates)
        prev_digit = mapping.get(first_letter, '')

        for char in text[1:]:
            digit = mapping.get(char, '')
            if digit and digit != prev_digit:
                code.append(digit)
                if len(code) >= 4:
                    break
            prev_digit = digit if digit else prev_digit

        # Pad to 4 characters
        result = ''.join(code)
        return result.ljust(4, '0')[:4]

    def phonetic_code(self, text: str) -> str:
        """Get cached phonetic code for a string.

        Uses LRU caching to avoid recomputing Soundex codes.
        """
        if not self.config.phonetic_enabled or not text:
            return ""

        # Normalize text
        clean_text = self.clean_text_conservative(text).lower()

        if clean_text in self._phonetic_cache:
            return self._phonetic_cache[clean_text]

        # Compute Soundex code
        code = self.soundex(clean_text)

        # Cache with LRU eviction
        if len(self._phonetic_cache) >= self.config.phonetic_cache_size:
            # Remove oldest entry (simple LRU: remove first added)
            oldest = next(iter(self._phonetic_cache))
            del self._phonetic_cache[oldest]

        self._phonetic_cache[clean_text] = code
        return code

    def phonetic_match(self, s1: str, s2: str) -> bool:
        """Check if two strings have matching phonetic codes.

        Returns True if Soundex codes match (allowing for phonetic variations
        like "Jon" vs "John", "Katy" vs "Katie", etc.).
        """
        if not self.config.phonetic_enabled:
            return False

        code1 = self.phonetic_code(s1)
        code2 = self.phonetic_code(s2)

        return code1 == code2 and code1 != "0000"

    def phonetic_similarity(self, s1: str, s2: str) -> float:
        """Calculate phonetic similarity between two strings.

        Returns a score 0-1 based on:
        - 1.0 if Soundex codes match exactly
        - 0.75 if codes match on first 3 characters
        - 0.5 if codes match on first 2 characters
        - 0.0 otherwise

        This allows graded matching for partial phonetic similarity.
        """
        if not self.config.phonetic_enabled:
            return 0.0

        code1 = self.phonetic_code(s1)
        code2 = self.phonetic_code(s2)

        if code1 == "0000" or code2 == "0000":
            return 0.0

        # Full match
        if code1 == code2:
            return 1.0

        # Partial matches (first N characters)
        if code1[:3] == code2[:3]:
            return 0.75

        if code1[:2] == code2[:2]:
            return 0.5

        return 0.0

    def phonetic_token_similarity(self, text1: str, text2: str) -> float:
        """Calculate phonetic similarity across tokens.

        Splits each string into words and computes average phonetic
        similarity for the best-matching token pairs.

        Useful for multi-word artist names where some words may be
        misspelled or phonetically similar.
        """
        if not self.config.phonetic_enabled:
            return 0.0

        tokens1 = self.clean_text_conservative(text1).lower().split()
        tokens2 = self.clean_text_conservative(text2).lower().split()

        if not tokens1 or not tokens2:
            return 0.0

        # Find best phonetic matches for each token in text1
        total_score = 0.0
        for t1 in tokens1:
            best_match = 0.0
            for t2 in tokens2:
                score = self.phonetic_similarity(t1, t2)
                if score > best_match:
                    best_match = score
            total_score += best_match

        return total_score / len(tokens1)

    def enhanced_artist_similarity(self, artist_hint: str, artist_credit: str) -> float:
        """Calculate enhanced similarity combining fuzzy + phonetic matching.

        Combines:
        - Fuzzy string similarity (Levenshtein/token-based)
        - Phonetic similarity (Soundex-based)

        Returns the maximum of the two scores, with a boost if both are high.
        This catches cases where:
        - Names are spelled similarly (fuzzy wins)
        - Names sound alike but spelled differently (phonetic wins)
        """
        # Get fuzzy similarity
        fuzzy_score = self.fuzzy_artist_similarity(artist_hint, artist_credit)

        # Get phonetic similarity
        phonetic_score = self.phonetic_token_similarity(artist_hint, artist_credit)

        if not self.config.phonetic_enabled:
            return fuzzy_score

        # If both scores are high, apply a boost
        if fuzzy_score >= 0.8 and phonetic_score >= 0.8:
            combined = max(fuzzy_score, phonetic_score) * self.config.phonetic_boost_similar
            return min(combined, 1.0)  # Cap at 1.0

        # Otherwise return the higher score
        return max(fuzzy_score, phonetic_score)

    # ========== Mode Management ==========

    def set_mode(self, mode: str):
        """Set matching mode: 'normal' or 'high_accuracy'.

        high_accuracy enables:
        - Fuzzy matching
        - Lower confidence thresholds when hints align
        - More cascade levels on COLD table
        """
        if mode not in ("normal", "high_accuracy"):
            raise ValueError(f"Invalid mode: {mode}")

        self.config.mode = mode

        if mode == "high_accuracy":
            self.config.fuzzy_enabled = True
            self.config.min_confidence_margin = 300_000  # Lower threshold
        else:
            self.config.fuzzy_enabled = False
            self.config.min_confidence_margin = 500_000

        # Clear cache when mode changes
        self._search_cache.clear()
        self._cache_access_order.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self._title_frequency_cache.clear()
        self._phonetic_cache.clear()  # Phase 5: clear phonetic cache too

        logger.info(f"Matching mode set to: {mode}")

    # Bad result placeholders that should trigger aggressive fallback
    BAD_RESULT_PATTERNS = frozenset([
        '[unknown]', '[no artist]', '[untitled]', '[various artists]',
        'unknown', 'unknown artist', 'various artists', 'va'
    ])

    def _is_bad_result(self, result: str) -> bool:
        """Check if result is a placeholder/bad match that should trigger aggressive fallback."""
        if not result:
            return True
        result_lower = result.lower().strip()
        return result_lower in self.BAD_RESULT_PATTERNS

    def _result_matches_hint(self, result: str, artist_hint: str) -> bool:
        """Check if result contains the artist hint (case-insensitive partial match)."""
        if not result or not artist_hint:
            return False
        result_lower = result.lower()
        hint_lower = artist_hint.lower()
        # Check if any significant part of the hint is in the result
        hint_words = [w for w in hint_lower.split() if len(w) > 2]
        if not hint_words:
            return hint_lower in result_lower
        # Match if at least one significant word matches
        return any(word in result_lower for word in hint_words)

    def _is_better_result(self, new_result: str, old_result: Optional[str], artist_hint: Optional[str]) -> bool:
        """Determine if new_result is better than old_result."""
        # New result is better if old was None or bad
        if not old_result or self._is_bad_result(old_result):
            return not self._is_bad_result(new_result)

        # If artist hint provided, prefer result that matches hint
        if artist_hint:
            old_matches = self._result_matches_hint(old_result, artist_hint)
            new_matches = self._result_matches_hint(new_result, artist_hint)
            if new_matches and not old_matches:
                return True
            if old_matches and not new_matches:
                return False

        # If both match or neither match hint, prefer non-bad result
        return self._is_bad_result(old_result) and not self._is_bad_result(new_result)

    def is_ready(self) -> bool:
        """Check if MusicBrainz is ready for fast searches."""
        ready = self._optimization_complete and self._conn is not None
        return ready

    def is_database_available(self) -> bool:
        """Check if CSV file is available for optimization."""
        return self.csv_file.exists()

    def is_efficiency_mode(self) -> bool:
        """
        Check if running in efficiency mode (simple schema).

        In efficiency mode, HOT/COLD are VIEWS not tables, so batch queries
        against them are extremely slow. Callers should use direct table queries.

        Returns:
            True if efficiency mode (simple schema), False if performance mode
        """
        return self._use_simple_schema

    @trace_call("MBManager.start_optimization_if_needed")
    def start_optimization_if_needed(self, progress_callback: Optional[Callable] = None) -> bool:
        """Start one-time optimization if needed."""
        logger.info("start_optimization_if_needed called")

        if not self.csv_file.exists():
            logger.error("CSV file not available")
            return False

        if self._optimization_complete:
            logger.info("Optimization already complete")
            return True

        if self._optimization_in_progress:
            logger.info("Optimization already in progress")
            return True

        # Check version
        current_version = self._compute_version()
        metadata = self._load_metadata()

        if not current_version:
            logger.warning("Unable to compute CSV version")

        schema_ok = metadata.get("schema_version") == SCHEMA_VERSION

        if metadata.get("version") == current_version and schema_ok and self.duckdb_file.exists():
            logger.info(f"Optimization already complete for version {current_version}")
            self._optimization_complete = True
            self._ready = True
            self._connect_to_duckdb()

            if not self._duckdb_has_required_tables():
                logger.warning("Metadata complete but tables missing - re-optimizing")
                self._optimization_complete = False
                self._ready = False
            else:
                return True

        # Start optimization
        logger.info("Starting optimization thread")
        self._optimization_in_progress = True

        def optimization_worker():
            try:
                self._run_optimization(current_version, progress_callback)
                self._optimization_complete = True
                self._ready = True
                self._optimization_in_progress = False
                logger.info("Optimization completed successfully")
            except Exception as e:
                logger.exception(f"Optimization failed: {e}")
                self._optimization_in_progress = False
                self._optimization_complete = False
                self._ready = False

        thread = threading.Thread(target=optimization_worker, daemon=True)
        thread.start()
        return True

    def cancel_optimization(self):
        """Request cancellation of ongoing optimization."""
        logger.info("Optimization cancellation requested")
        self._cancellation_requested = True

    def is_cancellation_requested(self) -> bool:
        """Check if optimization cancellation was requested."""
        return self._cancellation_requested

    def run_optimization_synchronously(self, progress_callback: Optional[Callable] = None):
        """Run optimization synchronously (blocking call for modal)."""
        self._cancellation_requested = False

        # Use consistent version computation
        current_version = self._compute_version()

        self._optimization_in_progress = True

        try:
            self._run_optimization(current_version, progress_callback)

            if self._cancellation_requested:
                self._optimization_in_progress = False
                self._optimization_complete = False
                self._ready = False
                raise RuntimeError("Optimization cancelled by user")

            self._optimization_complete = True
            self._ready = True
            self._optimization_in_progress = False
        except Exception as e:
            self._optimization_in_progress = False
            self._optimization_complete = False
            self._ready = False
            raise

    @trace_call("MBManager._run_optimization")
    def _run_optimization(self, version: str, progress_callback: Optional[Callable] = None):
        """
        Hardware-adaptive optimization with staging and atomic swap.

        Two modes based on system capabilities:
        - PERFORMANCE: Full optimization with all indexes and HOT/COLD tables
        - EFFICIENCY: Minimal optimization for low-RAM systems

        Both modes produce the same logical schema, just with different
        physical implementations (materialized vs computed).
        """
        start_time = time.time()
        timings = {}

        def progress(message: str, percent: float):
            if self._cancellation_requested:
                raise RuntimeError("Optimization cancelled by user")
            if progress_callback:
                progress_callback(message, percent, start_time)
            logger.info(f"[{percent:5.1f}%] {message}")

        # =================================================================
        # STEP 1: Hardware probe and mode selection
        # =================================================================
        progress("[Step 1] Detecting hardware...", 2)
        logger.print_always(f"\n[Step 1] Detecting hardware...")
        profile = self._probe_hardware_and_select_mode()
        logger.print_always(f"   [OK] RAM: {profile.ram_total_mb}MB, CPUs: {profile.cpu_count}")

        # Determine total steps based on mode for progress labels
        total_steps = 7 if profile.recommended_mode == OptimizationMode.PERFORMANCE else 5
        self._optimization_total_steps = total_steps

        logger.print_always(f"\n{'='*70}")
        logger.print_always(f"[>] MUSICBRAINZ OPTIMIZATION ({profile.recommended_mode.value.upper()} MODE)")
        logger.print_always(f"{'='*70}")
        logger.print_always(f"[i] Version: {version}")
        logger.print_always(f"[i] Schema: {SCHEMA_VERSION}")
        logger.print_always(f"[i] Start: {time.strftime('%H:%M:%S')}")
        logger.print_always(f"[i] Mode: {profile.recommended_mode.value.upper()} ({total_steps} steps)")

        # =================================================================
        # STEP 2: Cleanup and staging setup
        # =================================================================
        progress(f"[Step 2/{total_steps}] Preparing staging database...", 5)
        logger.print_always(f"\n[Step 2/{total_steps}] Preparing staging database...")
        self._cleanup_staging()
        self._connect_to_staging(profile)
        if not self._conn:
            raise RuntimeError("Failed to connect to staging database")
        logger.print_always(f"   [OK] Staging ready")

        try:
            # =============================================================
            # STEP 3: Run mode-specific optimization
            # =============================================================
            if profile.recommended_mode == OptimizationMode.EFFICIENCY:
                track_count = self._run_efficiency_optimization(progress, timings)
            else:
                track_count = self._run_performance_optimization(progress, timings, profile)

            # =============================================================
            # FINAL STEP: Checkpoint, swap, and activate
            # =============================================================
            progress(f"[Step {total_steps}/{total_steps}] Finalizing...", 92)
            logger.print_always(f"\n[Step {total_steps}/{total_steps}] Finalizing database...")

            logger.print_always(f"   [>] Checkpointing...")
            try:
                self._conn.execute("CHECKPOINT")
                logger.print_always(f"   [OK] Checkpoint complete")
            except Exception as e:
                logger.warning(f"   [!] Checkpoint failed (non-fatal): {e}")

            self._conn.close()
            self._conn = None

            progress(f"[Step {total_steps}/{total_steps}] Activating database...", 95)
            logger.print_always(f"   [>] Swapping staging to live...")
            self._atomic_swap_staging_to_live()
            logger.print_always(f"   [OK] Database activated")

            progress(f"[Step {total_steps}/{total_steps}] Saving metadata...", 98)
            logger.print_always(f"   [>] Saving metadata...")
            optimized_at = datetime.now().isoformat() + "Z"
            self._save_metadata(version, optimized_at, track_count=track_count)
            logger.print_always(f"   [OK] Metadata saved")

            # Reconnect to the live database
            logger.print_always(f"   [>] Reconnecting to live database...")
            self._connect_to_duckdb()
            logger.print_always(f"   [OK] Connected")

            progress("[Complete] Optimization finished!", 100)
            total_time = time.time() - start_time

            # Print summary
            self._print_optimization_summary(profile, timings, track_count, total_time)

        except Exception as e:
            # Cleanup on failure
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            self._cleanup_staging()
            raise

    def _run_performance_optimization(
        self,
        progress: Callable,
        timings: Dict[str, float],
        profile: HardwareProfile
    ) -> int:
        """
        Performance mode: Full optimization with all indexes.

        Used on systems with >= 8GB RAM and fast disk.
        Creates: basic, fuzzy, hot, cold, artist_popularity tables.
        """
        logger.print_always("\n[>] Running PERFORMANCE mode optimization (7 steps)...")

        # STEP 3/7: Build basic table + indexes
        progress("[Step 3/7] Building basic table...", 10)
        logger.print_always(f"\n[Step 3/7] Building basic table...")
        phase_start = time.time()
        self._build_basic_table()
        timings['basic_table'] = time.time() - phase_start
        logger.print_always(f"   [OK] Basic table: {timings['basic_table']:.1f}s")

        progress("[Step 3/7] Indexing basic table...", 20)
        logger.print_always(f"   [>] Indexing basic table...")
        phase_start = time.time()
        self._index_basic_table_parallel(
            progress_callback=lambda msg, pct: progress(f"[Step 3/7] Basic index: {msg}", 20 + int(pct * 10))
        )
        timings['basic_indexes'] = time.time() - phase_start
        logger.print_always(f"   [OK] Basic indexes: {timings['basic_indexes']:.1f}s")

        # STEP 4/7: Build fuzzy table + indexes
        progress("[Step 4/7] Building fuzzy table...", 30)
        logger.print_always(f"\n[Step 4/7] Building fuzzy table...")
        phase_start = time.time()
        self._build_fuzzy_table_optimized()
        timings['fuzzy_table'] = time.time() - phase_start
        logger.print_always(f"   [OK] Fuzzy table: {timings['fuzzy_table']:.1f}s")

        progress("[Step 4/7] Indexing fuzzy table...", 40)
        logger.print_always(f"   [>] Indexing fuzzy table...")
        phase_start = time.time()
        self._index_fuzzy_table_parallel(
            progress_callback=lambda msg, pct: progress(f"[Step 4/7] Fuzzy index: {msg}", 40 + int(pct * 10))
        )
        timings['fuzzy_indexes'] = time.time() - phase_start
        logger.print_always(f"   [OK] Fuzzy indexes: {timings['fuzzy_indexes']:.1f}s")

        # STEP 5/7: Build HOT/COLD tiered tables
        progress("[Step 5/7] Building HOT/COLD tables...", 50)
        logger.print_always(f"\n[Step 5/7] Building HOT/COLD tables...")
        phase_start = time.time()
        self._build_tiered_tables(
            progress_callback=lambda msg, pct: progress(f"[Step 5/7] Tiered: {msg}", 50 + int(pct * 20)),
            skip_cold_indexes=profile.skip_cold_indexes
        )
        timings['tiered_tables'] = time.time() - phase_start
        logger.print_always(f"   [OK] HOT/COLD tables: {timings['tiered_tables']:.1f}s")

        # STEP 6/7: Build artist cache + composite indexes
        progress("[Step 6/7] Building artist cache...", 70)
        logger.print_always(f"\n[Step 6/7] Building artist cache...")
        phase_start = time.time()
        self._build_artist_popularity_cache()
        timings['artist_cache'] = time.time() - phase_start
        logger.print_always(f"   [OK] Artist cache: {timings['artist_cache']:.1f}s")

        progress("[Step 6/7] Creating composite indexes...", 80)
        logger.print_always(f"   [>] Creating composite indexes...")
        phase_start = time.time()
        self._create_composite_indexes()
        timings['composite_indexes'] = time.time() - phase_start
        logger.print_always(f"   [OK] Composite indexes: {timings['composite_indexes']:.1f}s")

        # Get track count
        try:
            row = self._conn.execute("SELECT COUNT(*) FROM musicbrainz_basic").fetchone()
            track_count = int(row[0]) if row and row[0] else 0
        except Exception:
            track_count = 0

        return track_count

    def _run_efficiency_optimization(
        self,
        progress: Callable,
        timings: Dict[str, float]
    ) -> int:
        """
        Efficiency mode: Minimal optimization for low-RAM systems.

        Used on systems with < 8GB RAM or slow disk.
        Creates: single 'musicbrainz' table with lowercase columns.
        Skips: indexes (uses table scans), HOT/COLD split, artist cache.

        Search will use DuckDB's vectorized engine for efficient scans.
        """
        logger.print_always("\n[>] Running EFFICIENCY mode optimization (5 steps)...")
        logger.print_always("   [i] Creating minimal schema for low-RAM system")

        # Mark that we're using simple schema
        self._use_simple_schema = True

        # STEP 3/5: Import CSV with lowercase columns only
        progress("[Step 3/5] Importing data...", 15)
        logger.print_always(f"\n[Step 3/5] Importing data from CSV...")
        phase_start = time.time()

        self._conn.execute("DROP TABLE IF EXISTS musicbrainz")

        sql = f"""
            CREATE TABLE musicbrainz AS
            SELECT
                id,
                artist_credit_id,
                artist_mbids,
                artist_credit_name,
                release_mbid,
                release_name,
                recording_mbid,
                recording_name,
                coalesce(score, 0) AS score,
                lower(recording_name) AS recording_lower,
                lower(artist_credit_name) AS artist_lower,
                lower(release_name) AS release_lower
            FROM read_csv_auto('{self.csv_file}', ignore_errors=true)
            WHERE
                recording_name IS NOT NULL AND length(recording_name) > 0 AND
                artist_credit_name IS NOT NULL AND length(artist_credit_name) > 0
        """
        self._conn.execute(sql)

        timings['import'] = time.time() - phase_start
        logger.print_always(f"   [OK] Data import: {timings['import']:.1f}s")

        # Get track count
        try:
            row = self._conn.execute("SELECT COUNT(*) FROM musicbrainz").fetchone()
            track_count = int(row[0]) if row and row[0] else 0
        except Exception:
            track_count = 0

        logger.print_always(f"   [=] Track count: {track_count:,}")

        # STEP 4/5: Create minimal index for fast lookups
        # ALWAYS create index in efficiency mode - it's small and essential for performance
        progress("[Step 4/5] Creating index...", 60)
        logger.print_always(f"\n[Step 4/5] Creating index for fast lookups...")
        phase_start = time.time()

        try:
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mb_recording ON musicbrainz(recording_lower)"
            )
            timings['indexes'] = time.time() - phase_start
            logger.print_always(f"   [OK] Recording index: {timings['indexes']:.1f}s")
        except Exception as e:
            logger.warning(f"   [!] Index creation failed (non-fatal): {e}")
            timings['indexes'] = 0

        # EFFICIENCY MODE: Do NOT create views with PERCENTILE_CONT or regex
        # These views would kill memory on low-RAM systems (each query scans 29M rows)
        # Instead, all code paths check is_efficiency_mode() and use direct table queries
        progress("[Step 4/5] Efficiency mode ready...", 80)
        logger.print_always(f"   [i] Efficiency mode: Using direct table queries (no views)")
        logger.print_always(f"   [i] This avoids expensive PERCENTILE/regex operations")

        return track_count

    # NOTE: _create_efficiency_mode_views() was REMOVED because:
    # 1. It was never called (dead code)
    # 2. It contained dangerous PERCENTILE_CONT views that scan 29M rows per query
    # 3. Efficiency mode now uses direct table queries via is_efficiency_mode() checks
    # See: _batch_search_efficiency_mode() in ultra_fast_csv_processor.py

    def _print_optimization_summary(
        self,
        profile: HardwareProfile,
        timings: Dict[str, float],
        track_count: int,
        total_time: float
    ):
        """Print optimization summary."""
        logger.print_always(f"\n{'='*70}")
        logger.print_always(f"[OK] OPTIMIZATION COMPLETE!")
        logger.print_always(f"{'='*70}")
        logger.print_always(f"   Mode: {profile.recommended_mode.value.upper()}")
        logger.print_always(f"   Total time: {total_time:.1f}s")
        logger.print_always(f"   Tracks: {track_count:,}")
        logger.print_always(f"\n   Phase timings:")
        for phase, duration in timings.items():
            logger.print_always(f"     {phase}: {duration:.1f}s")

        # Show log location
        try:
            from .app_directories import get_user_log_dir
            log_dir = get_user_log_dir()
            logger.print_always(f"\n   [i] Detailed logs: {log_dir}")
            logger.print_always(f"   [i] To enable/disable logs: Edit settings.json -> logging.enabled")
        except Exception:
            pass

        logger.print_always(f"{'='*70}\n")

    # =========================================================================
    # GOLDEN-SET TESTING
    # =========================================================================

    def run_golden_set_test(self) -> Dict[str, Any]:
        """
        Run quick golden-set test to verify database accuracy.

        Tests a small set of known tracks to ensure the database is
        working correctly after optimization. This catches schema issues,
        corrupted data, or broken queries.

        Returns:
            Dict with test results: passed, total, accuracy, failures
        """
        if not self._conn:
            self._connect_to_duckdb()

        # Golden test set: well-known tracks that should exist in any
        # reasonable MusicBrainz dump. These are popular, unambiguous tracks.
        golden_tests = [
            # (track_name, artist_hint, should_find_match)
            ("bohemian rhapsody", "queen", True),
            ("imagine", "john lennon", True),
            ("billie jean", "michael jackson", True),
            ("smells like teen spirit", "nirvana", True),
            ("hotel california", "eagles", True),
            ("stairway to heaven", "led zeppelin", True),
            ("yesterday", "beatles", True),
            ("thriller", "michael jackson", True),
            # These should NOT match (fake tracks)
            ("xyzzy99nonexistent", "fakeartist123", False),
        ]

        results = {
            "passed": 0,
            "failed": 0,
            "total": len(golden_tests),
            "failures": [],
            "accuracy": 0.0,
        }

        logger.print_always("\n[>] Running golden-set validation...")

        for track, artist, should_match in golden_tests:
            try:
                # Quick search using basic lowercase matching
                query = """
                    SELECT recording_name, artist_credit_name
                    FROM musicbrainz_basic
                    WHERE recording_lower LIKE ?
                      AND artist_lower LIKE ?
                    LIMIT 1
                """
                row = self._conn.execute(
                    query, [f"%{track}%", f"%{artist}%"]
                ).fetchone()

                found = row is not None

                if found == should_match:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    results["failures"].append({
                        "track": track,
                        "artist": artist,
                        "expected": should_match,
                        "actual": found,
                    })

            except Exception as e:
                results["failed"] += 1
                results["failures"].append({
                    "track": track,
                    "artist": artist,
                    "error": str(e),
                })

        results["accuracy"] = (
            results["passed"] / results["total"] * 100
            if results["total"] > 0 else 0
        )

        # Report results
        if results["failed"] == 0:
            logger.print_always(f"   [OK] All {results['total']} tests passed")
        else:
            logger.print_always(f"   [!] {results['failed']}/{results['total']} tests failed")
            for f in results["failures"]:
                if "error" in f:
                    logger.print_always(f"       - {f['track']}: {f['error']}")
                else:
                    logger.print_always(
                        f"       - {f['track']}: expected {'match' if f['expected'] else 'no match'}, "
                        f"got {'match' if f['actual'] else 'no match'}"
                    )

        return results

    def validate_database_integrity(self) -> bool:
        """
        Validate that the database has required tables and data.

        Returns:
            True if database is valid, False otherwise
        """
        if not self._conn:
            try:
                self._connect_to_duckdb()
            except Exception:
                return False

        # Check required tables/views exist
        required_objects = ["musicbrainz_basic", "musicbrainz_hot", "musicbrainz_cold"]

        for obj in required_objects:
            try:
                result = self._conn.execute(f"SELECT 1 FROM {obj} LIMIT 1").fetchone()
                if result is None:
                    logger.warning(f"Table/view {obj} is empty")
                    return False
            except Exception as e:
                logger.warning(f"Table/view {obj} not accessible: {e}")
                return False

        # Quick row count check
        try:
            result = self._conn.execute(
                "SELECT COUNT(*) FROM musicbrainz_basic"
            ).fetchone()
            if result[0] < 1000:  # Expect at least 1000 tracks
                logger.warning(f"Database has only {result[0]} tracks - seems incomplete")
                return False
        except Exception:
            return False

        return True

    def _build_basic_table(self):
        """Build basic table with lowercase columns."""
        logger.info("Building basic table...")
        self._conn.execute("DROP TABLE IF EXISTS musicbrainz_basic")

        sql = f"""
            CREATE TABLE musicbrainz_basic AS
            SELECT
                id,
                artist_credit_id,
                artist_mbids,
                artist_credit_name,
                release_mbid,
                release_name,
                recording_mbid,
                recording_name,
                coalesce(score, 0) AS score,
                lower(recording_name) AS recording_lower,
                lower(artist_credit_name) AS artist_lower,
                lower(release_name) AS release_lower
            FROM read_csv_auto('{self.csv_file}')
            WHERE
                recording_name IS NOT NULL AND length(recording_name) > 0 AND
                artist_credit_name IS NOT NULL AND length(artist_credit_name) > 0
        """

        self._conn.execute(sql)
        logger.info("Basic table created")

    def _index_basic_table_parallel(self, progress_callback: Optional[Callable] = None):
        """OPTIMIZATION: Create indexes in PARALLEL using ThreadPoolExecutor.

        NOTE: Intel Macs (x86_64 on macOS) use SEQUENTIAL mode to avoid
        DuckDB connection issues caused by weaker memory ordering.
        """
        import platform

        # Detect Intel Mac - use sequential mode to avoid DuckDB issues
        is_intel_mac = (platform.system() == "Darwin" and platform.machine() == "x86_64")

        indexes = [
            ("idx_basic_rec_lower", "musicbrainz_basic", "recording_lower", 0),
            ("idx_basic_art_lower", "musicbrainz_basic", "artist_lower", 1),
            ("idx_basic_rel_lower", "musicbrainz_basic", "release_lower", 2)
        ]

        if is_intel_mac:
            # INTEL MAC: Use sequential index creation to avoid DuckDB connection issues
            logger.info("[>] INTEL MAC: Creating basic indexes SEQUENTIALLY (avoiding parallel DuckDB issues)")

            completed = 0
            for index_name, table, column, _ in indexes:
                try:
                    self._conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
                    completed += 1
                    if progress_callback:
                        progress_callback(f"{completed}/3 complete", completed / 3.0)
                except Exception as e:
                    logger.error(f"Index creation failed: {index_name} - {e}")

            logger.info("Basic table indexes created (SEQUENTIAL - Intel Mac)")
        else:
            # ARM64/OTHER: Use parallel index creation for performance
            logger.info("[>] OPTIMIZATION: Creating basic indexes in PARALLEL")

            # Create separate connections for each thread (DuckDB requirement)
            def create_index(index_name: str, table: str, column: str, thread_id: int):
                try:
                    # Each thread needs its own connection to the same database
                    conn = duckdb.connect(str(self.duckdb_file))
                    conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
                    conn.close()
                    return (index_name, True, None)
                except Exception as e:
                    return (index_name, False, str(e))

            # Execute in parallel
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(create_index, *idx) for idx in indexes]

                completed = 0
                for future in as_completed(futures):
                    result = future.result()
                    completed += 1
                    if progress_callback:
                        progress_callback(f"{completed}/3 complete", completed / 3.0)

                    if not result[1]:
                        logger.error(f"Index creation failed: {result[0]} - {result[2]}")

            logger.info("Basic table indexes created (PARALLEL)")

    def _build_fuzzy_table_optimized(self):
        """OPTIMIZATION: Build fuzzy table with PURE SQL cleaning (FAST + UNICODE!)."""
        logger.info("[>] OPTIMIZATION: Building fuzzy table with PURE SQL cleaning (Unicode-aware)")

        logger.debug(f"\n   [?] Getting row count from basic table...")
        row_count_result = self._conn.execute("SELECT COUNT(*) FROM musicbrainz_basic").fetchone()
        total_rows = row_count_result[0] if row_count_result else 0
        logger.print_always(f"   [=] Total rows to process: {total_rows:,}")
        logger.info(f"Basic table has {total_rows:,} rows")

        self._conn.execute("DROP TABLE IF EXISTS musicbrainz_fuzzy")

        logger.info(f"\n   [!] Using PURE SQL with Unicode property classes (8x faster + full Unicode support)...")
        logger.info("Using SQL-only text cleaning with Unicode property classes for maximum performance")

        query_start = time.time()

        # Pure SQL text cleaning - UNICODE-AWARE version:
        # 1. NFC normalize for consistency
        # 2. Remove content in parentheses/brackets
        # 3. Remove feat/ft patterns
        # 4. Remove punctuation (Unicode-aware: [^\p{L}\p{N}\s])
        # 5. Normalize whitespace
        # 6. Lowercase
        # NOTE: Uses [\p{L}\p{N}] Unicode property classes to preserve international characters
        sql = """
            CREATE TABLE musicbrainz_fuzzy AS
            SELECT
                id,
                artist_credit_id,
                artist_mbids,
                artist_credit_name,
                release_mbid,
                release_name,
                recording_mbid,
                recording_name,
                score,
                trim(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                regexp_replace(
                                    lower(nfc_normalize(recording_name)),
                                    '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
                                ),
                                '\\s+(feat\\.|featuring|ft\\.|with)\\s+.*', '', 'gi'
                            ),
                            '[^\\p{L}\\p{N}\\s]', '', 'g'
                        ),
                        '\\s+', ' ', 'g'
                    )
                ) AS recording_clean,
                trim(
                    regexp_replace(
                        regexp_replace(
                            regexp_replace(
                                regexp_replace(
                                    lower(nfc_normalize(artist_credit_name)),
                                    '\\([^)]*\\)|\\[[^\\]]*\\]', '', 'g'
                                ),
                                '\\s+(feat\\.|featuring|ft\\.|with)\\s+.*', '', 'gi'
                            ),
                            '[^\\p{L}\\p{N}\\s]', '', 'g'
                        ),
                        '\\s+', ' ', 'g'
                    )
                ) AS artist_clean
            FROM musicbrainz_basic
            WHERE recording_name IS NOT NULL
              AND artist_credit_name IS NOT NULL
              AND length(trim(recording_name)) > 0
              AND length(trim(artist_credit_name)) > 0
        """

        logger.info(f"   [GEAR]  Executing Unicode-aware SQL fuzzy table creation...")
        self._conn.execute(sql)

        query_time = time.time() - query_start
        logger.print_always(f"   [OK] Query completed in {query_time:.1f}s (8x faster + Unicode support!)")

        # Verify result count
        result_count = self._conn.execute("SELECT COUNT(*) FROM musicbrainz_fuzzy").fetchone()[0]
        logger.print_always(f"   [=] Fuzzy table rows: {result_count:,}")
        logger.info(f"Fuzzy table created with {result_count:,} rows in {query_time:.1f}s (Unicode-aware SQL)")

    def _index_fuzzy_table_parallel(self, progress_callback: Optional[Callable] = None):
        """OPTIMIZATION: Create fuzzy indexes in PARALLEL.

        NOTE: Intel Macs (x86_64 on macOS) use SEQUENTIAL mode to avoid
        DuckDB connection issues caused by weaker memory ordering.
        """
        import platform

        # Detect Intel Mac - use sequential mode to avoid DuckDB issues
        is_intel_mac = (platform.system() == "Darwin" and platform.machine() == "x86_64")

        indexes = [
            ("idx_fuzzy_rec_clean", "musicbrainz_fuzzy", "recording_clean", 0),
            ("idx_fuzzy_art_clean", "musicbrainz_fuzzy", "artist_clean", 1)
        ]

        if is_intel_mac:
            # INTEL MAC: Use sequential index creation to avoid DuckDB connection issues
            logger.info("[>] INTEL MAC: Creating fuzzy indexes SEQUENTIALLY (avoiding parallel DuckDB issues)")

            completed = 0
            for index_name, table, column, _ in indexes:
                try:
                    self._conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
                    completed += 1
                    if progress_callback:
                        progress_callback(f"{completed}/2 complete", completed / 2.0)
                except Exception as e:
                    logger.error(f"Index creation failed: {index_name} - {e}")

            logger.info("Fuzzy table indexes created (SEQUENTIAL - Intel Mac)")
        else:
            # ARM64/OTHER: Use parallel index creation for performance
            logger.info("[>] OPTIMIZATION: Creating fuzzy indexes in PARALLEL")

            def create_index(index_name: str, table: str, column: str, thread_id: int):
                try:
                    conn = duckdb.connect(str(self.duckdb_file))
                    conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})")
                    conn.close()
                    return (index_name, True, None)
                except Exception as e:
                    return (index_name, False, str(e))

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(create_index, *idx) for idx in indexes]

                completed = 0
                for future in as_completed(futures):
                    result = future.result()
                    completed += 1
                    if progress_callback:
                        progress_callback(f"{completed}/2 complete", completed / 2.0)

                    if not result[1]:
                        logger.error(f"Index creation failed: {result[0]} - {result[2]}")

            logger.info("Fuzzy table indexes created (PARALLEL)")

    def _build_tiered_tables(
        self,
        progress_callback: Optional[Callable] = None,
        skip_cold_indexes: bool = False
    ):
        """OPTIMIZATION: Build HOT/COLD tiered tables for faster searches.

        Args:
            progress_callback: Optional callback for progress updates
            skip_cold_indexes: If True, skip COLD table indexes (low-RAM optimization)
        """
        logger.info("[>] OPTIMIZATION: Building HOT/COLD tiered tables")

        if progress_callback:
            progress_callback("Analyzing score distribution", 0.0)

        # Drop existing tables
        self._conn.execute("DROP TABLE IF EXISTS musicbrainz_hot")
        self._conn.execute("DROP TABLE IF EXISTS musicbrainz_cold")

        # Calculate threshold score once to avoid recomputation
        # CRITICAL FIX: Lower score = more established track (earlier MusicBrainz entry)
        # So HOT table should contain tracks with LOWER scores (the 15th percentile)
        threshold_result = self._conn.execute("""
            SELECT PERCENTILE_CONT(0.15) WITHIN GROUP (ORDER BY score)
            FROM musicbrainz_fuzzy
        """).fetchone()
        threshold_score = threshold_result[0] if threshold_result else 0

        logger.info(f"HOT/COLD threshold score: {threshold_score}")

        if progress_callback:
            progress_callback("Creating HOT table (top 15% most established)", 0.2)

        # Hot table: Top 15% most established tracks (LOWEST scores = oldest/most established)
        # CRITICAL FIX: Use <= threshold and ORDER BY score ASC
        self._conn.execute(f"""
            CREATE TABLE musicbrainz_hot AS
            SELECT * FROM musicbrainz_fuzzy
            WHERE score <= {threshold_score}
            ORDER BY score ASC
        """)

        if progress_callback:
            progress_callback("Creating COLD table (remaining 85%)", 0.5)

        # Cold table: Remaining tracks (less established, higher scores)
        # CRITICAL FIX: Use > threshold
        self._conn.execute(f"""
            CREATE TABLE musicbrainz_cold AS
            SELECT * FROM musicbrainz_fuzzy
            WHERE score > {threshold_score}
        """)

        if progress_callback:
            progress_callback("Indexing HOT table", 0.7)

        # Index hot table aggressively (gets searched most)
        self._conn.execute("CREATE INDEX idx_hot_rec_clean ON musicbrainz_hot(recording_clean)")
        self._conn.execute("CREATE INDEX idx_hot_art_clean ON musicbrainz_hot(artist_clean)")
        self._conn.execute("CREATE INDEX idx_hot_score ON musicbrainz_hot(score)")

        # Index cold table (skip on low-RAM systems for faster optimization)
        if skip_cold_indexes:
            logger.print_always("   [>] Skipping COLD indexes (low-RAM/slow-disk mode)")
        else:
            if progress_callback:
                progress_callback("Indexing COLD table", 0.9)

            # Index cold table with prefix indexes (less frequently searched)
            self._conn.execute("CREATE INDEX idx_cold_rec_prefix ON musicbrainz_cold(SUBSTRING(recording_clean, 1, 3))")
            self._conn.execute("CREATE INDEX idx_cold_art_prefix ON musicbrainz_cold(SUBSTRING(artist_clean, 1, 3))")

        # Log counts
        hot_count = self._conn.execute("SELECT COUNT(*) FROM musicbrainz_hot").fetchone()[0]
        cold_count = self._conn.execute("SELECT COUNT(*) FROM musicbrainz_cold").fetchone()[0]

        logger.info(f"HOT table: {hot_count:,} rows, COLD table: {cold_count:,} rows")

        # Phase 4: Build FTS index for COLD table if enabled (skip on low-RAM)
        if self.config.fts_enabled and not skip_cold_indexes:
            self._build_fts_index(progress_callback)

        if progress_callback:
            progress_callback("Tiered tables complete", 1.0)

    def _build_fts_index(self, progress_callback: Optional[Callable] = None) -> None:
        """Phase 4: Build Full-Text Search index on COLD table for fast substring search.

        Uses DuckDB's FTS extension to speed up LIKE '%X%' queries on the COLD table.
        Falls back to LIKE queries if FTS fails.
        """
        logger.info("Building FTS index on COLD table...")

        if progress_callback:
            progress_callback("Building FTS index...", 0.95)

        try:
            # Install and load FTS extension
            self._conn.execute("INSTALL fts")
            self._conn.execute("LOAD fts")

            # Drop existing FTS index if any
            try:
                self._conn.execute("PRAGMA drop_fts_index('musicbrainz_cold')")
            except Exception:
                pass  # Index may not exist

            # Create FTS index on recording_clean and artist_credit_name
            # Using no stemmer for exact matching, lowercase, and accent stripping
            self._conn.execute("""
                PRAGMA create_fts_index(
                    'musicbrainz_cold',
                    'id',
                    'recording_clean', 'artist_credit_name',
                    stemmer='none',
                    lower=1,
                    strip_accents=1
                )
            """)

            self._fts_available = True
            logger.info("FTS index built successfully on COLD table")

        except Exception as e:
            logger.warning(f"FTS index creation failed (will use LIKE fallback): {e}")
            self._fts_available = False

    def _search_fts_cold(self, clean_track: str, artist_hint: Optional[str] = None,
                          album_hint: Optional[str] = None) -> Optional[str]:
        """Phase 4: Search COLD table using FTS instead of LIKE.

        Uses BM25 scoring for better relevance ranking.
        Falls back to LIKE if FTS is not available.

        Args:
            clean_track: Cleaned track name to search
            artist_hint: Optional artist name for filtering
            album_hint: Optional album name for filtering

        Returns:
            Best matching artist credit name, or None if no match
        """
        if not self._fts_available:
            # Fall back to standard LIKE-based search
            return self._search_fuzzy_contains(clean_track, artist_hint, album_hint, use_hot=False)

        try:
            # Build FTS query - use the track name as the search term
            # Split into tokens for AND-style matching
            fts_query = clean_track.replace(' ', ' AND ')

            # FTS search with BM25 scoring
            sql = f"""
                SELECT c.artist_credit_name, c.release_name, c.score,
                       fts_main_musicbrainz_cold.match_bm25(
                           c.id, ?, fields := 'recording_clean'
                       ) AS fts_score
                FROM musicbrainz_cold c
                WHERE fts_main_musicbrainz_cold.match_bm25(
                    c.id, ?, fields := 'recording_clean'
                ) IS NOT NULL
                ORDER BY fts_score DESC, c.score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            rows = self._conn.execute(sql, [fts_query, fts_query]).fetchall()

            if rows:
                return self._choose_candidate(
                    [(r[0], r[1], r[2]) for r in rows],  # artist, release, score
                    artist_hint, album_hint, clean_track
                )
            return None

        except Exception as e:
            logger.debug(f"FTS search failed, falling back to LIKE: {e}")
            # Fall back to LIKE search
            if self.config.fts_fallback_to_like:
                return self._search_fuzzy_contains(clean_track, artist_hint, album_hint, use_hot=False)
            return None

    def _build_artist_popularity_cache(self):
        """OPTIMIZATION: Build artist popularity lookup table."""
        logger.info("[>] OPTIMIZATION: Building artist popularity cache")

        self._conn.execute("DROP TABLE IF EXISTS artist_popularity")

        # CRITICAL FIX: Use MIN(score) not MAX(score)
        # Lower score = more established artist (earlier MusicBrainz entries)
        self._conn.execute("""
            CREATE TABLE artist_popularity AS
            SELECT
                artist_credit_name,
                MIN(score) as popularity_score,
                COUNT(*) as track_count
            FROM musicbrainz_basic
            GROUP BY artist_credit_name
        """)

        self._conn.execute("CREATE INDEX idx_artist_pop ON artist_popularity(artist_credit_name)")

        count = self._conn.execute("SELECT COUNT(*) FROM artist_popularity").fetchone()[0]
        logger.info(f"Artist popularity cache built: {count:,} artists")

    def _create_composite_indexes(self):
        """OPTIMIZATION: Create composite indexes for multi-column queries."""
        logger.info("[>] OPTIMIZATION: Creating composite indexes")

        # Composite index for queries with album hints (hot table)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hot_rec_album
            ON musicbrainz_hot(recording_clean, release_name)
        """)

        # Composite index for queries with artist hints (hot table)
        # Note: hot/cold tables use artist_clean, not artist_lower
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hot_rec_artist
            ON musicbrainz_hot(recording_clean, artist_clean)
        """)

        logger.info("Composite indexes created")

    def _search_simple(self, track_name: str, artist_hint: Optional[str] = None, album_hint: Optional[str] = None) -> Optional[str]:
        """
        Simple search for fast optimizer schema (single 'musicbrainz' table).

        Uses single table scan with CASE ordering instead of complex hot/cold cascade.
        Typical search time: 500ms-3s on low-RAM systems.
        """
        if not self._conn:
            return None

        # Clean inputs
        track_lower = track_name.lower().strip()
        artist_lower = artist_hint.lower().strip() if artist_hint else None
        album_lower = album_hint.lower().strip() if album_hint else None

        # Build conditions
        conditions = ["recording_lower LIKE ?"]
        params = [f"%{track_lower}%"]

        if artist_lower:
            conditions.append("artist_lower LIKE ?")
            params.append(f"%{artist_lower}%")

        if album_lower:
            conditions.append("release_lower LIKE ?")
            params.append(f"%{album_lower}%")

        where_clause = " AND ".join(conditions)

        # Single scan query with CASE ordering (exact > prefix > contains)
        sql = f"""
            SELECT artist_credit_name
            FROM musicbrainz
            WHERE {where_clause}
            ORDER BY
                CASE
                    WHEN recording_lower = ? THEN 1
                    WHEN recording_lower LIKE ? THEN 2
                    ELSE 3
                END,
                score ASC
            LIMIT 1
        """

        # Add params for ORDER BY CASE
        params.extend([track_lower, f"{track_lower}%"])

        try:
            row = self._conn.execute(sql, params).fetchone()
            if row:
                return row[0]
            return None
        except Exception as e:
            logger.error(f"Simple search error: {e}")
            return None

    @trace_call("MBManager.search")
    def search(self, track_name: str, artist_hint: Optional[str] = None, album_hint: Optional[str] = None) -> Optional[str]:
        """
        OPTIMIZATION: Search with LRU caching and HOT/COLD cascade.
        """
        search_start = time.time()

        if not self.is_ready():
            logger.warning("Search aborted - not ready")
            return None

        if not track_name or not track_name.strip():
            return None

        if album_hint and str(album_hint).strip().lower() in {"nan", "none", "null", ""}:
            album_hint = None

        # OPTIMIZATION: Check LRU cache first
        cache_key = (
            track_name.lower().strip(),
            (artist_hint or "").lower().strip(),
            (album_hint or "").lower().strip()
        )

        if cache_key in self._search_cache:
            # Cache hit!
            self._cache_hits += 1
            # Move to end (most recently used)
            self._cache_access_order.remove(cache_key)
            self._cache_access_order.append(cache_key)

            result = self._search_cache[cache_key]
            elapsed = (time.time() - search_start) * 1000
            logger.debug(f"[>] CACHE HIT: '{track_name}' -> '{result}' in {elapsed:.2f}ms")
            return result

        # Cache miss - do normal search
        self._cache_misses += 1

        # SIMPLE SCHEMA MODE: Use fast single-table search
        if self._use_simple_schema:
            result = self._search_simple(track_name, artist_hint, album_hint)
            # Add to cache
            if len(self._search_cache) >= LRU_CACHE_SIZE:
                oldest_key = self._cache_access_order.popleft()
                del self._search_cache[oldest_key]
            self._search_cache[cache_key] = result
            self._cache_access_order.append(cache_key)
            elapsed = (time.time() - search_start) * 1000
            logger.debug(f"Simple search for '{track_name}' completed in {elapsed:.2f}ms (result: {result})")
            return result

        # COMPLEX SCHEMA MODE: Try conservative cleaning first
        result = self._search_with_cleaning(track_name, artist_hint, album_hint, conservative=True)

        # Also try aggressive cleaning if:
        # 1. No result found, OR
        # 2. Result is a "bad" placeholder like "[unknown]", OR
        # 3. Artist hint provided but result doesn't match it
        should_try_aggressive = (
            not result or
            self._is_bad_result(result) or
            (artist_hint and not self._result_matches_hint(result, artist_hint))
        )

        if should_try_aggressive:
            aggressive_result = self._search_with_cleaning(track_name, artist_hint, album_hint, conservative=False)
            # Use aggressive result if it's better
            if aggressive_result and self._is_better_result(aggressive_result, result, artist_hint):
                logger.debug(f"Aggressive cleaning found better result: '{aggressive_result}' vs conservative: '{result}'")
                result = aggressive_result

        # Add to cache (evict oldest if needed)
        if len(self._search_cache) >= LRU_CACHE_SIZE:
            oldest_key = self._cache_access_order.popleft()
            del self._search_cache[oldest_key]

        self._search_cache[cache_key] = result
        self._cache_access_order.append(cache_key)

        elapsed = (time.time() - search_start) * 1000
        logger.debug(f"Search for '{track_name}' completed in {elapsed:.2f}ms (result: {result})")

        return result

    def _search_with_cleaning(self, track_name: str, artist_hint: Optional[str], album_hint: Optional[str], conservative: bool) -> Optional[str]:
        """Search with text cleaning."""
        if conservative:
            clean_track = self.clean_text_conservative(track_name)
        else:
            clean_track = self.clean_text_aggressive(track_name)

        if not clean_track:
            return None

        # Clean artist hint for matching
        clean_artist_hint = self.clean_text_conservative(artist_hint) if artist_hint else None

        # EDGE CASE: Ambiguous titles (short, generic, numbered) require artist hint
        # Without artist hint, return None to avoid false positives
        if self.is_ambiguous_title(track_name) and not clean_artist_hint:
            logger.debug(f"Ambiguous title '{track_name}' requires artist hint - skipping search")
            return None

        # EDGE CASE: High-frequency titles (50+ candidates) require album hint
        # Without album hint, the chance of false positive is too high
        if self.is_high_frequency_title(track_name) and not album_hint:
            # Allow if we have artist hint, but log warning
            if clean_artist_hint:
                logger.debug(f"High-frequency title '{track_name}' has only artist hint (no album) - proceeding with caution")
            else:
                logger.debug(f"High-frequency title '{track_name}' requires album hint - skipping search")
                return None

        # CRITICAL FIX: When album OR artist hint is provided, search BOTH hot and cold tables
        # The correct track might be in COLD with lower base score but should win with album/artist bonus
        # This fixes the bug where LCD Soundsystem's "I Can Change" was in COLD table but
        # Saddam Hussein's version was returned from HOT table due to cascade search stopping early
        if album_hint or clean_artist_hint:
            logger.debug(f"[?] Hint provided (artist={clean_artist_hint}, album={album_hint}): searching BOTH hot and cold tables")
            # Try exact match in both tables combined
            result = self._search_fuzzy_exact_combined(clean_track, clean_artist_hint, album_hint)
            if result:
                return result
            # Try prefix match in both tables combined
            result = self._search_fuzzy_prefix_combined(clean_track, clean_artist_hint, album_hint)
            if result:
                return result
            # Try contains match in both tables combined
            result = self._search_fuzzy_contains_combined(clean_track, clean_artist_hint, album_hint)
            if result:
                return result

        # OPTIMIZATION: Standard cascade for searches without album hint
        # Phase 4: Use FTS for cold_fuzzy_contains when available (faster than LIKE)
        cold_contains_method = (
            lambda: self._search_fts_cold(clean_track, clean_artist_hint, album_hint)
            if self._fts_available and self.config.fts_enabled
            else self._search_fuzzy_contains(clean_track, clean_artist_hint, album_hint, use_hot=False)
        )
        search_methods = [
            ("hot_fuzzy_exact", lambda: self._search_fuzzy_exact(clean_track, clean_artist_hint, album_hint, use_hot=True)),
            ("hot_fuzzy_prefix", lambda: self._search_fuzzy_prefix(clean_track, clean_artist_hint, album_hint, use_hot=True)),
            ("hot_fuzzy_contains", lambda: self._search_fuzzy_contains(clean_track, clean_artist_hint, album_hint, use_hot=True)),
            ("cold_fuzzy_exact", lambda: self._search_fuzzy_exact(clean_track, clean_artist_hint, album_hint, use_hot=False)),
            ("cold_fuzzy_prefix", lambda: self._search_fuzzy_prefix(clean_track, clean_artist_hint, album_hint, use_hot=False)),
            ("cold_fts_contains", cold_contains_method),  # Phase 4: FTS-accelerated search
            ("reverse_contains", lambda: self._search_reverse_contains(clean_track, clean_artist_hint, album_hint))
        ]

        for method_name, method in search_methods:
            try:
                result = method()
                if result:
                    return result
            except Exception as e:
                logger.exception(f"Search method {method_name} failed: {e}")
                continue

        return None

    def _search_fuzzy_exact(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str], use_hot: bool = True) -> Optional[str]:
        """OPTIMIZATION: Exact match with HOT/COLD split."""
        table = "musicbrainz_hot" if use_hot else "musicbrainz_cold"

        # CRITICAL FIX: When artist_hint is provided, prioritize artist matches in SQL ORDER BY
        # This ensures artist matches appear in results even if they have lower base scores
        if artist_hint and album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    (release_name ILIKE ?) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%", f"%{album_hint}%"]
        elif artist_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%"]
        elif album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY
                    (release_name ILIKE ?) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{album_hint}%"]
        else:
            # CRITICAL FIX: ORDER BY score ASC - lower score = more established track
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track]

        try:
            rows = self._conn.execute(sql, params).fetchall()
            return self._choose_candidate(rows, artist_hint, album_hint, clean_track)
        except Exception:
            logger.exception(f"fuzzy_exact query failed for '{clean_track}'")
            return None

    def _search_fuzzy_prefix(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str], use_hot: bool = True) -> Optional[str]:
        """OPTIMIZATION: Prefix match with HOT/COLD split."""
        table = "musicbrainz_hot" if use_hot else "musicbrainz_cold"

        # CRITICAL FIX: When artist_hint is provided, prioritize artist matches in SQL ORDER BY
        if artist_hint and album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%", f"%{album_hint}%"]
        elif artist_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%"]
        elif album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{album_hint}%"]
        else:
            # CRITICAL FIX: ORDER BY score ASC - lower score = more established track
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY length(recording_clean) ASC, score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track]

        try:
            rows = self._conn.execute(sql, params).fetchall()
            return self._choose_candidate(rows, artist_hint, album_hint, clean_track)
        except Exception:
            return None

    def _search_fuzzy_contains(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str], use_hot: bool = True) -> Optional[str]:
        """OPTIMIZATION: Contains match with HOT/COLD split."""
        if len(clean_track) < 3:
            return None

        table = "musicbrainz_hot" if use_hot else "musicbrainz_cold"

        # CRITICAL FIX: When artist_hint is provided, prioritize artist matches in SQL ORDER BY
        if artist_hint and album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%", f"%{album_hint}%"]
        elif artist_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%"]
        elif album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{album_hint}%"]
        else:
            # CRITICAL FIX: ORDER BY score ASC - lower score = more established track
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY length(recording_clean) ASC, score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track]

        try:
            rows = self._conn.execute(sql, params).fetchall()
            return self._choose_candidate(rows, artist_hint, album_hint, clean_track)
        except Exception:
            return None

    def _search_reverse_contains(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str]) -> Optional[str]:
        """Reverse containment search (searches HOT table only)."""
        if len(clean_track) < 3:
            return None

        # CRITICAL FIX: When artist_hint is provided, prioritize artist matches in SQL ORDER BY
        if artist_hint and album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM musicbrainz_hot
                WHERE length(recording_clean) >= 3
                  AND length(recording_clean) <= length(?)
                  AND ? LIKE '%' || recording_clean || '%'
                  AND length(?) <= {self._reverse_length_ratio} * length(recording_clean)
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, clean_track, clean_track, f"%{artist_hint}%", f"%{album_hint}%"]
        elif artist_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM musicbrainz_hot
                WHERE length(recording_clean) >= 3
                  AND length(recording_clean) <= length(?)
                  AND ? LIKE '%' || recording_clean || '%'
                  AND length(?) <= {self._reverse_length_ratio} * length(recording_clean)
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    length(recording_clean) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, clean_track, clean_track, f"%{artist_hint}%"]
        elif album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM musicbrainz_hot
                WHERE length(recording_clean) >= 3
                  AND length(recording_clean) <= length(?)
                  AND ? LIKE '%' || recording_clean || '%'
                  AND length(?) <= {self._reverse_length_ratio} * length(recording_clean)
                ORDER BY
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, clean_track, clean_track, f"%{album_hint}%"]
        else:
            # CRITICAL FIX: ORDER BY score ASC - lower score = more established track
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM musicbrainz_hot
                WHERE length(recording_clean) >= 3
                  AND length(recording_clean) <= length(?)
                  AND ? LIKE '%' || recording_clean || '%'
                  AND length(?) <= {self._reverse_length_ratio} * length(recording_clean)
                ORDER BY length(recording_clean) DESC, score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, clean_track, clean_track]

        try:
            rows = self._conn.execute(sql, params).fetchall()
            return self._choose_candidate(rows, artist_hint, album_hint, clean_track, prefer_longest=True)
        except Exception:
            return None

    def _choose_candidate(self, rows: List[Tuple], artist_hint: Optional[str], album_hint: Optional[str],
                         track_clean: str, prefer_longest: bool = False) -> Optional[str]:
        """Pick the best artist candidate from query results."""
        if not rows:
            return None

        best_aligned = None
        best_aligned_score = float('-inf')
        best_overall = None
        best_overall_score = float('-inf')

        # DEBUG: Log all candidates with scores
        logger.debug(f"[?] Evaluating {len(rows)} candidates for track '{track_clean}' with artist hint '{artist_hint}', album hint '{album_hint}'")

        for i, row in enumerate(rows, 1):
            artist_credit, release_name, score = (row + (0,))[:3]
            candidate_score = self._score_candidate(artist_credit, release_name, score or 0, track_clean, artist_hint, album_hint)

            # DEBUG: Log each candidate evaluation
            matches_album = self._result_matches_album(release_name, album_hint, track_clean)
            logger.debug(f"   Candidate {i}: '{artist_credit}' from '{release_name}'")
            logger.debug(f"      Base score: {score}, Final score: {candidate_score:,.0f}, Matches album: {matches_album}")

            if candidate_score > best_overall_score:
                best_overall = row
                best_overall_score = candidate_score

            if matches_album:
                if candidate_score > best_aligned_score:
                    best_aligned = row
                    best_aligned_score = candidate_score

        if best_aligned:
            logger.debug(f"[OK] Selected ALBUM-ALIGNED candidate: '{best_aligned[0]}' (score: {best_aligned_score:,.0f})")
            return best_aligned[0]

        if best_overall:
            logger.debug(f"[OK] Selected BEST OVERALL candidate: '{best_overall[0]}' (score: {best_overall_score:,.0f})")
        return best_overall[0] if best_overall else None

    def _score_candidate(self, artist_credit: str, release_name: str, score: float, track_clean: str, artist_hint: Optional[str] = None, album_hint: Optional[str] = None) -> float:
        """Score a candidate match with artist and album hint consideration."""
        release_clean = self.clean_text_conservative(release_name) if release_name else ''
        artist_clean = self.clean_text_conservative(artist_credit)

        # CRITICAL FIX: Invert score semantics
        # Lower MusicBrainz score = more established track = should have HIGHER weight
        # Use 5M as baseline so all weights stay positive
        MAX_SCORE = 5_000_000
        weight = MAX_SCORE - float(score)
        score_breakdown = [f"base={MAX_SCORE}-{score}={weight:.0f}"]

        # CRITICAL FIX: Artist popularity now uses MIN(score), so lower = more established
        # Invert it the same way
        popularity_score = self._get_artist_popularity_score(artist_credit)
        inverted_popularity = MAX_SCORE - popularity_score if popularity_score > 0 else 0
        weight += inverted_popularity
        if inverted_popularity > 0:
            score_breakdown.append(f"popularity=+{inverted_popularity:.0f}")

        # CRITICAL FIX: Add MASSIVE bonus for artist matches
        # This ensures that when we have artist info, we strongly prefer that artist
        if artist_hint and artist_credit:
            artist_hint_clean = self.clean_text_conservative(artist_hint)
            if artist_hint_clean:
                # Use token-based matching for better accuracy
                match_type, _ = self.artist_tokens_match(artist_hint, artist_credit)

                if match_type == "exact":
                    weight += self.config.artist_exact_bonus  # 5M for exact match
                    score_breakdown.append(f"artist_exact=+{self.config.artist_exact_bonus/1_000_000:.0f}M")
                elif match_type == "partial":
                    weight += self.config.artist_partial_bonus  # 4M for partial match
                    score_breakdown.append(f"artist_partial=+{self.config.artist_partial_bonus/1_000_000:.0f}M")
                elif match_type == "fuzzy":
                    # Tiered fuzzy + phonetic matching (Phase 1.3 + Phase 5)
                    # Higher similarity = higher confidence = larger bonus
                    # Now uses enhanced_artist_similarity which combines fuzzy + phonetic
                    fuzzy_sim = self.enhanced_artist_similarity(artist_hint, artist_credit)

                    if fuzzy_sim >= self.config.fuzzy_artist_high_threshold:
                        # High confidence fuzzy match (>=90%)
                        fuzzy_bonus = int(self.config.artist_fuzzy_bonus * fuzzy_sim * self.config.fuzzy_artist_high_multiplier)
                        weight += fuzzy_bonus
                        score_breakdown.append(f"artist_fuzzy_high=+{fuzzy_bonus/1_000_000:.1f}M({fuzzy_sim:.0%})")
                    elif fuzzy_sim >= self.config.fuzzy_artist_medium_threshold:
                        # Medium confidence fuzzy match (>=75%, <90%)
                        fuzzy_bonus = int(self.config.artist_fuzzy_bonus * fuzzy_sim * self.config.fuzzy_artist_medium_multiplier)
                        weight += fuzzy_bonus
                        score_breakdown.append(f"artist_fuzzy_med=+{fuzzy_bonus/1_000_000:.1f}M({fuzzy_sim:.0%})")
                    # Below medium threshold: no bonus (not confident enough)
                else:
                    # Legacy fallback: simple substring check
                    if artist_hint_clean in artist_clean or artist_clean in artist_hint_clean:
                        weight += self.config.artist_partial_bonus
                        score_breakdown.append(f"artist_partial_legacy=+{self.config.artist_partial_bonus/1_000_000:.0f}M")

        # CRITICAL FIX: Add MASSIVE bonus for album matches (fixes "808s & Heartbreak" issue)
        # This ensures that when we have album info, we strongly prefer tracks from that album
        if album_hint and release_name:
            album_clean = self.clean_text_conservative(album_hint)
            if album_clean:
                # Exact album match = HIGHEST priority
                if album_clean == release_clean:
                    weight += 5_000_000  # Massive bonus for exact album match
                    score_breakdown.append(f"album_exact=+5M")
                # Partial album match = HIGH priority
                elif album_clean in release_clean or release_clean in album_clean:
                    weight += 3_000_000  # Large bonus for partial album match
                    score_breakdown.append(f"album_partial=+3M")
        # CRITICAL FIX: Only apply title match bonus when NO album hint provided
        # When we have album info, we should ONLY reward album matches
        # This prevents "Amazing (Capshun remix)" from winning over "808s & Heartbreak"
        elif not album_hint:
            # Bonus for exact title match (single releases only)
            if track_clean and release_clean == track_clean:
                weight += 1_500_000
                score_breakdown.append(f"title_exact=+1.5M")
            elif track_clean and track_clean in release_clean:
                weight += 750_000
                score_breakdown.append(f"title_contains=+750K")

        # Token-level title similarity bonus (Phase 1.1 enhancement)
        # This helps match titles with word reordering or minor differences
        if self.config.token_similarity_enabled and track_clean and release_clean:
            hybrid_sim = self.hybrid_title_similarity(track_clean, release_clean)
            if hybrid_sim >= self.config.token_similarity_threshold:
                # Scale bonus by similarity level
                hybrid_bonus = int(self.config.hybrid_similarity_bonus * hybrid_sim)
                weight += hybrid_bonus
                score_breakdown.append(f"hybrid_sim=+{hybrid_bonus/1_000_000:.1f}M({hybrid_sim:.0%})")

        # Penalties for cover/tribute/karaoke keywords
        penalty_keywords_release = [
            'cover', 'tribute', 'karaoke', 'lounge', 'rendition', 'interpretation',
            'backing track', 'instrumental', 'session', 'workshop', 'demo', 'practice',
            'remix', 'live', 'bootleg', 'volume', 'vol', 'mix', 'compilation'
        ]
        penalty_keywords_artist = [
            'tribute', 'karaoke', 'cover', 'ensemble', 'orchestra', 'band', 'all stars',
            'lounge', 'sound-alike', 'backing track'
        ]

        penalties_applied = 0
        for kw in penalty_keywords_release:
            if kw in release_clean:
                weight -= 600_000
                penalties_applied += 600_000
        for kw in penalty_keywords_artist:
            if kw in artist_clean:
                weight -= 400_000
                penalties_applied += 400_000

        if penalties_applied > 0:
            score_breakdown.append(f"penalties=-{penalties_applied/1000:.0f}K")

        # Prefer shorter titles
        length_penalty = len(release_clean) * 100
        weight -= length_penalty
        if length_penalty > 0:
            score_breakdown.append(f"length=-{length_penalty}")

        # DEBUG: Log score breakdown for detailed analysis
        logger.debug(f"         Score breakdown: {' '.join(score_breakdown)} = {weight:,.0f}")

        return weight

    def _get_artist_popularity_score(self, artist_credit: str) -> float:
        """OPTIMIZATION: Fast lookup from pre-built cache table."""
        if not artist_credit:
            return 0.0

        if artist_credit in self._artist_score_cache:
            return self._artist_score_cache[artist_credit]

        if not self._conn:
            return 0.0

        try:
            row = self._conn.execute(
                "SELECT popularity_score FROM artist_popularity WHERE artist_credit_name = ?",
                [artist_credit]
            ).fetchone()
            value = float(row[0]) if row and row[0] is not None else 0.0
        except Exception:
            value = 0.0

        self._artist_score_cache[artist_credit] = value
        return value

    def _result_matches_album(self, release_name: Optional[str], album_hint: Optional[str], track_clean: str = "") -> bool:
        """Check if database release aligns with requested album - STRICT matching."""
        if not album_hint:
            return True

        if not release_name:
            return False

        album_clean = self.clean_text_conservative(album_hint)
        release_clean = self.clean_text_conservative(release_name)

        if not album_clean:
            return True

        # Exact match = always valid
        if album_clean == release_clean:
            return True

        # CRITICAL FIX: Remove loose substring matching that causes false positives
        # OLD: "808s heartbreak" matched "8 from 808s" because "808" is in both
        # NEW: Require strict token-based matching with minimum threshold

        # Track-as-album special case (single releases) - ONLY when no album hint provided
        # CRITICAL: Don't use this fallback when we have explicit album info!
        # Example: "Amazing (Capshun remix)" cleans to "amazing" and would match track "amazing"
        #          But we WANT "808s & Heartbreak" album, not a random remix single
        if not album_hint and track_clean and release_clean == track_clean:
            return True

        # Token-based matching with ULTRA-STRICT threshold
        stop_words = {"the", "and", "a", "an", "deluxe", "edition", "bonus", "version", "feat", "featuring", "from", "with"}

        album_tokens = [t for t in album_clean.split() if t not in stop_words]
        release_tokens = [t for t in release_clean.split() if t not in stop_words]

        if not album_tokens or not release_tokens:
            return False

        # CRITICAL FIX: Require ALL significant tokens to match (not just 50%)
        # Example: "808s & Heartbreak" has ["808s", "heartbreak"]
        #          "8 From 808s" has ["8", "808s"]
        #          Only "808s" matches = 1/2 = REJECT (need 2/2)

        matches = 0
        for token in album_tokens:
            found_match = False
            for release_token in release_tokens:
                if token == release_token:
                    matches += 1
                    found_match = True
                    break
                # Allow partial match only for longer tokens (4+ chars) AND similar length
                if (len(token) >= 4 and len(release_token) >= 4 and
                    abs(len(token) - len(release_token)) <= 2):
                    if token in release_token or release_token in token:
                        matches += 0.5  # Partial match counts as half
                        found_match = True
                        break

        # ULTRA-STRICT: Require 80% of album tokens to match (up from 50%)
        # This prevents "8 From 808s" (1/2 = 50%) from matching "808s & Heartbreak"
        overlap = matches / len(album_tokens)
        return overlap >= 0.8

    # ========== Confidence Scoring Methods ==========

    def _choose_candidate_with_confidence(
        self,
        rows: List[Tuple],
        artist_hint: Optional[str],
        album_hint: Optional[str],
        track_clean: str
    ) -> MatchResult:
        """Choose best candidate with confidence scoring.

        Returns MatchResult with confidence level and margin info.
        """
        if not rows:
            return MatchResult(
                artist_name=None,
                confidence="no_match",
                margin=0,
                top_candidates=[],
                reason="No candidates found"
            )

        # Score all candidates
        scored: List[CandidateResult] = []
        for row in rows:
            artist_credit, release_name, mb_score = (row + (0,))[:3]

            weight = self._score_candidate(
                artist_credit, release_name, mb_score or 0,
                track_clean, artist_hint, album_hint
            )

            artist_match_type, _ = self.artist_tokens_match(artist_hint, artist_credit) if artist_hint else (None, None)
            album_match = self._result_matches_album(release_name, album_hint, track_clean)

            scored.append(CandidateResult(
                artist_name=artist_credit,
                release_name=release_name,
                score=weight,
                mb_score=mb_score or 0,
                artist_match=artist_match_type,
                album_match=album_match,
                confidence="pending"
            ))

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)

        top_1 = scored[0]
        top_2 = scored[1] if len(scored) > 1 else None

        # Calculate margin
        margin = top_1.score - top_2.score if top_2 else float('inf')

        # Determine confidence
        if margin >= self.config.min_confidence_margin:
            confidence = "high"
            reason = f"Clear winner with margin {margin:,.0f}"
        elif top_1.score >= self.config.min_absolute_score and not top_2:
            confidence = "high"
            reason = "Only candidate with sufficient score"
        else:
            confidence = "low"
            reason = f"Margin {margin:,.0f} below threshold {self.config.min_confidence_margin:,.0f}"

        top_1.confidence = confidence

        return MatchResult(
            artist_name=top_1.artist_name,
            confidence=confidence,
            margin=margin,
            top_candidates=scored[:5],
            reason=reason
        )

    # ========== Edge Case Policy Methods ==========

    def _apply_ambiguous_title_policy(
        self,
        match_result: MatchResult,
        track_name: str,
        artist_hint: Optional[str],
        album_hint: Optional[str]
    ) -> MatchResult:
        """Apply stricter matching for ambiguous titles.

        For short/generic/numeric titles, require:
        - Strong artist match (exact token), OR
        - Strong album match

        Without hints, return no_match.
        """
        if match_result.confidence == "no_match":
            return match_result

        # Check if we have required evidence
        top = match_result.top_candidates[0] if match_result.top_candidates else None

        if not top:
            return match_result

        has_strong_artist = top.artist_match == "exact"
        has_strong_album = top.album_match

        if not artist_hint and not album_hint:
            # No hints for ambiguous title = reject
            if not self.config.match_short_titles_without_hints:
                return MatchResult(
                    artist_name=None,
                    confidence="no_match",
                    margin=match_result.margin,
                    top_candidates=match_result.top_candidates,
                    reason=f"Ambiguous title '{track_name}' requires artist or album hint"
                )

        if artist_hint and not has_strong_artist:
            if not has_strong_album:
                # Neither strong artist nor album match
                return MatchResult(
                    artist_name=None,
                    confidence="no_match",
                    margin=match_result.margin,
                    top_candidates=match_result.top_candidates,
                    reason=f"Ambiguous title: artist hint '{artist_hint}' did not match exactly"
                )

        return match_result

    def _apply_common_title_policy(
        self,
        match_result: MatchResult,
        track_name: str,
        artist_hint: Optional[str],
        album_hint: Optional[str]
    ) -> MatchResult:
        """Apply stricter matching for common/high-frequency titles.

        When title appears 50+ times in database, require stronger evidence.
        """
        if match_result.confidence == "no_match":
            return match_result

        top = match_result.top_candidates[0] if match_result.top_candidates else None

        if not top:
            return match_result

        # For common titles, check if multiple artists have similar scores
        if len(match_result.top_candidates) >= 2:
            top_2 = match_result.top_candidates[1]

            # Different artists with similar scores = ambiguous
            if (top.artist_name != top_2.artist_name and
                match_result.margin < self.config.min_confidence_margin * 2):

                # Without strong artist match, reject
                if not artist_hint or top.artist_match != "exact":
                    return MatchResult(
                        artist_name=None,
                        confidence="no_match",
                        margin=match_result.margin,
                        top_candidates=match_result.top_candidates,
                        reason=f"Common title '{track_name}' matches multiple artists with similar scores"
                    )

        # Without any hints, default to no_match for common titles
        if not artist_hint and not album_hint:
            return MatchResult(
                artist_name=None,
                confidence="no_match",
                margin=match_result.margin,
                top_candidates=match_result.top_candidates,
                reason=f"Common title '{track_name}' requires hints to disambiguate"
            )

        return match_result

    def _apply_obscure_artist_policy(
        self,
        match_result: MatchResult,
        track_name: str,
        artist_hint: Optional[str],
        album_hint: Optional[str]
    ) -> MatchResult:
        """Handle cases where artist may not exist in MusicBrainz.

        If artist_hint provided but no candidate matches it, prefer no_match.
        """
        if match_result.confidence == "no_match":
            return match_result

        if not artist_hint:
            return match_result

        top = match_result.top_candidates[0] if match_result.top_candidates else None

        if not top:
            return match_result

        # Artist hint provided but doesn't match any candidate
        if top.artist_match is None:
            # Check if album matches strongly
            if album_hint and top.album_match:
                # Album matches, might be compilation or different credit
                return MatchResult(
                    artist_name=match_result.artist_name,
                    confidence="low",
                    margin=match_result.margin,
                    top_candidates=match_result.top_candidates,
                    reason=f"Artist '{artist_hint}' not in credits but album matched"
                )

            # No artist match, no album match - likely not in database
            return MatchResult(
                artist_name=None,
                confidence="no_match",
                margin=match_result.margin,
                top_candidates=match_result.top_candidates,
                reason=f"Artist '{artist_hint}' not found in any candidate - may not exist in MusicBrainz"
            )

        return match_result

    # ========== Enhanced Search with Confidence ==========

    def search_with_confidence(
        self,
        track_name: str,
        artist_hint: Optional[str] = None,
        album_hint: Optional[str] = None
    ) -> MatchResult:
        """Search with full confidence info returned.

        Use this when you need detailed match information including
        confidence level, margin, and top candidates.
        """
        if not self.is_ready():
            return MatchResult(
                artist_name=None,
                confidence="no_match",
                margin=0,
                top_candidates=[],
                reason="Database not ready"
            )

        if not track_name or not track_name.strip():
            return MatchResult(
                artist_name=None,
                confidence="no_match",
                margin=0,
                top_candidates=[],
                reason="Empty track name"
            )

        if album_hint and str(album_hint).strip().lower() in {"nan", "none", "null", ""}:
            album_hint = None

        # Try conservative cleaning first
        clean_track = self.clean_text_conservative(track_name)
        if not clean_track:
            return MatchResult(
                artist_name=None,
                confidence="no_match",
                margin=0,
                top_candidates=[],
                reason="Track name cleaned to empty"
            )

        clean_artist_hint = self.clean_text_conservative(artist_hint) if artist_hint else None

        # Get candidates from combined search (normal mode first)
        rows = self._get_combined_candidates(clean_track, clean_artist_hint, album_hint)

        # Score and choose with confidence
        match_result = self._choose_candidate_with_confidence(
            rows, clean_artist_hint, album_hint, clean_track
        )

        # DYNAMIC MODE ESCALATION
        # If confidence is low or margin is below threshold, try high accuracy mode
        should_escalate = (
            self.config.auto_escalate_on_low_confidence and
            self.config.mode == "normal" and
            match_result.confidence == "low" and
            match_result.margin < self.config.low_confidence_escalation_threshold
        )

        if should_escalate:
            logger.debug(f"Auto-escalating to high accuracy mode: margin={match_result.margin:,.0f}")

            # Temporarily enable high accuracy features
            original_fuzzy = self.config.fuzzy_enabled
            original_limit = self.config.search_row_limit

            self.config.fuzzy_enabled = True
            self.config.search_row_limit = self.config.high_accuracy_row_limit

            try:
                # Get more candidates with fuzzy matching
                rows_escalated = self._get_combined_candidates(clean_track, clean_artist_hint, album_hint)

                if rows_escalated:
                    escalated_result = self._choose_candidate_with_confidence(
                        rows_escalated, clean_artist_hint, album_hint, clean_track
                    )

                    # Use escalated result if it's better
                    if (escalated_result.confidence != "no_match" and
                        (escalated_result.margin > match_result.margin or
                         escalated_result.confidence == "high")):
                        match_result = escalated_result
                        match_result.reason = f"[Escalated] {match_result.reason}"
                        logger.debug(f"Escalation improved result: {match_result.artist_name}, margin={match_result.margin:,.0f}")
            finally:
                # Restore original settings
                self.config.fuzzy_enabled = original_fuzzy
                self.config.search_row_limit = original_limit

        # Apply edge case policies
        if self.is_ambiguous_title(track_name):
            match_result = self._apply_ambiguous_title_policy(
                match_result, track_name, artist_hint, album_hint
            )

        if self.is_common_title(track_name):
            match_result = self._apply_common_title_policy(
                match_result, track_name, artist_hint, album_hint
            )

        # Apply obscure artist policy
        match_result = self._apply_obscure_artist_policy(
            match_result, track_name, artist_hint, album_hint
        )

        # Final check: enforce minimum absolute score
        if (match_result.confidence != "no_match" and
            match_result.top_candidates and
            match_result.top_candidates[0].score < self.config.min_absolute_score):
            logger.debug(f"Rejecting match: score {match_result.top_candidates[0].score:,.0f} < min {self.config.min_absolute_score:,.0f}")
            match_result = MatchResult(
                artist_name=None,
                confidence="no_match",
                margin=match_result.margin,
                top_candidates=match_result.top_candidates,
                reason=f"Score {match_result.top_candidates[0].score:,.0f} below minimum threshold"
            )

        return match_result

    def _get_combined_candidates(
        self,
        clean_track: str,
        artist_hint: Optional[str],
        album_hint: Optional[str]
    ) -> List[Tuple]:
        """Get candidates from both HOT and COLD tables for scoring."""
        if not self._conn:
            return []

        try:
            # Query both tables
            hot_rows = self._query_fuzzy_exact(clean_track, artist_hint, album_hint, use_hot=True)
            cold_rows = self._query_fuzzy_exact(clean_track, artist_hint, album_hint, use_hot=False)

            # Combine and limit total candidates
            all_rows = list(hot_rows or []) + list(cold_rows or [])

            # If no exact matches, try prefix
            if not all_rows:
                hot_prefix = self._query_fuzzy_prefix(clean_track, artist_hint, album_hint, use_hot=True)
                cold_prefix = self._query_fuzzy_prefix(clean_track, artist_hint, album_hint, use_hot=False)
                all_rows = list(hot_prefix or []) + list(cold_prefix or [])

            # If still no matches, try contains
            if not all_rows:
                hot_contains = self._query_fuzzy_contains(clean_track, artist_hint, album_hint, use_hot=True)
                cold_contains = self._query_fuzzy_contains(clean_track, artist_hint, album_hint, use_hot=False)
                all_rows = list(hot_contains or []) + list(cold_contains or [])

            return all_rows[:self.config.search_row_limit * 2]  # Allow more candidates for better scoring
        except Exception as e:
            logger.exception(f"Error getting combined candidates: {e}")
            return []

    # ========== Logging and Observability ==========

    def _log_match_attempt(
        self,
        track_name: str,
        artist_hint: Optional[str],
        album_hint: Optional[str],
        result: MatchResult,
        search_tier: str,
        elapsed_ms: float
    ):
        """Log detailed match attempt for analysis and tuning."""
        log_data = {
            "input": {
                "track": track_name,
                "artist_hint": artist_hint,
                "album_hint": album_hint
            },
            "result": {
                "artist": result.artist_name,
                "confidence": result.confidence,
                "margin": result.margin,
                "reason": result.reason
            },
            "search": {
                "tier": search_tier,
                "elapsed_ms": elapsed_ms,
                "mode": self.config.mode,
                "candidates_count": len(result.top_candidates)
            },
            "top_candidates": [
                {
                    "artist": c.artist_name,
                    "release": c.release_name,
                    "score": c.score,
                    "artist_match": c.artist_match,
                    "album_match": c.album_match
                }
                for c in result.top_candidates[:3]
            ]
        }

        logger.debug(f"Match attempt: {json.dumps(log_data)}")

    def get_cache_stats(self) -> Dict:
        """Get cache performance statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate_percent": hit_rate,
            "cache_size": len(self._search_cache),
            "cache_max_size": LRU_CACHE_SIZE
        }

    @trace_call("MBManager.wait_until_ready")
    def wait_until_ready(self, timeout: float = 600.0) -> bool:
        """Block until optimization is complete."""
        if self.is_ready():
            return True

        if not self.is_database_available():
            return False

        if not self._optimization_in_progress:
            self.start_optimization_if_needed()

        start_time = time.time()
        while not self.is_ready() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        return self.is_ready()

    def get_optimization_status(self) -> Dict:
        """Get current optimization status."""
        return {
            "ready": self.is_ready(),
            "in_progress": self._optimization_in_progress,
            "csv_available": self.is_database_available(),
            "duckdb_exists": self.duckdb_file.exists(),
            "metadata": self._metadata,
            "cache_stats": self.get_cache_stats()
        }

    # Legacy compatibility methods
    def download_database(self, progress_callback: Optional[Callable] = None) -> bool:
        """
        Download MusicBrainz canonical data with extensive debugging and retry logic.

        Based on:
        - https://metabrainz.org/datasets/derived-dumps
        - https://data.metabrainz.org/pub/musicbrainz/canonical_data/
        """
        import httpx
        import tempfile
        from datetime import datetime
        import re

        # MusicBrainz canonical data URL
        BASE_URL = "https://data.metabrainz.org/pub/musicbrainz/canonical_data/"

        logger.print_always("\n" + "="*80)
        logger.print_always("[DOWN] MUSICBRAINZ DATABASE DOWNLOAD")
        logger.print_always("="*80)

        try:
            logger.print_always(f"[PIN] Base URL: {BASE_URL}")
            logger.print_always(f"[FOLDER] Download directory: {self.data_dir}")

            # Step 1: Discover latest canonical data file
            logger.print_always("\n[SIGNAL] STEP 1: Discovering latest canonical data file...")

            if progress_callback:
                progress_callback("Discovering latest canonical data...", 0, {"url": BASE_URL})

            # Try to list directory and find latest file
            try:
                logger.print_always(f"[W] Fetching directory listing from: {BASE_URL}")
                logger.print_always(f"[~] Sending HTTP GET request...")

                with httpx.Client(http2=False, timeout=30.0) as client:
                    response = client.get(BASE_URL)

                logger.print_always(f"[OK] HTTP {response.status_code} {response.reason_phrase}")
                logger.print_always(f"[LIST] Response Headers:")
                logger.print_always(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
                logger.print_always(f"   Content-Length: {response.headers.get('content-length', 'N/A')}")
                logger.print_always(f"   Server: {response.headers.get('server', 'N/A')}")

                response.raise_for_status()

                # Save full HTML for debugging
                html_content = response.text
                logger.print_always(f"[f] HTML Response: {len(html_content)} characters")

                # Save HTML to debug file
                try:
                    debug_html_path = self.data_dir / "debug_directory_listing.html"
                    with open(debug_html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.print_always(f"[D] Saved HTML debug file: {debug_html_path}")
                    logger.info(f"Saved directory listing to: {debug_html_path}")
                except Exception as e:
                    logger.warning(f"[!]  Could not save debug HTML: {e}")

                # Parse HTML to find dated subdirectories first
                logger.print_always(f"\n[?] Searching for dated subdirectories...")
                logger.print_always(f"[?] Pattern: musicbrainz-canonical-dump-YYYYMMDD-HHMMSS/")

                # Look for directories like: musicbrainz-canonical-dump-20251003-080003/
                dir_pattern = r'href="(musicbrainz-canonical-dump-(\d{8})-\d+/)"'
                dir_matches = re.findall(dir_pattern, html_content)

                logger.print_always(f"[=] Found {len(dir_matches)} dated subdirectories")

                if len(dir_matches) == 0:
                    logger.print_always(f"[X] No subdirectories found - showing first 500 chars of HTML:")
                    logger.print_always(html_content[:500])

                for i, (dir_name, date_str) in enumerate(dir_matches[:5], 1):  # Show first 5
                    try:
                        dir_date = datetime.strptime(date_str, '%Y%m%d')
                        logger.print_always(f"   {i}. {dir_name} -> {dir_date.strftime('%Y-%m-%d')}")
                    except:
                        logger.print_always(f"   {i}. {dir_name} -> (invalid date)")

                if len(dir_matches) > 5:
                    logger.print_always(f"   ... and {len(dir_matches) - 5} more")

                if dir_matches:
                    # Sort by date and get latest
                    sorted_dirs = sorted(dir_matches, key=lambda x: x[1])
                    latest_dir, latest_date = sorted_dirs[-1]

                    logger.print_always(f"\n[*] Selected LATEST: {latest_dir}")
                    try:
                        dir_date = datetime.strptime(latest_date, '%Y%m%d')
                        logger.print_always(f"[CALENDAR] Date: {dir_date.strftime('%Y-%m-%d')}")
                    except:
                        logger.print_always(f"[CALENDAR] Date: {latest_date} (raw)")

                    # Now fetch the contents of this subdirectory
                    subdir_url = BASE_URL + latest_dir
                    logger.print_always(f"\n[W] Fetching subdirectory: {subdir_url}")

                    with httpx.Client(http2=False, timeout=30.0) as client:
                        subdir_response = client.get(subdir_url)
                    logger.print_always(f"[OK] HTTP {subdir_response.status_code} {subdir_response.reason_phrase}")

                    subdir_response.raise_for_status()
                    subdir_html = subdir_response.text
                    logger.print_always(f"[f] Subdirectory HTML: {len(subdir_html)} characters")

                    # Save subdirectory HTML for debugging
                    try:
                        debug_subdir_html_path = self.data_dir / "debug_subdirectory_listing.html"
                        with open(debug_subdir_html_path, 'w', encoding='utf-8') as f:
                            f.write(subdir_html)
                        logger.print_always(f"[D] Saved subdirectory HTML: {debug_subdir_html_path}")
                    except Exception as e:
                        logger.warning(f"[!]  Could not save subdirectory HTML: {e}")

                    # Now look for data files in the subdirectory
                    logger.print_always(f"\n[?] STEP 2: Searching for data files in subdirectory...")
                    logger.print_always(f"[?] Looking for: *.csv or *.tar.zst")

                    # Look for .csv files
                    pattern_csv = r'href="([^"]*\.csv)"'
                    matches_csv = re.findall(pattern_csv, subdir_html)
                    logger.print_always(f"[=] Found {len(matches_csv)} .csv files")
                    for i, match in enumerate(matches_csv, 1):
                        file_size = "unknown size"
                        # Try to extract file size from HTML (varies by server)
                        size_match = re.search(rf'{re.escape(match)}"[^>]*>.*?(\d+[KMGT]?B?)', subdir_html)
                        if size_match:
                            file_size = size_match.group(1)
                        logger.print_always(f"   {i}. {match} ({file_size})")

                    # Try .tar.zst if no CSV
                    if not matches_csv:
                        logger.print_always(f"[!]  No .csv files found, trying .tar.zst pattern...")
                        pattern_zst = r'href="([^"]*\.tar\.zst)"'
                        matches_zst = re.findall(pattern_zst, subdir_html)
                        logger.print_always(f"[=] Found {len(matches_zst)} .tar.zst files")
                        for i, match in enumerate(matches_zst, 1):
                            file_size = "unknown size"
                            size_match = re.search(rf'{re.escape(match)}"[^>]*>.*?(\d+[KMGT]?B?)', subdir_html)
                            if size_match:
                                file_size = size_match.group(1)
                            logger.print_always(f"   {i}. {match} ({file_size})")
                        matches = matches_zst
                    else:
                        matches = matches_csv

                    if matches:
                        # Use the first match (should only be one file)
                        selected_file = matches[0]
                        logger.print_always(f"\n[*] SELECTED FILE: {selected_file}")

                        download_url = subdir_url + selected_file
                        logger.print_always(f"[PIN] Full download URL: {download_url}")
                    else:
                        logger.print_always(f"\n[X] No data files found in subdirectory")
                        logger.print_always(f"[f] Showing first 500 chars of subdirectory HTML:")
                        logger.print_always(subdir_html[:500])
                        logger.print_always(f"\n[!]  Falling back to known dated directory")
                        # Use a known working dated directory format (August 2024)
                        download_url = BASE_URL + "musicbrainz-canonical-dump-20240817-080003/canonical_musicbrainz_data.csv"
                        logger.print_always(f"[PIN] Fallback URL: {download_url}")
                else:
                    # Fallback: try to find files directly in root (old behavior)
                    logger.print_always(f"\n[!]  No dated subdirectories found, searching root directory...")
                    logger.print_always(f"[?] Pattern: canonical_musicbrainz_data*.csv")

                    pattern_csv = r'href="(canonical_musicbrainz_data[^"]*\.csv)"'
                    matches_csv = re.findall(pattern_csv, html_content)

                    logger.print_always(f"[=] Found {len(matches_csv)} matching files in root")

                    if matches_csv:
                        latest_file = sorted(matches_csv)[-1]
                        logger.print_always(f"[*] Selected (latest): {latest_file}")
                        download_url = BASE_URL + latest_file
                        logger.print_always(f"[PIN] Full URL: {download_url}")
                    else:
                        logger.print_always(f"[X] No files found in root directory")
                        logger.print_always(f"[f] Showing first 500 chars of root HTML:")
                        logger.print_always(html_content[:500])
                        logger.print_always(f"\n[!]  Using fallback with known dated directory")
                        # Use a known working dated directory format (August 2024)
                        download_url = BASE_URL + "musicbrainz-canonical-dump-20240817-080003/canonical_musicbrainz_data.csv"
                        logger.print_always(f"[PIN] Fallback URL: {download_url}")

            except Exception as e:
                logger.print_always(f"\n[!] EXCEPTION during directory discovery:")
                logger.print_always(f"[X] Error: {e}")
                import traceback
                logger.print_always(f"[LIST] Traceback:\n{traceback.format_exc()}")
                logger.print_always(f"[!]  Using fallback URL with known dated directory...")
                # Use a known working dated directory format (August 2024)
                download_url = BASE_URL + "musicbrainz-canonical-dump-20240817-080003/canonical_musicbrainz_data.csv"
                logger.print_always(f"[PIN] Fallback URL: {download_url}")

            logger.print_always(f"\n" + "="*80)
            logger.print_always(f"[DOWNLOAD] FINAL DOWNLOAD URL: {download_url}")
            logger.print_always(f"="*80)

            # Step 2: Download with retry logic and exponential backoff
            logger.print_always(f"\n[DOWNARROW]  STEP 3: Download with retry logic and exponential backoff")

            max_retries = 3
            retry_delay = 2  # Start with 2 seconds

            logger.print_always(f"[R] Max retries: {max_retries}")
            logger.print_always(f"[TIME]  Initial retry delay: {retry_delay}s")

            for attempt in range(max_retries):
                try:
                    logger.print_always(f"\n{'='*80}")
                    logger.print_always(f"[R] DOWNLOAD ATTEMPT {attempt + 1}/{max_retries}")
                    logger.print_always(f"{'='*80}")

                    if progress_callback:
                        progress_callback(
                            f"Downloading (attempt {attempt + 1}/{max_retries})...",
                            5,
                            {"url": download_url}
                        )

                    # Parallel range download for maximum throughput
                    logger.print_always(f"\n[SIGNAL] Checking server capabilities...")
                    logger.print_always(f"[W] HEAD {download_url}")

                    # Reset cancellation flag
                    self._cancellation_requested = False

                    download_start_time = time.time()

                    import httpx
                    import threading
                    from queue import Queue

                    # Check if server supports range requests
                    head_response = httpx.head(download_url, follow_redirects=True, timeout=30.0)
                    logger.print_always(f"[OK] HTTP {head_response.status_code} {head_response.reason_phrase}")
                    head_response.raise_for_status()

                    total_size = int(head_response.headers.get('content-length', 0))
                    accept_ranges = head_response.headers.get('accept-ranges', '').lower()
                    supports_ranges = 'bytes' in accept_ranges

                    logger.print_always(f"\n[P] File Information:")
                    logger.print_always(f"   Size: {total_size:,} bytes ({total_size / (1024**2):.2f} MB / {total_size / (1024**3):.2f} GB)")
                    logger.print_always(f"   Range support: {'[OK] Yes' if supports_ranges else '[X] No'}")
                    logger.print_always(f"   Accept-Ranges header: {head_response.headers.get('accept-ranges', 'N/A')}")
                    logger.print_always(f"   Content-Type: {head_response.headers.get('content-type', 'N/A')}")

                    # Create temporary file (use mkstemp for Windows compatibility)
                    logger.print_always(f"\n[D] Creating temporary file...")
                    import os
                    temp_fd, temp_path = tempfile.mkstemp(suffix='.csv')
                    os.close(temp_fd)  # Close file descriptor immediately, we'll open it later

                    if supports_ranges and total_size > 50 * 1024 * 1024:  # Use parallel for files >50MB
                        # PARALLEL DOWNLOAD with multiple connections
                        NUM_CONNECTIONS = 4  # 4 parallel connections (fewer = less contention)
                        RANGE_SIZE = 64 * 1024 * 1024  # 64MB per range (larger = fewer seeks)

                        logger.print_always(f"   [>] Using parallel download: {NUM_CONNECTIONS} connections")
                        logger.info(f"   [P] Range size: {RANGE_SIZE / (1024**2):.0f} MB")
                        logger.info(f"   Temp file: {temp_path}")
                        logger.info(f"Parallel download: {NUM_CONNECTIONS} connections, {RANGE_SIZE} bytes per range")

                        # Pre-allocate file
                        with open(temp_path, 'wb') as f:
                            f.truncate(total_size)

                        # Calculate ranges
                        ranges = []
                        for start in range(0, total_size, RANGE_SIZE):
                            end = min(start + RANGE_SIZE - 1, total_size - 1)
                            ranges.append((start, end))

                        logger.print_always(f"   [=] Split into {len(ranges)} ranges")

                        # Progress tracking - minimize lock contention
                        downloaded = [0]
                        lock = threading.Lock()
                        last_update_time = [time.time()]
                        last_downloaded = [0]

                        def download_range(start, end, file_path):
                            """Download a specific byte range"""
                            # Check for cancellation
                            if self._cancellation_requested:
                                raise Exception("Download cancelled by user")

                            headers = {"Range": f"bytes={start}-{end}"}
                            # Use connection pooling within each thread
                            limits = httpx.Limits(max_connections=1, max_keepalive_connections=1)
                            with httpx.Client(http2=False, timeout=120.0, limits=limits) as client:
                                with client.stream("GET", download_url, headers=headers) as response:
                                    response.raise_for_status()
                                    # Buffer writes to reduce file I/O contention
                                    buffer = bytearray()
                                    buffer_size = 4 * 1024 * 1024  # 4MB buffer before write

                                    with open(file_path, 'r+b') as f:
                                        f.seek(start)
                                        for chunk in response.iter_bytes(2 * 1024 * 1024):  # 2MB chunks
                                            # Check for cancellation
                                            if self._cancellation_requested:
                                                raise Exception("Download cancelled by user")

                                            buffer.extend(chunk)

                                            # Write when buffer is full
                                            if len(buffer) >= buffer_size:
                                                f.write(buffer)
                                                bytes_written = len(buffer)
                                                buffer.clear()

                                                # Update counter outside expensive operations
                                                with lock:
                                                    downloaded[0] += bytes_written
                                                    current_time = time.time()

                                                    # Update progress less frequently (1.5 seconds)
                                                    if current_time - last_update_time[0] >= 1.5:
                                                        # Do expensive calculations inside lock but minimize time held
                                                        # Download is Step 1/5, uses 0-75% of progress bar
                                                        progress_pct = (downloaded[0] / total_size) * 75
                                                        gb_downloaded = downloaded[0] / (1024**3)
                                                        gb_total = total_size / (1024**3)

                                                        bytes_since = downloaded[0] - last_downloaded[0]
                                                        elapsed = current_time - last_update_time[0]
                                                        mb_per_sec = (bytes_since / (1024**2)) / elapsed

                                                        bytes_remaining = total_size - downloaded[0]
                                                        eta_seconds = bytes_remaining / (bytes_since / elapsed) if bytes_since > 0 else 0
                                                        eta_mins = int(eta_seconds // 60)
                                                        eta_secs = int(eta_seconds % 60)
                                                        eta_str = f"{eta_mins}m {eta_secs}s" if eta_mins > 0 else f"{eta_secs}s"

                                                        last_update_time[0] = current_time
                                                        last_downloaded[0] = downloaded[0]

                                                        # Release lock before I/O
                                                        logger.print_always(f"   [=] {progress_pct:.1f}% | {gb_downloaded:.2f}/{gb_total:.2f} GB | {mb_per_sec:.2f} MB/s | ETA: {eta_str}")

                                                        if progress_callback:
                                                            progress_callback(
                                                                f"[Step 1/5] Download: {gb_downloaded:.2f}/{gb_total:.2f} GB ({mb_per_sec:.1f} MB/s, ETA: {eta_str})",
                                                                progress_pct,
                                                                {"url": download_url}
                                                            )

                                        # Write remaining buffer
                                        if buffer:
                                            f.write(buffer)
                                            with lock:
                                                downloaded[0] += len(buffer)

                        # Download ranges in parallel with thread pool
                        logger.print_always(f"\n[DOWNARROW]  Downloading with {NUM_CONNECTIONS} parallel connections...")
                        logger.print_always(f"[THREAD] Starting thread pool executor...")

                        from concurrent.futures import ThreadPoolExecutor, as_completed
                        with ThreadPoolExecutor(max_workers=NUM_CONNECTIONS) as executor:
                            futures = [executor.submit(download_range, start, end, temp_path) for start, end in ranges]
                            for future in as_completed(futures):
                                future.result()  # Raise any exceptions

                        downloaded_total = downloaded[0]

                    else:
                        # FALLBACK: Single-stream download
                        logger.print_always(f"\n[SIGNAL] Using single-stream download (file <50MB or no range support)")
                        logger.print_always(f"[D] Temp file: {temp_path}")
                        logger.print_always(f"[W] GET {download_url}")

                        downloaded_total = 0
                        last_update_time = time.time()
                        last_downloaded = 0

                        with httpx.Client(http2=False, timeout=120.0, follow_redirects=True) as client:
                            with client.stream("GET", download_url) as response:
                                logger.print_always(f"[OK] HTTP {response.status_code} {response.reason_phrase}")
                                response.raise_for_status()

                                logger.print_always(f"\n[DOWNARROW]  Streaming download...")
                                with open(temp_path, 'wb', buffering=16*1024*1024) as f:
                                    for chunk in response.iter_bytes(8 * 1024 * 1024):
                                        # Check for cancellation
                                        if self._cancellation_requested:
                                            raise Exception("Download cancelled by user")

                                        f.write(chunk)
                                        downloaded_total += len(chunk)

                                        current_time = time.time()
                                        elapsed = current_time - last_update_time
                                        if elapsed >= 1.0:
                                            progress_pct = (downloaded_total / total_size) * 90
                                            gb_downloaded = downloaded_total / (1024**3)
                                            gb_total = total_size / (1024**3)

                                            bytes_since = downloaded_total - last_downloaded
                                            mb_per_sec = (bytes_since / (1024**2)) / elapsed

                                            bytes_remaining = total_size - downloaded_total
                                            eta_seconds = bytes_remaining / (bytes_since / elapsed) if bytes_since > 0 else 0
                                            eta_mins = int(eta_seconds // 60)
                                            eta_secs = int(eta_seconds % 60)
                                            eta_str = f"{eta_mins}m {eta_secs}s" if eta_mins > 0 else f"{eta_secs}s"

                                            logger.print_always(f"   [=] {progress_pct:.1f}% | {gb_downloaded:.2f}/{gb_total:.2f} GB | {mb_per_sec:.2f} MB/s | ETA: {eta_str}")

                                            last_update_time = current_time
                                            last_downloaded = downloaded_total

                    # Download complete
                    download_elapsed = time.time() - download_start_time
                    avg_speed_mb = (downloaded_total / (1024**2)) / download_elapsed

                    logger.print_always(f"\n[OK] Download completed!")
                    logger.print_always(f"   [=] Total: {downloaded_total:,} bytes ({downloaded_total / (1024**3):.2f} GB)")
                    logger.print_always(f"   [TIME]  Time: {download_elapsed:.1f}s ({int(download_elapsed // 60)}m {int(download_elapsed % 60)}s)")
                    logger.print_always(f"   [CHART] Avg speed: {avg_speed_mb:.2f} MB/s")

                    # Step 4: Validate downloaded file
                    logger.print_always(f"\n[v]  STEP 4: Validating downloaded file...")

                    if progress_callback:
                        progress_callback("Validating downloaded file...", 92)

                    temp_path_obj = Path(temp_path)

                    logger.print_always(f"[F] Checking file: {temp_path}")

                    if not temp_path_obj.exists():
                        logger.print_always(f"[X] ERROR: Temp file does not exist!")
                        raise Exception(f"Temp file does not exist: {temp_path}")

                    file_size = temp_path_obj.stat().st_size
                    logger.print_always(f"[OK] File exists")
                    logger.print_always(f"[=] File size: {file_size:,} bytes ({file_size / (1024**2):.2f} MB / {file_size / (1024**3):.2f} GB)")

                    if file_size < 1000000:  # At least 1MB
                        logger.print_always(f"[X] ERROR: File too small (expected at least 1MB)")
                        raise Exception(f"Downloaded file is too small: {file_size} bytes (expected at least 1MB)")

                    if total_size > 0 and file_size != total_size:
                        logger.print_always(f"[!]  Size mismatch: expected {total_size:,}, got {file_size:,}")
                    else:
                        logger.print_always(f"[OK] File size matches expected size")

                    logger.print_always(f"[OK] File validation passed")

                    # Step 5: Extract if compressed archive
                    # NOTE: Extraction takes significant time on slow CPUs, so we give it
                    # more of the progress bar: download=0-80%, decompress=80-90%, tar=90-99%
                    final_csv_path = temp_path  # Default to downloaded file

                    if download_url.endswith('.tar.zst'):
                        logger.print_always(f"\n[P] STEP 5: Extracting compressed archive...")
                        logger.print_always(f"[COMPRESS]  Archive format: .tar.zst (zstandard compression + tar)")

                        if progress_callback:
                            progress_callback("[Step 2/5] Starting decompression (this may take a while on slow CPUs)...", 75)

                        try:
                            import tarfile
                            import zstandard as zstd

                            # Create extraction directory
                            extract_dir = Path(tempfile.mkdtemp(prefix='musicbrainz_extract_'))
                            logger.print_always(f"[F] Extraction directory: {extract_dir}")

                            # Step 5a: Decompress .zst
                            logger.print_always(f"\n[U] Step 5a: Decompressing zstandard (.zst) archive...")
                            logger.print_always(f"[DOWNLOAD] Input: {temp_path}")

                            tar_path = extract_dir / "archive.tar"
                            logger.print_always(f"[OUTBOX] Output: {tar_path}")

                            decompression_start = time.time()
                            # Estimate: typical zst compression is ~4-5x, so expect ~8-10GB decompressed
                            estimated_decompressed = file_size * 5  # Conservative estimate
                            last_progress_pct = 0

                            with open(temp_path, 'rb') as compressed:
                                dctx = zstd.ZstdDecompressor()
                                with open(tar_path, 'wb') as destination:
                                    decompressed_size = 0
                                    for chunk in dctx.read_to_iter(compressed):
                                        destination.write(chunk)
                                        decompressed_size += len(chunk)

                                        # Show progress every 2% for better feedback on slow CPUs
                                        progress_pct = min(99, int((decompressed_size / estimated_decompressed) * 100))
                                        if progress_pct >= last_progress_pct + 2 or (progress_pct > 0 and last_progress_pct == 0):
                                            elapsed = time.time() - decompression_start
                                            speed_mb = (decompressed_size / (1024**2)) / elapsed if elapsed > 0 else 0
                                            eta_seconds = (estimated_decompressed - decompressed_size) / (decompressed_size / elapsed) if decompressed_size > 0 and elapsed > 0 else 0
                                            logger.print_always(f"   [>] Decompressing: {progress_pct}% ({decompressed_size / (1024**3):.2f} GB, {speed_mb:.1f} MB/s, ETA: {eta_seconds:.0f}s)")

                                            if progress_callback:
                                                # Map decompression progress to 75-85% range (gives 10% of bar to decompression)
                                                overall_pct = 75 + int(progress_pct * 0.10)
                                                progress_callback(f"[Step 2/5] Decompress: {progress_pct}% ({decompressed_size / (1024**3):.2f} GB, {speed_mb:.1f} MB/s, ETA: {eta_seconds:.0f}s)", overall_pct)

                                            last_progress_pct = progress_pct

                            decompression_elapsed = time.time() - decompression_start
                            logger.print_always(f"[OK] Decompressed in {decompression_elapsed:.1f}s")
                            logger.print_always(f"[=] Decompressed size: {decompressed_size:,} bytes ({decompressed_size / (1024**3):.2f} GB)")
                            logger.print_always(f"[CHART] Decompression ratio: {file_size / decompressed_size:.2f}x")

                            # Step 5b: Extract .tar
                            logger.print_always(f"\n[P] Step 5b: Extracting tar archive...")

                            if progress_callback:
                                progress_callback("[Step 3/5] Extracting tar archive...", 85)

                            extraction_start = time.time()
                            with tarfile.open(tar_path, 'r') as tar:
                                members = tar.getmembers()
                                total_members = len(members)
                                total_size = sum(m.size for m in members)
                                logger.print_always(f"[=] Archive contains {total_members} files ({total_size / (1024**3):.2f} GB total)")

                                # List all files (show first 10)
                                csv_files = []
                                logger.print_always(f"[LIST] Archive contents (first 10):")
                                for i, member in enumerate(members[:10], 1):
                                    logger.print_always(f"   {i}. {member.name} ({member.size:,} bytes, {member.size / (1024**2):.2f} MB)")
                                    if member.name.endswith('.csv'):
                                        csv_files.append(member)

                                if total_members > 10:
                                    logger.print_always(f"   ... and {total_members - 10} more files")

                                # Extract with progress
                                logger.print_always(f"\n[GEAR]  Extracting all files to: {extract_dir}")
                                extracted_size = 0
                                last_progress_pct = 0
                                for i, member in enumerate(members, 1):
                                    tar.extract(member, path=extract_dir)
                                    extracted_size += member.size

                                    # Calculate progress percentage
                                    if total_size > 0:
                                        progress_pct = int((extracted_size / total_size) * 100)
                                    else:
                                        progress_pct = int((i / total_members) * 100)

                                    # Update progress every 5% or on last file
                                    if progress_pct >= last_progress_pct + 5 or i == total_members:
                                        elapsed = time.time() - extraction_start
                                        speed_mb = (extracted_size / (1024**2)) / elapsed if elapsed > 0 else 0
                                        remaining_size = total_size - extracted_size
                                        eta_seconds = remaining_size / (extracted_size / elapsed) if extracted_size > 0 and elapsed > 0 else 0

                                        logger.print_always(f"   [>] Extracting: {progress_pct}% ({i}/{total_members} files, {extracted_size / (1024**3):.2f}/{total_size / (1024**3):.2f} GB, {speed_mb:.1f} MB/s, ETA: {eta_seconds:.0f}s)")

                                        if progress_callback:
                                            # Map extraction progress to 85-95% range (gives 10% of bar to tar extraction)
                                            overall_pct = 85 + int(progress_pct * 0.10)
                                            progress_callback(f"[Step 3/5] Extract tar: {progress_pct}% ({i}/{total_members} files, {speed_mb:.1f} MB/s, ETA: {eta_seconds:.0f}s)", overall_pct)

                                        last_progress_pct = progress_pct

                            extraction_elapsed = time.time() - extraction_start
                            logger.print_always(f"[OK] Extraction complete in {extraction_elapsed:.1f}s")

                            # Step 5c: Find CSV file
                            logger.print_always(f"\n[?] Step 5c: Finding CSV file in extracted contents...")

                            # Look for canonical_musicbrainz_data.csv
                            csv_candidates = list(extract_dir.rglob("*.csv"))
                            logger.print_always(f"[=] Found {len(csv_candidates)} CSV files:")

                            for i, csv_file in enumerate(csv_candidates, 1):
                                relative_path = csv_file.relative_to(extract_dir)
                                csv_size = csv_file.stat().st_size
                                logger.print_always(f"   {i}. {relative_path} ({csv_size:,} bytes, {csv_size / (1024**3):.2f} GB)")

                            if not csv_candidates:
                                logger.print_always(f"[X] ERROR: No CSV files found in extracted archive")
                                logger.print_always(f"[F] Contents of {extract_dir}:")
                                for item in extract_dir.iterdir():
                                    logger.print_always(f"   - {item.name}")
                                raise Exception("No CSV files found in extracted archive")

                            # Use the largest CSV file (should be the canonical data)
                            final_csv = max(csv_candidates, key=lambda p: p.stat().st_size)
                            final_csv_path = str(final_csv)

                            logger.print_always(f"\n[*] Selected (largest) CSV: {final_csv.name}")
                            logger.print_always(f"[=] Size: {final_csv.stat().st_size:,} bytes ({final_csv.stat().st_size / (1024**3):.2f} GB)")
                            logger.print_always(f"[F] Full path: {final_csv_path}")

                            # Clean up compressed files
                            logger.print_always(f"\n[DEL]  Cleaning up temporary compressed files...")
                            try:
                                Path(temp_path).unlink()
                                tar_path.unlink()
                                logger.print_always(f"[OK] Cleaned up compressed and tar files")
                            except Exception as e:
                                logger.print_always(f"[!]  Could not clean up temp files: {e}")

                            logger.print_always(f"[OK] Archive extraction complete!")

                        except ImportError as e:
                            logger.print_always(f"\n[X] ERROR: Missing required library")
                            logger.print_always(f"[P] Library: zstandard (for .zst decompression)")
                            logger.print_always(f"[TIP] Install with: pip install zstandard")
                            logger.print_always(f"[X] Error details: {e}")
                            raise Exception("zstandard library not installed. Run: pip install zstandard")
                        except Exception as e:
                            logger.print_always(f"\n[!] EXCEPTION during extraction:")
                            logger.print_always(f"[X] Error: {e}")
                            import traceback
                            logger.print_always(f"[LIST] Traceback:\n{traceback.format_exc()}")
                            raise
                    else:
                        logger.print_always(f"\n[i]  File is already uncompressed (not .tar.zst)")
                        logger.print_always(f"[OK] No extraction needed")

                    # Step 6: Move to final location
                    logger.print_always(f"\n[P] STEP 6: Installing database to final location...")

                    if progress_callback:
                        progress_callback("[Step 4/5] Installing database...", 95)

                    self.canonical_dir.mkdir(parents=True, exist_ok=True)
                    logger.print_always(f"[F] Target directory: {self.canonical_dir}")
                    logger.print_always(f"[f] Target file: {self.csv_file}")

                    if self.csv_file.exists():
                        old_size = self.csv_file.stat().st_size
                        logger.print_always(f"[!]  Existing file will be replaced ({old_size:,} bytes, {old_size / (1024**3):.2f} GB)")

                    # Use chunked copy with progress instead of shutil.copy2
                    logger.print_always(f"\n[LIST] Installing database file...")
                    logger.print_always(f"   From: {final_csv_path}")
                    logger.print_always(f"   To: {self.csv_file}")

                    copy_start = time.time()
                    try:
                        # Get source file size for progress calculation
                        source_size = Path(final_csv_path).stat().st_size
                        logger.print_always(f"   Size: {source_size / (1024**3):.2f} GB")

                        # Chunked copy with progress reporting
                        chunk_size = 64 * 1024 * 1024  # 64MB chunks
                        copied_size = 0
                        last_progress_pct = 0

                        with open(final_csv_path, 'rb') as src:
                            with open(self.csv_file, 'wb') as dst:
                                while True:
                                    chunk = src.read(chunk_size)
                                    if not chunk:
                                        break
                                    dst.write(chunk)
                                    copied_size += len(chunk)

                                    # Calculate and report progress
                                    progress_pct = int((copied_size / source_size) * 100)
                                    if progress_pct >= last_progress_pct + 5 or progress_pct == 100:
                                        elapsed = time.time() - copy_start
                                        speed_mb = (copied_size / (1024**2)) / elapsed if elapsed > 0 else 0
                                        remaining = source_size - copied_size
                                        eta_seconds = remaining / (copied_size / elapsed) if copied_size > 0 and elapsed > 0 else 0

                                        logger.print_always(f"   [>] Installing: {progress_pct}% ({copied_size / (1024**3):.2f}/{source_size / (1024**3):.2f} GB, {speed_mb:.1f} MB/s, ETA: {eta_seconds:.0f}s)")

                                        if progress_callback:
                                            # Map 95-99% for install step (gives 4% of bar to file copy)
                                            overall_pct = 95 + int(progress_pct * 0.04)
                                            progress_callback(f"[Step 4/5] Install: {progress_pct}% ({copied_size / (1024**3):.2f}/{source_size / (1024**3):.2f} GB, {speed_mb:.1f} MB/s, ETA: {eta_seconds:.0f}s)", overall_pct)

                                        last_progress_pct = progress_pct

                        # Copy metadata (timestamps)
                        try:
                            shutil.copystat(final_csv_path, self.csv_file)
                        except Exception:
                            pass  # Ignore metadata copy errors

                        Path(final_csv_path).unlink()  # Delete source after successful copy
                        copy_elapsed = time.time() - copy_start
                        logger.print_always(f"[OK] File installed in {copy_elapsed:.1f}s")
                        logger.print_always(f"[F] Location: {self.csv_file}")
                    except Exception as e:
                        logger.print_always(f"[X] ERROR: Failed to install database file")
                        logger.print_always(f"   Error: {e}")
                        raise Exception(f"Could not install database file: {e}")

                    # Step 7: Clear optimization state to force rebuild
                    logger.print_always(f"\n[R] STEP 7: Clearing optimization state...")

                    if progress_callback:
                        progress_callback("[Step 5/5] Verifying and finalizing...", 99)

                    self._optimization_complete = False
                    self._optimization_in_progress = False

                    if self.duckdb_file.exists():
                        logger.print_always(f"[DEL]  Removing old DuckDB file: {self.duckdb_file}")
                        self.duckdb_file.unlink()
                        logger.print_always(f"[OK] Old DuckDB file removed")

                    # Step 8: Verify installation
                    logger.print_always(f"\n[v]  STEP 8: Verifying final installation...")

                    final_size = self.csv_file.stat().st_size
                    logger.print_always(f"[=] Final CSV size: {final_size:,} bytes ({final_size / (1024**3):.2f} GB)")
                    logger.print_always(f"[F] Location: {self.csv_file}")
                    logger.print_always(f"[OK] Installation verified")

                    # Save metadata with download timestamp
                    logger.print_always(f"\n[D] Saving download metadata...")
                    version = "download-" + datetime.now().strftime("%Y%m%d")
                    optimized_at = datetime.now().isoformat()

                    logger.print_always(f"[N] Version: {version}")
                    logger.print_always(f"[N] Timestamp: {optimized_at}")

                    # Save using the standard metadata format
                    self._save_metadata(version, optimized_at)
                    logger.print_always(f"[OK] Metadata saved")

                    if progress_callback:
                        progress_callback("[Complete] Database ready!", 100)

                    logger.print_always(f"\n" + "="*80)
                    logger.print_always(f"[OK] DATABASE DOWNLOAD COMPLETED SUCCESSFULLY")
                    logger.print_always(f"="*80)
                    logger.print_always(f"[=] Summary:")
                    logger.print_always(f"   URL: {download_url}")
                    logger.print_always(f"   Size: {final_size:,} bytes ({final_size / (1024**3):.2f} GB)")
                    logger.print_always(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.print_always(f"="*80)

                    return True

                except (httpx.HTTPError, httpx.RequestError) as e:
                    logger.print_always(f"\n[!] REQUEST EXCEPTION on attempt {attempt + 1}/{max_retries}")
                    logger.print_always(f"[X] Exception type: {type(e).__name__}")
                    logger.print_always(f"[X] Error: {e}")

                    if hasattr(e, 'response'):
                        logger.print_always(f"[LIST] HTTP Response:")
                        logger.print_always(f"   Status: {e.response.status_code}")
                        logger.print_always(f"   Headers: {dict(e.response.headers)}")

                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        import random
                        sleep_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.print_always(f"\n[R] Retrying in {sleep_time:.1f} seconds...")

                        if progress_callback:
                            progress_callback(f"Retry in {int(sleep_time)}s...", 5)

                        time.sleep(sleep_time)
                    else:
                        logger.print_always(f"\n[X] All {max_retries} download attempts exhausted")
                        raise

                except Exception as e:
                    logger.print_always(f"\n[!] UNEXPECTED EXCEPTION on attempt {attempt + 1}/{max_retries}")
                    logger.print_always(f"[X] Exception type: {type(e).__name__}")
                    logger.print_always(f"[X] Error: {e}")
                    import traceback
                    logger.print_always(f"[LIST] Traceback:\n{traceback.format_exc()}")
                    raise

            logger.print_always(f"\n[X] Download failed after {max_retries} attempts")
            return False

        except Exception as e:
            logger.print_always(f"\n" + "="*80)
            logger.print_always(f"[X] DATABASE DOWNLOAD FAILED")
            logger.print_always(f"="*80)
            logger.print_always(f"[!] Exception type: {type(e).__name__}")
            logger.print_always(f"[X] Error message: {e}")
            import traceback
            logger.print_always(f"[LIST] Full traceback:\n{traceback.format_exc()}")
            logger.print_always(f"="*80)

            if progress_callback:
                progress_callback(f"Download failed: {str(e)}", 0)

            return False

    def manual_import_database(self, file_path: str, progress_callback: Optional[Callable] = None) -> bool:
        """
        Manually import MusicBrainz canonical data file.

        Accepts:
        - .tar.zst files (compressed archive, recommended)
        - .csv files (canonical_musicbrainz_data.csv)
        - .tsv files (tab-separated)

        Expected CSV format:
        - Columns: id, artist_credit_id, artist_mbids, artist_credit_name,
                   release_mbid, release_name, recording_mbid, recording_name,
                   combined_lookup, score
        """
        try:
            logger.info(f"\n{'='*80}")
            logger.debug(f"[R] MANUAL IMPORT DEBUG - START")
            logger.info(f"{'='*80}")
            logger.info(f"[F] File path: {file_path}")
            logger.info("Manual import from %s", file_path)
            file_path_obj = Path(file_path)

            if not file_path_obj.exists():
                error_msg = f"Error: File not found: {file_path}"
                logger.error(f"[X] {error_msg}")
                if progress_callback:
                    progress_callback(error_msg, 0)
                logger.error(f"File not found: {file_path}")
                return False

            file_extension = file_path_obj.suffix.lower()
            logger.info(f"[N] Initial extension detected: {file_extension}")

            # Handle .tar.zst extension (e.g., file.tar.zst)
            if file_path_obj.name.endswith('.tar.zst'):
                file_extension = '.tar.zst'
                logger.info(f"[N] Corrected extension to: {file_extension} (detected .tar.zst)")

            file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
            logger.print_always(f"[=] File size: {file_size_mb:.2f} MB")

            if progress_callback:
                progress_callback(f"Validating file format: {file_extension}", 10)

            # Check file extension
            logger.debug(f"[?] Checking if extension '{file_extension}' is valid...")
            logger.info(f"   Valid extensions: ['.csv', '.tsv', '.tar.zst']")
            if file_extension not in ['.csv', '.tsv', '.tar.zst']:
                error_msg = f"Error: Invalid format '{file_extension}'. Expected .tar.zst, .csv, or .tsv (MusicBrainz canonical data)"
                logger.error(f"[X] {error_msg}")
                if progress_callback:
                    progress_callback(error_msg, 0)
                logger.error(f"Invalid file extension: {file_extension}")
                return False

            logger.print_always(f"[OK] Extension '{file_extension}' is valid")

            # If tar.zst, extract it first
            if file_extension == '.tar.zst':
                logger.info(f"\n[P] Extracting .tar.zst archive...")
                if progress_callback:
                    progress_callback("Extracting compressed archive...", 20)

                try:
                    logger.info(f"   Importing required modules...")
                    import tarfile
                    import tempfile
                    import zstandard as zstd
                    logger.print_always(f"   [OK] Modules imported successfully")

                    # Create extraction directory
                    extract_dir = Path(tempfile.mkdtemp(prefix='musicbrainz_extract_'))
                    logger.info(f"   [F] Created extraction directory: {extract_dir}")
                    logger.info(f"Extracting to: {extract_dir}")

                    # Decompress and extract
                    logger.info(f"   [U] Opening compressed file...")
                    with open(file_path_obj, 'rb') as compressed:
                        logger.info(f"   [U] Creating ZStandard decompressor...")
                        dctx = zstd.ZstdDecompressor()
                        logger.info(f"   [U] Creating stream reader...")
                        with dctx.stream_reader(compressed) as reader:
                            logger.info(f"   [FOLDER] Opening tar archive...")
                            with tarfile.open(fileobj=reader, mode='r|') as tar:
                                logger.info(f"   [FOLDER] Extracting files from tar archive...")
                                tar.extractall(path=extract_dir)
                                logger.print_always(f"   [OK] Extraction complete!")

                    # Find the CSV file
                    logger.debug(f"\n   [?] Searching for CSV files in extraction directory...")
                    csv_candidates = list(extract_dir.rglob("*.csv"))
                    logger.print_always(f"   [=] Found {len(csv_candidates)} CSV file(s)")

                    if not csv_candidates:
                        error_msg = "Error: No CSV file found in archive"
                        logger.error(f"   [X] {error_msg}")
                        logger.info(f"   [F] Contents of {extract_dir}:")
                        for item in extract_dir.rglob("*"):
                            logger.info(f"      - {item.name} ({item.stat().st_size} bytes)")
                        if progress_callback:
                            progress_callback(error_msg, 0)
                        logger.error("No CSV found in tar.zst archive")
                        return False

                    # Use the largest CSV file (canonical data)
                    file_path_obj = max(csv_candidates, key=lambda p: p.stat().st_size)
                    file_extension = '.csv'
                    file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)

                    logger.print_always(f"   [OK] Selected CSV: {file_path_obj.name} ({file_size_mb:.1f} MB)")
                    logger.info(f"Extracted CSV: {file_path_obj} ({file_size_mb:.1f} MB)")
                    if progress_callback:
                        progress_callback(f"Extracted {file_size_mb:.1f} MB CSV file", 40)

                except Exception as e:
                    error_msg = f"Error extracting archive: {str(e)}"
                    logger.error(f"   [X] {error_msg}")
                    import traceback
                    logger.debug(f"   [?] Traceback:")
                    traceback.print_exc()
                    if progress_callback:
                        progress_callback(error_msg, 0)
                    logger.error(f"Extraction failed: {e}", exc_info=True)
                    return False

            # Basic size validation (canonical data CSV is typically 25-30 GB)
            logger.info(f"\n[RULER] Validating file size...")
            logger.info(f"   File size: {file_size_mb:.1f} MB")
            if file_size_mb < 1000:  # Less than 1GB is suspiciously small
                warning_msg = f"File is only {file_size_mb:.1f} MB (expected ~28GB)"
                logger.warning(f"   [!]  {warning_msg}")
                logger.warning(f"File size {file_size_mb:.1f} MB seems small for canonical data (expected ~28GB)")
                if progress_callback:
                    progress_callback(
                        f"Warning: {warning_msg}. Continuing anyway...",
                        50
                    )
            else:
                logger.print_always(f"   [OK] File size looks good")

            # Validate CSV structure (check first few lines)
            logger.debug(f"\n[?] Validating CSV structure...")
            if progress_callback:
                progress_callback("Validating CSV structure...", 60)

            try:
                logger.info(f"   [BOOK] Reading first line of CSV...")
                with open(file_path_obj, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    logger.info(f"   [N] First line (first 200 chars): {first_line[:200]}...")

                    # Check for expected columns
                    expected_columns = [
                        'id', 'artist_credit_id', 'artist_mbids', 'artist_credit_name',
                        'release_mbid', 'release_name', 'recording_mbid', 'recording_name',
                        'combined_lookup', 'score'
                    ]
                    logger.info(f"   [LIST] Expected columns: {', '.join(expected_columns[:4])}...")

                    # Handle both CSV and TSV delimiters
                    delimiter = '\t' if file_extension == '.tsv' else ','
                    logger.info(f"   [LIST] Using delimiter: {'TAB' if delimiter == '\\t' else 'COMMA'}")
                    header_columns = [col.strip() for col in first_line.split(delimiter)]
                    logger.info(f"   [LIST] Found columns ({len(header_columns)}): {', '.join(header_columns[:5])}...")

                    # Check if header matches (allow some flexibility)
                    matches = [expected_col in header_columns for expected_col in expected_columns[:3]]
                    logger.debug(f"   [?] Column match check: {matches}")
                    if not any(matches):
                        error_msg = f"CSV structure doesn't match MusicBrainz canonical format. Expected columns like: {', '.join(expected_columns[:4])}..."
                        logger.error(f"   [X] {error_msg}")
                        logger.error(f"   [X] Found columns: {', '.join(header_columns[:5])}")
                        if progress_callback:
                            progress_callback(f"Error: {error_msg}", 0)
                        logger.error(f"CSV header doesn't match expected format. Found: {header_columns[:5]}")
                        return False

                    logger.print_always(f"   [OK] CSV structure validation passed")

            except Exception as e:
                logger.warning(f"   [!]  CSV validation warning: {e}")
                logger.warning(f"CSV validation warning: {e}")
                # Continue anyway if we can't validate structure

            # Copy file to destination
            logger.info(f"\n[LIST] Copying file to database location...")
            logger.info(f"   Source: {file_path_obj}")
            logger.info(f"   Destination: {self.csv_file}")
            logger.info(f"   Size: {file_size_mb:.1f} MB")
            if progress_callback:
                progress_callback(f"Copying {file_size_mb:.1f} MB to {self.csv_file}...", 70)

            logger.info(f"   [F] Creating canonical directory: {self.canonical_dir}")
            self.canonical_dir.mkdir(parents=True, exist_ok=True)
            logger.print_always(f"   [OK] Directory created/verified")

            # Use shutil.copy2 to preserve metadata
            logger.info(f"   [LIST] Starting file copy...")
            shutil.copy2(file_path_obj, self.csv_file)
            logger.print_always(f"   [OK] File copied successfully to: {self.csv_file}")

            if progress_callback:
                progress_callback("Clearing old optimization data...", 80)

            # Clear optimization state to force rebuild
            logger.info(f"\n[R] Clearing old optimization data...")
            self._optimization_complete = False
            self._optimization_in_progress = False

            if self.duckdb_file.exists():
                logger.info(f"   [DEL]  Removing old DuckDB file: {self.duckdb_file}")
                if self._conn:
                    try:
                        self._conn.close()
                        self._conn = None
                        logger.print_always(f"   [OK] Closed DuckDB connection")
                    except Exception as close_err:
                        logger.warning(f"   [!]  Error closing connection: {close_err}")
                self.duckdb_file.unlink()
                logger.print_always(f"   [OK] DuckDB file removed")

            # Clear metadata to force re-check
            if self.meta_file.exists():
                logger.info(f"   [DEL]  Removing old metadata file: {self.meta_file}")
                self.meta_file.unlink()
                logger.print_always(f"   [OK] Metadata file removed")

            # Update metadata
            logger.print_always(f"\n[D] Saving new metadata...")
            from datetime import datetime
            version = "manual-" + datetime.now().strftime("%Y%m%d")
            optimized_at = datetime.now().isoformat()

            self._save_metadata(version, optimized_at)
            logger.print_always(f"   [OK] Metadata saved (version: {version}, timestamp: {optimized_at})")

            if progress_callback:
                progress_callback("Import complete!", 100)

            logger.info(f"\n{'='*80}")
            logger.print_always(f"[OK] MANUAL IMPORT SUCCESSFUL")
            logger.info(f"{'='*80}")
            logger.print_always(f"[=] File size: {file_size_mb:.1f} MB")
            logger.info(f"[F] Saved to: {self.csv_file}")
            logger.info(f"{'='*80}\n")

            logger.info(f"Manual import successful: {file_size_mb:.1f} MB")
            return True

        except Exception as e:
            logger.info(f"\n{'='*80}")
            logger.error(f"[X] MANUAL IMPORT FAILED - EXCEPTION CAUGHT")
            logger.info(f"{'='*80}")
            logger.error(f"Error: {str(e)}")
            import traceback
            logger.info(f"Traceback:")
            traceback.print_exc()
            logger.info(f"{'='*80}\n")

            logger.error(f"Manual import error: {e}")
            if progress_callback:
                progress_callback(f"Import failed: {str(e)}", 0)
            return False

    def cancel_download(self):
        """Cancel the current download operation."""
        self._cancellation_requested = True
        logger.info("Download cancellation requested")
        logger.info("[STOP] Download cancellation requested...")

    def delete_database(self) -> bool:
        """Delete MusicBrainz database files."""
        try:
            deleted = False

            if self.csv_file.exists():
                self.csv_file.unlink()
                deleted = True

            if self.duckdb_file.exists():
                if self._conn:
                    self._conn.close()
                    self._conn = None
                self.duckdb_file.unlink()
                deleted = True

            wal_path = Path(str(self.duckdb_file) + ".wal")
            if wal_path.exists():
                wal_path.unlink()

            if self.meta_file.exists():
                self.meta_file.unlink()

            self._optimization_complete = False
            self._optimization_in_progress = False

            return deleted

        except Exception as e:
            logger.error(f"Delete error: {e}")
            return False

    def check_for_updates(self) -> Tuple[bool, str]:
        """
        Check if a newer MusicBrainz canonical data dump is available.

        MusicBrainz canonical data is updated twice per month (1st and 15th).
        Compares the current database file timestamp with available versions.

        Returns:
            (has_updates, message): Tuple of update status and informational message
        """
        import httpx
        from datetime import datetime
        import re

        BASE_URL = "https://data.metabrainz.org/pub/musicbrainz/canonical_data/"

        try:
            # Check if we have a database to compare against
            if not self.csv_file.exists():
                return False, "No database installed. Please download first."

            # Get local database info
            local_metadata = self._load_metadata()
            local_timestamp = local_metadata.get("last_updated", "Unknown")

            # Try to parse local date
            try:
                if local_timestamp != "Unknown":
                    from dateutil import parser
                    local_date = parser.parse(local_timestamp)
                else:
                    # Fall back to file modification time
                    local_date = datetime.fromtimestamp(self.csv_file.stat().st_mtime)
            except:
                local_date = datetime.fromtimestamp(self.csv_file.stat().st_mtime)

            # Fetch directory listing
            logger.info("Checking for MusicBrainz updates...")
            response = httpx.get(BASE_URL, timeout=30)
            response.raise_for_status()

            # Parse HTML to find dated subdirectories (e.g., musicbrainz-canonical-dump-20251003-080003/)
            subdir_pattern = r'href="(musicbrainz-canonical-dump-(\d{8})-\d+/)\"'
            subdir_matches = re.findall(subdir_pattern, response.text)

            if not subdir_matches:
                return False, "Could not find canonical data directories on server."

            # Sort by date and get the latest subdirectory
            dated_subdirs = [(match[0], match[1]) for match in subdir_matches]
            dated_subdirs.sort(key=lambda x: x[1], reverse=True)
            latest_subdir, latest_date_str = dated_subdirs[0]

            # Try to extract date from subdirectory name
            date_match = re.search(r'(\d{8})', latest_subdir)
            if date_match:
                date_str = date_match.group(1)
                try:
                    server_date = datetime.strptime(date_str, '%Y%m%d')

                    # Compare dates
                    if server_date > local_date:
                        days_diff = (server_date - local_date).days
                        return True, (
                            f"Update available!\n\n"
                            f"Your database: {local_date.strftime('%Y-%m-%d')}\n"
                            f"Latest version: {server_date.strftime('%Y-%m-%d')}\n"
                            f"({days_diff} days newer)\n\n"
                            f"MusicBrainz canonical data is updated twice per month (1st and 15th)."
                        )
                    else:
                        return False, (
                            f"Your database is up to date!\n\n"
                            f"Current version: {local_date.strftime('%Y-%m-%d')}\n"
                            f"Latest available: {server_date.strftime('%Y-%m-%d')}"
                        )
                except:
                    pass

            # If we can't parse dates, compare subdirectories
            if latest_subdir not in local_metadata.get("download_url", ""):
                return True, (
                    f"A newer version may be available.\n\n"
                    f"Latest version: {latest_subdir}\n\n"
                    f"Your current version was last updated: {local_date.strftime('%Y-%m-%d')}"
                )
            else:
                return False, "Your database appears to be up to date."

        except (httpx.HTTPError, httpx.RequestError) as e:
            logger.error(f"Update check failed (network error): {e}")
            return False, f"Could not check for updates: Network error ({str(e)})"
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return False, f"Could not check for updates: {str(e)}"

    def get_database_info(self) -> dict:
        """Get database information."""
        info = {
            "exists": False,
            "size_mb": 0,
            "last_updated": "Unknown",
            "version": "V2-Optimized",
            "track_count": 0,
            "type": "DuckDB Ultra-Optimized"
        }

        if self.csv_file.exists():
            info["exists"] = True
            info["size_mb"] = round(self.csv_file.stat().st_size / (1024 * 1024), 1)

        if self.duckdb_file.exists():
            info["type"] = "DuckDB Ultra-Optimized (Ready)" if self._optimization_complete else "DuckDB (Optimizing...)"
            db_size = self.duckdb_file.stat().st_size / (1024 * 1024)
            info["size_mb"] += round(db_size, 1)

        # Reload metadata to get latest values
        metadata = self._load_metadata()
        if metadata:
            info["version"] = metadata.get("version", "V2-Optimized")
            info["last_updated"] = metadata.get("optimized_at", "Unknown")
            info["track_count"] = metadata.get("track_count", 0)

        return info

    def close(self):
        """Explicitly close DuckDB connection to prevent GIL issues during shutdown.

        This should be called before application exit to ensure clean shutdown.
        """
        if self._conn:
            try:
                logger.print_always("[L] Closing DuckDB connection...")
                self._conn.close()
                self._conn = None
                logger.print_always("[OK] DuckDB connection closed successfully")
            except Exception as e:
                logger.print_always(f"[!]  Error closing DuckDB connection: {e}")
                self._conn = None

    def __del__(self):
        """Clean up during garbage collection.

        Note: Relying on __del__ during Python shutdown can cause GIL issues.
        Always call close() explicitly before app exit.
        """
        if self._conn:
            try:
                self._conn.close()
            except:
                pass
    def _search_fuzzy_exact_combined(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str]) -> Optional[str]:
        """Search BOTH hot and cold tables for exact match, combine results for scoring."""
        logger.debug(f"   [R] Searching fuzzy_exact in BOTH hot and cold tables")

        # Query both tables
        hot_rows = self._query_fuzzy_exact(clean_track, artist_hint, album_hint, use_hot=True)
        cold_rows = self._query_fuzzy_exact(clean_track, artist_hint, album_hint, use_hot=False)

        # Combine results
        all_rows = list(hot_rows) + list(cold_rows)
        logger.debug(f"   [=] Combined {len(hot_rows)} hot + {len(cold_rows)} cold = {len(all_rows)} total candidates")

        return self._choose_candidate(all_rows, artist_hint, album_hint, clean_track)

    def _search_fuzzy_prefix_combined(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str]) -> Optional[str]:
        """Search BOTH hot and cold tables for prefix match, combine results for scoring."""
        logger.debug(f"   [R] Searching fuzzy_prefix in BOTH hot and cold tables")

        hot_rows = self._query_fuzzy_prefix(clean_track, artist_hint, album_hint, use_hot=True)
        cold_rows = self._query_fuzzy_prefix(clean_track, artist_hint, album_hint, use_hot=False)

        all_rows = list(hot_rows) + list(cold_rows)
        logger.debug(f"   [=] Combined {len(hot_rows)} hot + {len(cold_rows)} cold = {len(all_rows)} total candidates")

        return self._choose_candidate(all_rows, artist_hint, album_hint, clean_track)

    def _search_fuzzy_contains_combined(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str]) -> Optional[str]:
        """Search BOTH hot and cold tables for contains match, combine results for scoring."""
        logger.debug(f"   [R] Searching fuzzy_contains in BOTH hot and cold tables")

        hot_rows = self._query_fuzzy_contains(clean_track, artist_hint, album_hint, use_hot=True)
        cold_rows = self._query_fuzzy_contains(clean_track, artist_hint, album_hint, use_hot=False)

        all_rows = list(hot_rows) + list(cold_rows)
        logger.debug(f"   [=] Combined {len(hot_rows)} hot + {len(cold_rows)} cold = {len(all_rows)} total candidates")

        return self._choose_candidate(all_rows, artist_hint, album_hint, clean_track)

    def _query_fuzzy_exact(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str], use_hot: bool) -> List[Tuple]:
        """Query exact match from specified table with dynamic ORDER BY based on hints."""
        table = "musicbrainz_hot" if use_hot else "musicbrainz_cold"

        # Build dynamic ORDER BY based on which hints are provided
        if artist_hint and album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    (release_name ILIKE ?) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%", f"%{album_hint}%"]
        elif artist_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%"]
        elif album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY
                    (release_name ILIKE ?) DESC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{album_hint}%"]
        else:
            # CRITICAL FIX: ORDER BY score ASC - lower score = more established track
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean = ?
                ORDER BY score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track]

        try:
            return self._conn.execute(sql, params).fetchall()
        except Exception:
            logger.exception(f"fuzzy_exact query failed for '{clean_track}' in {table}")
            return []

    def _query_fuzzy_prefix(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str], use_hot: bool) -> List[Tuple]:
        """Query prefix match from specified table with dynamic ORDER BY based on hints."""
        table = "musicbrainz_hot" if use_hot else "musicbrainz_cold"

        # Build dynamic ORDER BY based on which hints are provided
        if artist_hint and album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%", f"%{album_hint}%"]
        elif artist_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%"]
        elif album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{album_hint}%"]
        else:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE ? || '%'
                ORDER BY
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track]

        try:
            return self._conn.execute(sql, params).fetchall()
        except Exception:
            logger.exception(f"fuzzy_prefix query failed for '{clean_track}' in {table}")
            return []

    def _query_fuzzy_contains(self, clean_track: str, artist_hint: Optional[str], album_hint: Optional[str], use_hot: bool) -> List[Tuple]:
        """Query contains match from specified table with dynamic ORDER BY based on hints."""
        table = "musicbrainz_hot" if use_hot else "musicbrainz_cold"

        # Build dynamic ORDER BY based on which hints are provided
        if artist_hint and album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%", f"%{album_hint}%"]
        elif artist_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY
                    (artist_credit_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{artist_hint}%"]
        elif album_hint:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY
                    (release_name ILIKE ?) DESC,
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track, f"%{album_hint}%"]
        else:
            sql = f"""
                SELECT artist_credit_name, release_name, score
                FROM {table}
                WHERE recording_clean LIKE '%' || ? || '%'
                ORDER BY
                    length(recording_clean) ASC,
                    score ASC
                LIMIT {SEARCH_ROW_LIMIT}
            """
            params = [clean_track]

        try:
            return self._conn.execute(sql, params).fetchall()
        except Exception:
            logger.exception(f"fuzzy_contains query failed for '{clean_track}' in {table}")
            return []
