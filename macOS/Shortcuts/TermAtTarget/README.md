# Term At Target

Open Terminal at the selected Finder location using a macOS Shortcut + AppleScript.

## Features

- Opens Terminal for a selected Finder folder.
- If a file is selected, opens Terminal in that file’s containing folder.
- Supports Finder aliases (choose target location or alias location).
- Supports folder open mode: inside folder or parent level.
- Includes a run lock to avoid double-trigger launches.

## Requirements

- macOS with Shortcuts and Terminal app available.
- Finder selection passed into the Shortcut as input.
- AppleScript action inside the Shortcut.

## Installation

Use the setup guide:

[https://resolve.resoltico.com/apps/term-at-target/](https://resolve.resoltico.com/apps/term-at-target/)

## Configuration

Set these AppleScript properties in the script:

- `defaultFolderAction`: `ASK`, `INSIDE`, `LEVEL`
- `defaultAliasAction`: `ASK`, `TARGET`, `ALIAS`

## Usage

1. Select a file, folder, or alias in Finder.
2. Run the Shortcut.
3. Terminal opens at the resolved location.

## Troubleshooting

- If files/folders are duplicated, check Finder shortcut conflicts.
- Do not bind this Shortcut to `⌘D` (Finder Duplicate).
- If Terminal opens twice, verify the Shortcut is not assigned in multiple places.

## License

MIT License. See `LICENSE`.
