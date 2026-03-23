---
name: analyze-with-claude
description: Analyzes a codebase using Claude Code CLI (claude --print)
category: analyze-codebase
requires:
  bins: ["claude"]
command: ["claude", "--print", "--dangerously-skip-permissions", "{prompt}"]
---

# Analyze Codebase with Claude Code

## Command

Run in the project directory:

```bash
claude --print --dangerously-skip-permissions "<prompt>"
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
- Use `--dangerously-skip-permissions` for non-interactive mode
- Output is captured entirely and saved as the project context document
- Timeout: 5 minutes
