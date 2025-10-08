# MusicBrainz API Rate Limiting Debug Guide

## What I've Added

I've added extensive debugging logs throughout the critical code paths to diagnose why MusicBrainz API is experiencing iTunes-style rate limiting (60-second waits after 4 requests).

## Debug Messages You'll See

### 1. Provider Changes
```
🔧 set_search_provider() CALLED: Changing provider to 'X'
   📊 Previous provider was: 'Y'
   📍 Called from: file.py:123 in function_name()
   ✅ Provider saved: 'X'
```
**What this tells us:** Every time the provider is changed, who changed it, and what it was before.

### 2. Batch Search Entry
```
================================================================================
🚀 search_batch_api() CALLED
================================================================================
📊 BATCH SEARCH CONTEXT:
   Total songs: N
   Current provider: 'musicbrainz_api'
   itunes_rate_limit: 20
   use_adaptive_rate_limit: True/False
   discovered_rate_limit: None/120/etc
   📍 Called from: file.py:123 in function_name()
================================================================================
```
**What this tells us:** The complete state when batch search starts.

### 3. Sequential vs Parallel Decision
```
🔀 SEQUENTIAL vs PARALLEL DECISION:
   use_parallel: True/False
   max_workers: 10
   Provider: 'musicbrainz_api'
   ➡️  Using SEQUENTIAL mode (parallel disabled)
```
**What this tells us:** Whether sequential or parallel mode was chosen and why.

### 4. Parallel Mode Guard (MusicBrainz API Protection)
```
🛡️  PARALLEL MODE GUARD CHECK:
   Provider: 'musicbrainz_api'
   Sequential mode (always used)
```
**What this tells us:** All API calls use sequential mode to avoid rate limiting.

### 5. Request Routing (Sequential Mode)
```
🔀 ROUTING REQUEST 1/10: Provider='musicbrainz_api' | Song='Bohemian Rhapsody'
   ➡️  Calling _search_musicbrainz_api()
```
**What this tells us:** For each track, which provider is active and which search method will be called.

### 6. Search Method Execution
```
🟢 _search_musicbrainz_api() CALLED | Provider=musicbrainz_api | Song='Bohemian Rhapsody' | Thread=123456
```
(GREEN = MusicBrainz API, correct!)

```
🔴 _search_itunes() CALLED | Provider=musicbrainz_api | Song='Bohemian Rhapsody' | Thread=123456
```
(RED = iTunes called with wrong provider, BUG!)

**What this tells us:** Which search method is ACTUALLY executed (not just routed to).

### 7. iTunes Rate Limiting (Should NOT Appear for MusicBrainz API!)
```
⏰ _enforce_rate_limit() CALLED | Provider='musicbrainz_api' | Thread=123456
   ⚠️  WARNING: Rate limiting called for provider 'musicbrainz_api' (expected 'itunes')
```
**What this tells us:** If iTunes rate limiting is incorrectly being applied to MusicBrainz API.

```
⏸️  iTunes API RATE LIMIT HIT: 4 requests in last 60s (limit: 4) - waiting 56.3s
```
**What this tells us:** The 60-second iTunes rate limit wait (should NEVER appear for MusicBrainz API).

### 8. MusicBrainz API Rate Limiting (1 req/sec, Should Appear!)
```
✅ MusicBrainz API: First request (no wait)
✅ MusicBrainz API: No wait needed (1.23s since last request)
⏸️  MusicBrainz API rate limit: waiting 0.45s (1 req/sec policy)
```
**What this tells us:** MusicBrainz API's own 1-second rate limiting (expected and correct).

## Expected Output for Working MusicBrainz API

For each request, you should see:
1. ✅ Provider set to 'musicbrainz_api'
2. ✅ Sequential mode (parallel disabled for MusicBrainz API)
3. ✅ Routing shows `Provider='musicbrainz_api'`
4. ✅ **🟢 _search_musicbrainz_api() CALLED** (GREEN, correct!)
5. ✅ MusicBrainz API 1-second waits (0-1 second, not 60 seconds!)
6. ❌ NO **🔴 _search_itunes() CALLED** (should not appear)
7. ❌ NO **⏰ _enforce_rate_limit()** with provider='musicbrainz_api' (should not appear)
8. ❌ NO **⏸️ iTunes API RATE LIMIT HIT** with 60-second wait (should not appear)

## What We're Looking For (The Bug)

If the bug exists, we'll see one of these smoking guns:

**Option A: Wrong Routing**
```
🔀 ROUTING REQUEST 5/10: Provider='musicbrainz_api' | Song='Song Name'
   ➡️  Calling _search_itunes()  ← BUG! Should call _search_musicbrainz_api()
```

**Option B: Provider Changed Mid-Search**
```
🔧 set_search_provider() CALLED: Changing provider to 'itunes'
   📊 Previous provider was: 'musicbrainz_api'
   📍 Called from: some_file.py:456 in some_function()
```
This would show something is changing the provider during the search.

**Option C: iTunes Rate Limiting Applied to Wrong Provider**
```
⏰ _enforce_rate_limit() CALLED | Provider='musicbrainz_api' | Thread=123456
   ⚠️  WARNING: Rate limiting called for provider 'musicbrainz_api' (expected 'itunes')
⏸️  iTunes API RATE LIMIT HIT: 4 requests in last 60s (limit: 4) - waiting 56.3s
```
This would show iTunes rate limiting is somehow being applied even though provider is 'musicbrainz_api'.

## How to Use

1. Run the main app with MusicBrainz API selected
2. Start a search
3. Copy ALL the console output
4. Send it to me

The extensive logging will reveal exactly:
- What provider is active at each step
- Which search method is actually being called
- Where rate limiting is being enforced
- If/when the provider is being changed
- Complete call stacks to trace the flow

## Test Scripts

I've also created test scripts:
- `test_musicbrainz_api_batch.py` - Tests batch search in isolation
- `test_musicbrainz_api_rate_limit.py` - Tests individual searches

Both tests show MusicBrainz API working correctly when called directly, which suggests the bug is in how the main app calls the search service.
