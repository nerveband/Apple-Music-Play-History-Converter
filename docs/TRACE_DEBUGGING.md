# Trace Debugging Guide

This project now ships with an opt-in trace system that records every major UI
event and backend call. Use it when you need to understand exactly which
handlers fire (and in what order) while you interact with the app.

## Enable tracing

```bash
export APPLE_MUSIC_TRACE=1
export APPLE_MUSIC_TRACE_FILE=app_trace.log  # Optional (defaults to app_trace.log)
python run_toga_app.py
```

Tracing works for both synchronous and asynchronous functions. Decorated
methods log entry, exit, thread name, and elapsed time. Widget callbacks for
buttons, selections, and switches are auto-instrumented when tracing is active.

## Watching the logs

Use a second terminal to monitor the trace output in real time:

```bash
tail -f app_trace.log
```

The log shows messages such as:

```
2025-09-18 14:05:03,512 [TRACE] → App.startup thread=MainThread args=() kwargs={}
2025-09-18 14:05:03,842 [TRACE] ← App.startup (329.62 ms)
2025-09-18 14:05:09,210 [TRACE] → provider_selection.on_change thread=MainThread args=(<Selection ...>,) kwargs={}
```

This makes it obvious when a handler begins and ends, and which thread it was
running on.

## Typical workflow

1. Enable tracing (`APPLE_MUSIC_TRACE=1`) and start the app.
2. Interact with the UI (load a CSV, trigger conversions, etc.).
3. Keep `tail -f app_trace.log` open to watch the handler sequence.
4. Share the trace log when reporting issues; it contains the entire call stack
   history without needing to replicate the exact UI sequence manually.

## Traced components

- `AppleMusicConverterApp`: startup, provider switches, file browsing,
  conversion, missing-artist search, MusicBrainz optimisation UI, etc.
- `MusicSearchServiceV2`: provider selection, MusicBrainz/iTunes searches, rate
  limiting, readiness checks.
- `MusicBrainzManagerV2`: optimisation, table/index creation, search cascade
  (including each fuzzy/basic search strategy), wait loops, manual import, and
  database info calls.
- Common widgets (buttons, selections, switches) are wrapped so each user
  interaction is logged automatically.

## Disabling tracing

Tracing is completely off by default. Either omit the environment variable, or
explicitly set `APPLE_MUSIC_TRACE=0` to restore the normal lightweight mode.

