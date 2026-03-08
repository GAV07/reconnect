# Coding Conventions

**Analysis Date:** 2026-03-08

## Naming Patterns

**Files:**
- Snake case for Python files: `daily_pipeline.py`, `email_digest.py`, `csv_import.py`
- Kebab case for TypeScript Edge Functions: `supabase/functions/{name}/index.ts`
- PascalCase for component files in PWA: Not strongly enforced, mixed usage
- Double underscore prefix for private/dunder modules: `__init__.py` in all packages

**Functions:**
- Snake case for all Python functions: `run_daily_pipeline()`, `import_linkedin_csv()`, `get_enrichment_data()`
- Camel case for JavaScript async functions: `renderQueue()`, `queueAction()`, `setupQueueRealtime()`
- TypeScript functions also camelCase: `buildDraftPrompt()`, `createActionTokens()`
- Helper functions prefixed with underscore: `_get_mock_profile_data()`, `_get_tier2_connections()`, `_record_to_dict()`

**Variables:**
- Snake case in Python: `connection_source`, `reconnect_score`, `linkedin_url`, `current_company`
- Camel case in JavaScript/TypeScript: `supabaseUrl`, `queueItemId`, `connectionId`, `openaiKey`
- Private variables prefixed with underscore: `_upsert_record()`, `_record_to_dict()`
- Constants in UPPER_SNAKE_CASE: `CONNECTION_SYNC_FIELDS`, `SUPABASE_URL`, `SYSTEM_PROMPT`

**Types/Classes:**
- PascalCase for all class and dataclass names: `Connection`, `UserProfile`, `ImportResult`, `ScoreResult`, `PipelineResult`
- Interface names in TypeScript prefixed with `I` or documented as interfaces: `interface DraftRequest`

## Code Style

**Formatting:**
- Tool: `ruff` (configured in `pyproject.toml`)
- Line length: 100 characters (set via `line-length = 100` in ruff config)
- No strict formatter (Black equivalent); ruff handles imports primarily
- Indentation: 4 spaces for Python, 2 spaces for TypeScript/JavaScript

**Linting:**
- Tool: `ruff` with select rules `["E", "F", "I"]`
  - `E`: Error codes (PEP 8 compliance)
  - `F`: Pyflakes (undefined names, unused imports)
  - `I`: Isort-style import sorting
- No pre-commit hooks configured
- Build system uses `hatchling`

**Trailing whitespace and semicolons:**
- Python: No semicolons; bare except with no trailing statements
- TypeScript: Semicolons used consistently; `catch { ... }` syntax preferred

## Import Organization

**Order (Python):**
1. Standard library imports: `import sys`, `from pathlib import Path`, `from datetime import datetime`, `from typing import`
2. Third-party imports: `from sqlmodel import select`, `from openai import OpenAI`, `from pydantic_settings import BaseSettings`
3. Local imports: `from src.config import settings`, `from src.database.engine import get_session`
4. Blank line between each group

**Example from `src/llm/scoring.py`:**
```python
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from openai import OpenAI

from src.config import settings
from src.database.engine import get_session
from src.database.models import Connection, UserProfile, get_enrichment_data
```

**Path Aliases:**
- No path aliases configured in Python (uses direct relative imports from project root)
- Project root added to sys.path in `src/ui/app.py`: `sys.path.insert(0, str(project_root))`
- Imports always use `src.` prefix: `from src.database.models import Connection`

**TypeScript imports:**
- Use ESM imports from CDN: `import { createClient } from "https://esm.sh/@supabase/supabase-js@2"`
- No local import path resolution needed in Deno Edge Functions

## Error Handling

**Patterns:**
- Broad exception catching with `except Exception:` followed by `pass` for silent failures
- Example from `src/config.py`:
```python
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        return dict(st.secrets)
except Exception:
    pass
return {}
```

- Specific exception handling for expected errors:
```python
try:
    return datetime.strptime(date_str.strip(), fmt)
except ValueError:
    continue
```

