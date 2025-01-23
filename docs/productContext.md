# Product Context

## Purpose
The Apple Music Play History Converter is a tool designed to help users convert their Apple Music listening history into a format that's compatible with Last.fm, specifically for use with Universal Scrobbler.

## Problems Solved
1. Apple Music doesn't directly integrate with Last.fm for scrobbling
2. Apple's exported music history data is not in a format that Last.fm can understand
3. Manual conversion of play history would be time-consuming and error-prone

## How It Works
1. Users request their listening history from privacy.apple.com
2. The tool processes three types of Apple Music CSV files:
   - Play History Daily Tracks
   - Recently Played Tracks
   - Play Activity
3. Converts the data into a format compatible with Universal Scrobbler
4. Optionally uses iTunes API to fill in missing artist information
5. Allows users to save or copy the converted data for import into Last.fm

## Key Features
- Local processing (no data leaves the user's computer)
- Support for multiple Apple Music export formats
- iTunes API integration for enhanced artist information
- Progress tracking for large files
- Preview of converted data
- Copy to clipboard and save as CSV options 