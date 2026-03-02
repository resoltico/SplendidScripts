# Changelog

Notable changes to this project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - 2026-03-02

### Added
- Re-entry lock (`/tmp/term-at-target.lock`) to prevent immediate double-trigger runs.
- Stale lock recovery (auto-clear lock older than 15 seconds).

### Changed
- Refactored path resolution into dedicated handlers for maintainability.
- Standardized output to `return {}` to avoid passing Finder items downstream.
- Kept Terminal launch via `open -a Terminal <path>` with safe quoting.

### Fixed
- Parser error: `Expected class name but found identifier`.
- Removed brittle `kind` string reliance in alias/folder decisions.
- Improved consistency across Finder item types.

## [1.2.1] - 2025-07-21

### Added
- Initial release.
- Open Terminal from Finder selection (file, folder, alias).
- `defaultFolderAction`: `ASK`, `INSIDE`, `LEVEL`.
- `defaultAliasAction`: `ASK`, `TARGET`, `ALIAS`.
- Fallback folder chooser when no Finder input is provided.
- Debug log UI with clipboard copy on error.
