# v2.0.3 - Enhanced Matching Algorithm

Major improvements to artist matching with improved accuracy on typical music libraries.

## Highlights

- **improved Matching Accuracy**: Completely overhauled matching algorithm with proper score ordering, edge case detection, and phonetic matching
- **Better Edge Case Handling**: Generic titles ("Intro", "Home"), short titles, and collaboration credits now handled correctly
- **Hardware-Adaptive Performance**: Auto-detects system capabilities; works on budget hardware (tested on AWS t2.medium: 2 vCPUs, 4GB RAM)
- **Windows Stability**: Fixed console encoding crashes by replacing emojis with ASCII indicators
- **204 Tests Passing**: Comprehensive test coverage across all CSV formats and matching scenarios

## Downloads

| Platform | Download | Requirements |
|----------|----------|--------------|
| **macOS** | [Apple Music History Converter-2.0.3.dmg](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/download/v2.0.3/Apple.Music.History.Converter-2.0.3.dmg) | macOS 10.13+ (Apple Silicon + Intel) |
| **Windows** | [Apple-Music-History-Converter-2.0.3.msi](https://github.com/nerveband/Apple-Music-Play-History-Converter/releases/download/v2.0.3/Apple.Music.History.Converter-2.0.3.msi) | Windows 10/11 x64 |

## What's New

### Enhanced Matching Algorithm

| Feature | Before | After |
|---------|--------|-------|
| **Accuracy** | variable | **improved** |
| **Score ordering** | Wrong (DESC) | Fixed (ASC - lower = more established) |
| **Edge cases** | Often wrong | Detected and handled |
| **Collaborations** | Partial | Full tokenization (feat., &, with, vs) |
| **Unicode** | Basic | Full normalization pipeline |

### What Works Well Now
- Popular music matches instantly
- Album sessions get consistent artist credits
- Collaborations properly tokenized
- Unicode apostrophes/quotes normalized
- Phonetic matching for misspellings (Jon/John)

### Known Limitations
Some tracks may still not match:
- Generic titles ("Intro", "Home") without artist hints
- Japanese/Korean text (different romanizations)
- Typos in source data
- Very obscure indie releases
- Classical music with movement numbers

See [Artist Matching: What to Expect](README.md#artist-matching-what-to-expect) in the README.

### Hardware-Adaptive Performance Modes

| Mode | System | What Happens |
|------|--------|--------------|
| **Performance** | 8GB+ RAM, fast SSD | Full optimization with HOT/COLD tables and all indexes |
| **Efficiency** | 4GB RAM, any disk | Minimal schema for slower systems |

- Auto-detects RAM, CPU cores, and disk speed
- Tested on AWS t2.medium (2 vCPUs, 4GB RAM, slow EBS storage)
- No configuration needed - picks the right mode automatically

### Code Quality

- Removed legacy debug scripts and dead code
- Fixed Windows console encoding (CP1252) crashes
- 204 tests passing
- New [Matching Algorithm documentation](docs/MUSICBRAINZ_MATCHING_ALGORITHM.md)

## Technical Details

For detailed algorithm documentation:
- [Matching Algorithm Wiki](wiki/Matching-Algorithm.md) - Full technical documentation
- [MusicBrainz Matching Algorithm](docs/MUSICBRAINZ_MATCHING_ALGORITHM.md) - Database and search details
- [FAQ](wiki/FAQ.md) - Common questions

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for complete details.

---

**macOS app is fully signed and notarized** by Apple Developer ID - no security warnings, opens immediately.

**Windows MSI installer** - professional installer, no Python required.
