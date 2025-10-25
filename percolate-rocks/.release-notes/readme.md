# Release Notes

This directory contains all release-related documentation for REM Database.

## Release history

- [v0.2.0](./v0.2.0.md) - SQL query improvements (OFFSET, IN, LIKE, COUNT)
- [v0.1.0](./v0.1.0-published.md) - Initial PyPI release

## Planning

- [Roadmap](./roadmap.md) - Complete feature roadmap through v1.0.0
- [Status](./status.md) - Current implementation status with detailed metrics

## Guides

- [Building and publishing](./building-and-publishing.md) - Complete guide for building wheels and publishing to PyPI

## Archive

The `archive/` directory contains historical reference documents:
- [Query test results](./archive/query-test-results.md) - Historical query testing from v0.1.0
- [Warnings analysis](./archive/warnings-analysis.md) - Compiler warning tracking during development

## Upcoming releases

### v0.3.0 (in progress - 95% complete)

**Focus:** Peer replication with WAL and gRPC streaming

**Completed:**
- Write-ahead log (WAL) implementation
- Database WAL integration (insert/update/delete logging)
- gRPC protocol definitions
- Primary node (gRPC server)
- Replica node (gRPC client, 95% complete)
- Sync state machine

**Outstanding:**
- Replica WAL application (~2 hours)
- Lag calculation (~1 hour)
- Integration tests (~4 hours)
- WAL test updates (~1 hour)

**Estimated release:** November 2024

See `../status.md` for detailed feature tracking.
