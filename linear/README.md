# linear

Linear integration plugin for Noxus

## Overview

This plugin is built for the Noxus platform and provides Linear integration functionality including reading issues, listing users and statuses, and managing Linear workflow items.

## Installation

This plugin is a standard Python package. Install dependencies with:

```bash
pip install -e .
```

## Usage

### Local Development

To test your plugin locally:

```bash
# Validate the plugin
noxus-cli plugin validate

```

### Configuration

The plugin is configured as a Python package:

- **Name**: linear
- **Version**: 0.1.0 (in `pyproject.toml`)
- **Execution**: runtime
- **Dependencies**: Managed in `pyproject.toml`

## Nodes

### LinearIssuesReaderNode

Fetches issues from Linear with optional filtering by status and assignee

**Outputs:**
- `issues` (list): List of Linear issues formatted as markdown or JSON

**Configuration:**
- Status filter (multi-select)
- Assignee filter (multi-select) 
- Format as Markdown toggle

## Development

### Requirements

- Python 3.11+
- Dependencies defined in `pyproject.toml`

### Project Structure

```
linear/
├── __init__.py          # Plugin definitions and main exports
├── nodes/               # Node implementations
│   ├── __init__.py      # Node exports
│   └── issue_reader.py  # Issue reading node
├── pyproject.toml       # Dependencies and metadata
├── tests/               # Test files
│   ├── __init__.py
│   └── test_linear.py
└── README.md           # This file
```

### Adding Dependencies

Edit `pyproject.toml`:

```toml
[project]
dependencies = [
    "httpx>=0.24.0",
    "pydantic>=2.0.0",
    # Add your dependencies here
]
```

### Testing

Install test dependencies:

```bash
pip install -e ".[test]"
```

Run tests:

```bash
python -m pytest tests/
```