- No custom exception classes; standard library exceptions used throughout
- When raising exceptions, provide context: `raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in .env")`
- TypeScript catches with implicit error typing: `catch { ... }` (no error binding)

**Validation at module load:**
- Configuration validation deferred to Settings class instantiation
- Optional dependencies checked at runtime with `try/except ImportError`

## Logging

**Framework:** Standard library `logging` module (no external logging framework)

**Setup Pattern:**
```python
import logging
logger = logging.getLogger(__name__)
```

**Usage:**
- Info level for pipeline milestones: `logger.info("Dashboard snapshot saved")`
- No debug, warning, or error logging observed in main code
- Minimal logging overall—more focused on returning structured results

**Example from `src/sync/push.py`:**
```python
import logging
...
logger = logging.getLogger(__name__)
...
logger.info(
    "Synced %d connections, %d queue items...",
    stats["connections"], stats["queue_items"]
)
```

## Comments

**When to Comment:**
- Module docstrings required for all files (triple-quoted at top)
- Function docstrings provided for public functions and complex logic
- Inline comments rare; code is self-documenting via clear naming
- Use comments to explain WHY, not WHAT

**Example from `src/database/models.py`:**
```python
def get_enrichment_data(connection: "Connection") -> dict:
    """Unwrap enrichment data from raw_enrichment.

    RapidAPI responses nest profile fields under a ``"data"`` key.  Older
    records or other providers may store fields at the top level.  This
    helper returns the inner dict so callers always get flat field access
    (e.g. ``data.get("headline")``).
    """
```

**JSDoc/TSDoc:**
- Not used; minimal comment blocks in TypeScript Edge Functions
- Inline comments in TypeScript for business logic:
```typescript
// Handle CORS preflight
if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
}
```

## Function Design

**Size:** Functions typically 20-60 lines; longer functions broken into step-by-step pipelines

**Parameters:**
- Use keyword arguments in Python functions for clarity
- Optional parameters use `Optional[Type]` from typing with sensible defaults
- Complex functions accept `**kwargs` or dataclass parameters for flexibility

**Example from `src/pipeline/daily_pipeline.py`:**
```python
def run_daily_pipeline(
    linkedin_dump_path: Optional[Path] = None,
    user_name: Optional[str] = None,
    skip_enrichment: bool = False,
    skip_queue_generation: bool = False,
    enrich_budget: Optional[int] = None,
    queue_size: Optional[int] = None,
) -> dict:
```

**Return Values:**
- Functions return dicts for flexibility: `-> dict`
- Structured results wrapped in dataclasses: `ScoreResult`, `ProseResult`, `ImportResult`, `PipelineResult`
- Dataclasses include type hints and post-init validation

**Example dataclass:**
```python
@dataclass
class ScoreResult:
    """Result of scoring a connection."""
    score: float  # 0-100
    reasoning: str
    key_factors: list[str]
    conversation_hooks: list[str]
    dimension_scores: dict[str, int] = None

    def __post_init__(self):
        if self.dimension_scores is None:
            self.dimension_scores = {}
```

## Module Design

**Exports:**
- No `__all__` lists; all public functions/classes are importable
- Private helpers prefixed with underscore to signal intent
- Barrel files not used; direct imports from specific modules

**Module structure pattern:**
```
src/
├── config.py                    # Settings singleton
├── database/
│   ├── __init__.py
│   ├── engine.py               # Session management
│   └── models.py               # SQLModel definitions
├── pipeline/
│   ├── __init__.py
│   └── daily_pipeline.py       # Main orchestration
└── llm/
    ├── __init__.py
    └── scoring.py              # LLM scoring logic
```

**Circular dependency handling:**
- Avoided via clear layer separation
- Configuration imported early and cached: `from src.config import settings`
- Database models have helpers for common transformations: `get_enrichment_data()`

---

*Convention analysis: 2026-03-08*
