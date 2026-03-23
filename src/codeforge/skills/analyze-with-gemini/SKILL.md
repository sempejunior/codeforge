---
name: analyze-with-gemini
description: Analyzes a codebase using Gemini CLI
category: analyze-codebase
requires:
  bins: ["gemini"]
  env: ["GEMINI_API_KEY"]
command: ["gemini", "-p", "{prompt}"]
---

# Analyze Codebase with Gemini CLI

## Command

Run in the project directory:

```bash
gemini -p "<prompt>"
```

## Prompt

Analyze this codebase and produce a structured context document. Output ONLY the document, no conversation. Use this exact structure:

# Context: <project name from package.json/pyproject.toml/Cargo.toml>

## Stack
List the main languages, frameworks, and key libraries with versions.

## Architecture
Describe the high-level structure: layers, main modules, how they connect.

## Key Modules
List the 5-10 most important files/modules with one-line descriptions.

## Patterns
Describe coding patterns, conventions, and idioms used (e.g. async/await, dependency injection, etc.).

## Test Coverage
Describe what is tested and how (frameworks, test structure).

## External Integrations
List external APIs, services, databases, and queues used.

## Notes
- Requires GEMINI_API_KEY environment variable
- Output is captured entirely and saved as the project context document
- Timeout: 5 minutes
