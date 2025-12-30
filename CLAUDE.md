# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project is for converting HWPX files (한글 문서, Korean Hangul word processor format) to Pandoc-compatible formats.

## Project Status

This is a new project. The codebase structure, build commands, and architecture will be defined as development progresses.

## HWPX Format Notes

HWPX is a ZIP-based XML document format used by Hancom Office Hangul (한컴오피스 한글). Key characteristics:
- Container is a ZIP archive with .hwpx extension
- Contains XML files describing document structure, styles, and content
- Main content typically in `Contents/section0.xml`
- Metadata in `META-INF/` directory
