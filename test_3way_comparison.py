#!/usr/bin/env python3
"""
3-Way Album Matching Comparison Test

Compares album matching accuracy across three sources:
1. Offline DuckDB (MusicBrainz database)
2. MusicBrainz API (online, authoritative)
3. iTunes API (online, alternative)

Methodology:
- Sample 200 tracks from real CSV
- Search each track in all three sources
- Compare album matches to identify discrepancies
- Rate limit: 1 second per track for API calls
"""

import sys
import os
import time
import pandas as pd
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from apple_music_history_converter.musicbrainz_manager_v2_optimized import MusicBrainzManagerV2Optimized as MusicBrainzManagerV2
from apple_music_history_converter.app_directories import get_database_dir


@dataclass
class SearchResult:
    """Unified search result structure"""
    track_name: str
    artist_name: str
    album_name: Optional[str]
    source: str
    confidence: float = 0.0
    found: bool = False


class ThreeWayComparison:
    """Compare album matching across offline DB and online APIs"""

    def __init__(self):
        self.mb_manager = None
        self.results = []
        self.api_delay = 1.0  # 1 second between API calls

    def initialize_offline_db(self) -> bool:
        """Initialize offline MusicBrainz database"""
        try:
            print("\n🔧 Initializing offline MusicBrainz database...")
            data_dir = str(get_database_dir())
            self.mb_manager = MusicBrainzManagerV2(data_dir)

            if not self.mb_manager.is_ready():
                print("❌ Offline database not ready. Please optimize database first.")
                return False

            print("✅ Offline database ready")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize offline DB: {e}")
            return False

    def sample_tracks_from_csv(self, csv_path: str, sample_size: int = 200) -> List[Dict]:
        """Sample tracks from real CSV file"""
        try:
            print(f"\n📊 Sampling {sample_size} tracks from CSV...")

            # Read CSV
            df = pd.read_csv(csv_path, encoding='utf-8-sig')

            # Detect columns (handle different CSV formats)
            artist_col = None
            track_col = None

            for col in df.columns:
                col_lower = col.lower()
                if 'artist' in col_lower and not artist_col:
                    artist_col = col
                elif 'song' in col_lower or 'track' in col_lower and not track_col:
                    track_col = col

            if not artist_col or not track_col:
                print(f"❌ Could not find artist/track columns. Columns: {df.columns.tolist()}")
                return []

            print(f"   Using columns: Artist='{artist_col}', Track='{track_col}'")

            # Sample tracks (skip rows with missing values)
            df_clean = df[[artist_col, track_col]].dropna()

            # Take random sample
            if len(df_clean) > sample_size:
                df_sample = df_clean.sample(n=sample_size, random_state=42)
            else:
                df_sample = df_clean

            tracks = []
            for _, row in df_sample.iterrows():
                tracks.append({
                    'artist': str(row[artist_col]).strip(),
                    'track': str(row[track_col]).strip()
                })

            print(f"✅ Sampled {len(tracks)} tracks")
            return tracks

        except Exception as e:
            print(f"❌ Error sampling tracks: {e}")
            return []

    def search_offline_db(self, artist: str, track: str) -> SearchResult:
        """Search in offline DuckDB"""
        try:
            if not self.mb_manager:
                return SearchResult(track, artist, None, "Offline DB", found=False)

            # Use the search method (returns artist name only)
            artist_result = self.mb_manager.search(
                track_name=track,
                artist_hint=artist,
                album_hint=None  # Don't provide album hint for fair comparison
            )

            if artist_result:
                # Get album by querying the database directly
                album = self._get_album_from_db(track, artist_result)

                return SearchResult(
                    track_name=track,
                    artist_name=artist_result,
                    album_name=album,
                    source="Offline DB",
                    confidence=1.0,
                    found=True
                )
            else:
                return SearchResult(track, artist, None, "Offline DB", found=False)

        except Exception as e:
            print(f"   ⚠️ Offline DB error: {e}")
            return SearchResult(track, artist, None, "Offline DB", found=False)

    def _get_album_from_db(self, track: str, artist: str) -> Optional[str]:
        """Get album name by querying DuckDB directly"""
        try:
            clean_track = self.mb_manager.clean_text_conservative(track)

            # Search for the track with matching artist
            sql = """
                SELECT release_name
                FROM musicbrainz_hot
                WHERE recording_clean = ?
                  AND artist_credit_name = ?
                LIMIT 1
            """

            result = self.mb_manager._conn.execute(sql, [clean_track, artist]).fetchone()

            if result:
                return result[0]

            # Try COLD table if not found in HOT
            sql = """
                SELECT release_name
                FROM musicbrainz_cold
                WHERE recording_clean = ?
                  AND artist_credit_name = ?
                LIMIT 1
            """

            result = self.mb_manager._conn.execute(sql, [clean_track, artist]).fetchone()

            if result:
                return result[0]

            return None

        except Exception:
            return None

    def search_musicbrainz_api(self, artist: str, track: str) -> SearchResult:
        """Search using MusicBrainz API (authoritative source)"""
        try:
            # Respect rate limit
            time.sleep(self.api_delay)

            # Build query with fuzzy matching (no quotes for better results)
            # MusicBrainz uses Lucene query syntax
            query = f'artist:{artist} AND recording:{track}'

            url = "https://musicbrainz.org/ws/2/recording/"
            params = {
                'query': query,
                'fmt': 'json',
                'limit': 10  # Get more results for better matching
            }

            headers = {
                'User-Agent': 'AppleMusicConverter/2.0 (nerveband@gmail.com)'
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                print(f"   ⚠️ MusicBrainz API status: {response.status_code}")
                return SearchResult(track, artist, None, "MusicBrainz API", found=False)

            data = response.json()
            recordings = data.get('recordings', [])

            if not recordings:
                return SearchResult(track, artist, None, "MusicBrainz API", found=False)

            # Filter results by minimum score threshold (80+)
            good_matches = [r for r in recordings if r.get('score', 0) >= 80]

            if not good_matches:
                # No high-confidence matches
                return SearchResult(track, artist, None, "MusicBrainz API", found=False)

            # Get best result (highest score)
            best_match = good_matches[0]

            # Extract artist name
            artist_name = artist
            if best_match.get('artist-credit'):
                artist_name = best_match['artist-credit'][0].get('name', artist)

            # Extract album - prefer primary type releases over compilations
            album = None
            if 'releases' in best_match and best_match['releases']:
                # Try to find a primary album release
                for release in best_match['releases']:
                    release_type = release.get('release-group', {}).get('primary-type', '')
                    if release_type == 'Album':
                        album = release.get('title')
                        break

                # Fallback to first release if no album found
                if not album:
                    album = best_match['releases'][0].get('title')

            return SearchResult(
                track_name=best_match.get('title', track),
                artist_name=artist_name,
                album_name=album,
                source="MusicBrainz API",
                confidence=best_match.get('score', 0) / 100.0,
                found=True
            )

        except requests.Timeout:
            print(f"   ⏱️ MusicBrainz API timeout")
            return SearchResult(track, artist, None, "MusicBrainz API", found=False)
        except Exception as e:
            print(f"   ⚠️ MusicBrainz API error: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            return SearchResult(track, artist, None, "MusicBrainz API", found=False)

    def search_itunes_api(self, artist: str, track: str) -> SearchResult:
        """Search using iTunes API"""
        try:
            # Respect rate limit
            time.sleep(self.api_delay)

            url = "https://itunes.apple.com/search"
            params = {
                'term': f'{artist} {track}',
                'media': 'music',
                'entity': 'song',
                'limit': 5
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                return SearchResult(track, artist, None, "iTunes API", found=False)

            data = response.json()
            results = data.get('results', [])

            if not results:
                return SearchResult(track, artist, None, "iTunes API", found=False)

            # Get first result
            best_match = results[0]

            return SearchResult(
                track_name=best_match.get('trackName', track),
                artist_name=best_match.get('artistName', artist),
                album_name=best_match.get('collectionName'),
                source="iTunes API",
                confidence=1.0,  # iTunes doesn't provide scores
                found=True
            )

        except requests.Timeout:
            print(f"   ⏱️ iTunes API timeout")
            return SearchResult(track, artist, None, "iTunes API", found=False)
        except Exception as e:
            print(f"   ⚠️ iTunes API error: {e}")
            return SearchResult(track, artist, None, "iTunes API", found=False)

    def compare_track(self, artist: str, track: str, index: int, total: int) -> Dict:
        """Compare a single track across all three sources"""
        print(f"\n[{index}/{total}] 🎵 {artist} - {track}")

        # Search all sources
        offline_result = self.search_offline_db(artist, track)
        print(f"   📀 Offline DB: {'✅ ' + (offline_result.album_name or 'No album') if offline_result.found else '❌ Not found'}")

        mb_result = self.search_musicbrainz_api(artist, track)
        print(f"   🌐 MusicBrainz: {'✅ ' + (mb_result.album_name or 'No album') if mb_result.found else '❌ Not found'}")

        itunes_result = self.search_itunes_api(artist, track)
        print(f"   🍎 iTunes: {'✅ ' + (itunes_result.album_name or 'No album') if itunes_result.found else '❌ Not found'}")

        # Compare albums
        comparison = {
            'artist': artist,
            'track': track,
            'offline_found': offline_result.found,
            'offline_album': offline_result.album_name,
            'mb_found': mb_result.found,
            'mb_album': mb_result.album_name,
            'itunes_found': itunes_result.found,
            'itunes_album': itunes_result.album_name,
            'albums_match': False,
            'offline_correct': False
        }

        # Check if albums match
        if offline_result.album_name and mb_result.album_name:
            comparison['albums_match'] = offline_result.album_name.lower() == mb_result.album_name.lower()
            comparison['offline_correct'] = comparison['albums_match']

        return comparison

    def run_comparison(self, csv_path: str, sample_size: int = 200):
        """Run full 3-way comparison"""
        print("=" * 80)
        print("🔬 3-Way Album Matching Comparison Test")
        print("=" * 80)

        # Initialize
        if not self.initialize_offline_db():
            return

        # Sample tracks
        tracks = self.sample_tracks_from_csv(csv_path, sample_size)
        if not tracks:
            return

        print(f"\n⏱️ Estimated time: ~{len(tracks) * self.api_delay * 2 / 60:.1f} minutes (2 APIs × {self.api_delay}s per track)")
        print("\nStarting comparison...")

        # Compare each track
        comparisons = []
        start_time = time.time()

        for i, track_info in enumerate(tracks, 1):
            comparison = self.compare_track(
                track_info['artist'],
                track_info['track'],
                i,
                len(tracks)
            )
            comparisons.append(comparison)

        elapsed = time.time() - start_time

        # Generate report
        self.generate_report(comparisons, elapsed)

    def generate_report(self, comparisons: List[Dict], elapsed_time: float):
        """Generate detailed comparison report"""
        print("\n" + "=" * 80)
        print("📊 COMPARISON REPORT")
        print("=" * 80)

        total = len(comparisons)

        # Count results
        offline_found = sum(1 for c in comparisons if c['offline_found'])
        mb_found = sum(1 for c in comparisons if c['mb_found'])
        itunes_found = sum(1 for c in comparisons if c['itunes_found'])

        offline_has_album = sum(1 for c in comparisons if c['offline_album'])
        mb_has_album = sum(1 for c in comparisons if c['mb_album'])
        itunes_has_album = sum(1 for c in comparisons if c['itunes_album'])

        albums_match = sum(1 for c in comparisons if c['albums_match'])

        # Print statistics
        print(f"\n⏱️ Time taken: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
        print(f"\n📈 SEARCH SUCCESS RATES:")
        print(f"   Offline DB:     {offline_found}/{total} ({offline_found/total*100:.1f}%)")
        print(f"   MusicBrainz API: {mb_found}/{total} ({mb_found/total*100:.1f}%)")
        print(f"   iTunes API:      {itunes_found}/{total} ({itunes_found/total*100:.1f}%)")

        print(f"\n💿 ALBUM FOUND RATES:")
        print(f"   Offline DB:     {offline_has_album}/{total} ({offline_has_album/total*100:.1f}%)")
        print(f"   MusicBrainz API: {mb_has_album}/{total} ({mb_has_album/total*100:.1f}%)")
        print(f"   iTunes API:      {itunes_has_album}/{total} ({itunes_has_album/total*100:.1f}%)")

        if mb_has_album > 0:
            accuracy = albums_match / mb_has_album * 100
            print(f"\n🎯 OFFLINE DB ACCURACY (vs MusicBrainz API):")
            print(f"   Albums matching: {albums_match}/{mb_has_album} ({accuracy:.1f}%)")

            if accuracy >= 95:
                print(f"   ✅ EXCELLENT - Offline DB is highly accurate!")
            elif accuracy >= 80:
                print(f"   ⚠️ GOOD - Some discrepancies found")
            else:
                print(f"   ❌ NEEDS IMPROVEMENT - Significant discrepancies")

        # Show discrepancies
        discrepancies = [c for c in comparisons if c['offline_album'] and c['mb_album'] and not c['albums_match']]

        if discrepancies:
            print(f"\n❌ DISCREPANCIES ({len(discrepancies)} found):")
            for i, disc in enumerate(discrepancies[:20], 1):  # Show first 20
                print(f"\n{i}. {disc['artist']} - {disc['track']}")
                print(f"   Offline:    {disc['offline_album']}")
                print(f"   MusicBrainz: {disc['mb_album']}")
                if disc['itunes_album']:
                    print(f"   iTunes:     {disc['itunes_album']}")

            if len(discrepancies) > 20:
                print(f"\n   ... and {len(discrepancies) - 20} more discrepancies")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")

        if albums_match / mb_has_album >= 0.95 if mb_has_album > 0 else False:
            print("   ✅ Offline DB algorithm is working well!")
            print("   ✅ No changes needed to scoring algorithm")
        else:
            print("   ⚠️ Consider adjusting offline DB scoring:")
            print("   1. Review album matching weight in scoring algorithm")
            print("   2. Check if album hints are being properly utilized")
            print("   3. Verify artist name normalization matches API behavior")
            print("   4. Test with stricter album name matching")

        print("\n" + "=" * 80)


def main():
    """Main entry point"""

    # Check for CSV file argument
    if len(sys.argv) < 2:
        print("Usage: python test_3way_comparison.py <csv_file> [sample_size]")
        print("\nExample:")
        print("  python test_3way_comparison.py ~/Music/apple_music_history.csv 200")

        # Try to find a CSV file in common locations
        common_paths = [
            Path.home() / "Music" / "Apple Music Play Activity.csv",
            Path.home() / "Downloads" / "Apple Music Play Activity.csv",
            Path.home() / "Desktop" / "Apple Music Play Activity.csv",
        ]

        for path in common_paths:
            if path.exists():
                print(f"\n💡 Found CSV at: {path}")
                csv_path = str(path)
                break
        else:
            print("\n❌ No CSV file found. Please specify path.")
            return
    else:
        csv_path = sys.argv[1]

    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    # Verify file exists
    if not Path(csv_path).exists():
        print(f"❌ File not found: {csv_path}")
        return

    # Run comparison
    comparison = ThreeWayComparison()
    comparison.run_comparison(csv_path, sample_size)


if __name__ == "__main__":
    main()
