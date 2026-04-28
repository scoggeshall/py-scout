# Py-Scout v0.2.0 - Focused Discovery and Mapping

Py-Scout has been simplified into a focused GUI-first network field tool.

## Core Workflow

Plug in -> Run discovery -> See switch/port -> Save mapping -> Done

## Changed

- Refocused Py-Scout around switchport discovery and physical mapping
- Removed non-core product surface areas from the active app
- Kept the active GUI limited to:
  - Discovery
  - Mapper
- Removed the old tracked py_scout package
- Improved GUI layout and spacing
- Improved app icon and in-app branding
- Built as a Windows GUI application with no command prompt window
- Updated README and GitHub Pages docs

## Active Features

- PySide6 GUI
- TShark-based LLDP/CDP discovery
- Physical mapping records
- SQLite persistence
- Single executable: pyscout.exe

## Requirements

- Windows
- Wireshark/TShark
- Npcap/Wireshark capture support

## Validation

Passed before release:

- python -m unittest discover
- python -m compileall pyscout
- python -m pyscout --help
- python -m pyscout version
- .\build.ps1
- .\dist\pyscout.exe smoke launch
