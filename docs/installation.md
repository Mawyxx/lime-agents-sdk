# Installation

## Requirements

- Python **3.10** or newer
- Runtime dependencies: `httpx`, `mcp`

## PyPI

```bash
pip install lime-agents-sdk
```

## Latest from GitHub

```bash
pip install git+https://github.com/Mawyxx/lime-agents-sdk.git
```

## Development install

```bash
git clone https://github.com/Mawyxx/lime-agents-sdk.git
cd lime-agents-sdk
pip install -e ".[dev]"
```

Build documentation locally:

```bash
pip install -r docs/requirements.txt && pip install .
mkdocs serve -f docs/mkdocs.yml
```
