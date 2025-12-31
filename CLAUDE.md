# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Markdown to HWPX (Korean Hangul document) converter for Korean public agency report styles. Converts markdown documents into HWPX files with the standard government hierarchy format: Ⅰ.→①→□→ㅇ.

## Commands

```bash
# Install (editable mode)
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# CLI usage
hwpx-convert input.md -o output.hwpx
hwpx-convert input.md --template custom.hwpx
hwpx-convert --guide  # Show markdown guide

# Start API server
hwpx-server
# or: uvicorn hwpx_converter.api:app --host 0.0.0.0 --port 8000

# Run tests
pytest

# Linting and formatting
black src/
ruff check src/
```

**Prerequisite**: Pandoc must be installed (`choco install pandoc` on Windows).

## Architecture

```
src/hwpx_converter/
├── converter.py   # Core: HwpxConverter class, markdown preprocessing
├── api.py         # FastAPI REST endpoints (POST /v1/conversions, etc.)
├── cli.py         # Command-line interface (hwpx-convert)
├── models.py      # Pydantic models (ConversionJob, Template, API schemas)
├── storage.py     # Job/template file storage with auto-cleanup
└── errors.py      # Custom exceptions with error codes
```

### Conversion Flow

1. `HwpxConverter.preprocess_markdown()` transforms markdown syntax:
   - `# Title` → `Ⅰ. Title` (Roman numerals)
   - `## Title` → `① Title` (circled numbers)
   - `- item` → `□ item` (level 1)
   - `    - item` → `ㅇ item` (level 2, 4-space indent)
   - `> note` → `* note` (footnote style)

2. Preprocessed markdown is passed to `pypandoc-hwpx` for HWPX generation

3. Output uses a blank HWPX template from `data/templates/blank.hwpx`

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/conversions` | Submit markdown for conversion |
| GET | `/v1/conversions/{id}` | Check conversion status |
| GET | `/v1/conversions/{id}/download` | Download result HWPX |
| GET/POST | `/v1/templates` | List/upload templates |

## HWPX Format Notes

HWPX is a ZIP-based XML format used by Hancom Office Hangul (한컴오피스 한글):
- Container is a ZIP archive with .hwpx extension
- Main content in `Contents/section0.xml`
- Metadata in `META-INF/` directory
- XML namespaces defined in `HwpxConverter.NAMESPACES`

## Key Constants

- `MAX_INPUT_SIZE`: 3MB limit for input files
- Font sizes (HWP units, 1pt=100): title=1800, subtitle=1500, level1=1300, level2=1200, note=1000
- Job files auto-deleted after 24 hours
