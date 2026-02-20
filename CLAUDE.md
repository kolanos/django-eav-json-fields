# CLAUDE.md — django-eav-json-fields

## Project Overview

Schema-validated JSONFields for Django using an EAV-style DSL. Stores structured configuration as plain JSONB while enforcing type safety, coercion, and constraints at the application layer.

- **Version**: 0.1.0
- **Python**: >=3.10 (targets 3.10–3.13)
- **Django**: >=4.2 (targets 4.2, 5.0, 5.1, 5.2)
- **Only runtime dependency**: Django

## Quick Commands

```bash
# Run all tests (99 tests, ~0.06s)
./.venv/bin/pytest

# Run a specific test file/class/test
./.venv/bin/pytest tests/test_eav.py::TestEAVString::test_accepts_valid_string

# Lint
./.venv/bin/ruff check .

# Auto-fix lint issues
./.venv/bin/ruff check --fix .

# Format
./.venv/bin/ruff format .

# Type check
uv run ty check

# Check formatting without changing files
./.venv/bin/ruff format --check .
```

## Project Structure

```
eav_fields/              # Main package
  __init__.py             # Public API exports (__all__)
  eav.py                  # Core: EAVAttribute types, EAVSchema metaclass & base
  fields.py               # Django model field: EAVField
  widgets.py              # EAVWidget for Django admin (HTML + inline JS)
tests/
  conftest.py             # Minimal Django settings (in-memory SQLite)
  test_eav.py             # Schema/attribute tests (43 tests)
  test_fields.py          # Model field tests (38 tests)
  test_widgets.py         # Admin widget tests (18 tests)
```

## Architecture

### Module Responsibilities

- **eav.py** — Declarative schema DSL. `EAVAttribute` subtypes (String, Bool, Integer, Float, Decimal) handle type checking, coercion, and constraints. `EAVSchema` (via `EAVSchemaMeta` metaclass) collects attributes and orchestrates validation.
- **fields.py** — Django model field. `EAVField` wraps a schema (static or polymorphic via `schema_map`).
- **widgets.py** — `EAVWidget` renders typed HTML inputs per attribute with inline JS for JSON sync. Supports polymorphic show/hide fieldsets.

### Key Design Decisions

- **Metaclass for DSL**: `EAVSchemaMeta` collects `EAVAttribute` instances at class definition time
- **Decimal stored as string**: Preserves precision in JSON (no native decimal type)
- **Lazy schema resolution**: Schemas can be referenced as dotted string paths for migration serialization
- **Polymorphic via schema_map**: Schema selected by a sibling field's value, not via inheritance
- **Strict type checking**: `EAVBoolean` rejects 0/1, `EAVInteger` rejects bools

### Validation Flow

1. Reject unknown keys
2. Per-attribute: type check → coerce → constraint check → choice validation
3. Cross-field validation (`validate_cross()` hook)
4. Return cleaned dict with `to_json()` values

## Code Conventions

- `from __future__ import annotations` in all modules
- `TYPE_CHECKING` guard for type-only imports
- Type annotations on all functions
- Google-style docstrings
- Private methods prefixed with `_`
- Ruff config: `line-length = 120`, rules: `E, F, W, I, UP, B, SIM, RUF`

## Testing Conventions

- pytest with pytest-django
- Django settings configured in `tests/conftest.py` (no settings module)
- `SimpleNamespace` used for mock model instances in field tests
- `pytest.raises()` for exception assertions
- Test classes named `Test<Component>` with methods `test_<behavior>`
- No fixtures beyond conftest — tests are self-contained

## Build & Tooling

- **Package manager**: uv
- **Build backend**: hatchling
- **Linter/formatter**: ruff
- **Test runner**: pytest
- **CI/CD**: GitHub Actions — `ci.yml` (lint + test matrix on push/PR), `publish.yml` (PyPI via trusted publisher on release)
