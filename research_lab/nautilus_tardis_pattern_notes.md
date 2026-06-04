# Nautilus Tardis Pattern Notes

## TL;DR

This is a time-boxed stub for later exploration. Full Nautilus source download was intentionally not pursued because the core deliverables are Materials #1-#3 and Nautilus is optional. We are not migrating to Nautilus. Selective value is in Tardis data normalization patterns: typed event parsing, explicit timestamp conversion, streaming/gzip CSV loading, and normalized domain objects.

Sources lightly reviewed:

- Nautilus Tardis docs: https://nautilustrader.io/docs/latest/integrations/tardis/
- docs.rs `nautilus_tardis` API pages
- DeepWiki summary of relevant Nautilus Tardis source files

## Tardis Adapter Pattern

Observed pattern from docs/summaries:

- Separate HTTP metadata/instrument resolution from CSV/replay data loading.
- Convert Tardis-specific symbols and event schemas into internal domain types.
- Parse timestamps with explicit precision conversion, e.g. microseconds to nanoseconds in Nautilus.
- Provide both batch loading and streaming iterators for large CSV/gzip files.
- Treat replay as event ingestion into an engine, not as ad hoc DataFrame loading.

## Schema Normalization

Relevant ideas for btc-bot:

- Normalize raw exchange symbols and instrument metadata once, then attach normalized symbol/instrument id to every event.
- Keep raw timestamp and normalized UTC timestamp.
- Store event type explicitly: trade, book change, liquidation/force order, bar, instrument metadata.
- Use deterministic parsing for side/action/aggressor fields.

## Gap Handling

Items to investigate later:

- Whether Nautilus surfaces missing intervals as explicit gaps or leaves that to caller validation.
- How retry logic handles partially unavailable compressed CSV files.
- Whether replay preserves source ordering for same-timestamp events.

## Lessons For Our Liquidation Backfill

1. Build a parser per Tardis event schema rather than a single loosely typed CSV loader.
2. Preserve raw fields plus normalized fields, especially timestamp, side, price, size, and exchange symbol.
3. Support streaming processing for large historical files; do not require loading multi-year liquidation files into memory.

## What We Do Not Take

- No platform migration.
- No LGPL code copying into btc-bot.
- No Rust event engine dependency.
- No change to live decision loop.

## Later Exploration Checklist

- Inspect `crates/adapters/tardis/src/csv/record.rs`.
- Inspect `crates/adapters/tardis/src/csv/mod.rs`.
- Inspect `crates/adapters/tardis/src/http/parse.rs`.
- Inspect `crates/adapters/tardis/src/replay.rs`.
- Extract only patterns, not code.
