# Testing Patterns

**Analysis Date:** 2026-03-08

## Test Framework

**Runner:**
- `pytest` [7.4.0+] - Configured in `pyproject.toml` optional-dependencies
- `pytest-cov` [4.1.0+] - Coverage reporting (configured but not actively used)
- Config file: None detected (uses pytest defaults)

**Assertion Library:**
- Standard `assert` statements (pytest style)

**Run Commands:**
```bash
pytest                  # Run all tests (not configured in repo)
pytest --cov           # Run with coverage
pytest -v              # Verbose output
```

**Current State:** No test files found in codebase. Testing framework is installed as dev dependency but not actively used.

## Test File Organization

**Location:**
- No test directory structure exists
- Recommended pattern (not yet implemented): `tests/` directory at project root
- Alternative pattern: Co-located `test_*.py` files next to source modules

**Naming:**
- Convention available but unused: `test_{module}.py` or `{module}_test.py`
- Would follow from pyproject.toml configuration

**Structure (Recommended):**
```
tests/
├── __init__.py
├── unit/
│   ├── test_database_models.py
│   ├── test_llm_scoring.py
│   └── test_pipeline.py
├── integration/
│   ├── test_sync_push_pull.py
│   └── test_pipeline_end_to_end.py
└── fixtures/
    └── sample_data.py
```

## Test Structure

**Suite Organization (from pytest conventions):**
```python
import pytest
from src.database.models import Connection

class TestConnection:
    """Test suite for Connection model."""

    def setup_method(self):
        """Run before each test."""
        self.connection = Connection(
            id="test-id",
            name="John Doe",
            email="john@example.com"
        )

    def teardown_method(self):
        """Run after each test."""
        # Cleanup
        pass

    def test_connection_creation(self):
        """Test basic connection model instantiation."""
        assert self.connection.name == "John Doe"
        assert self.connection.email == "john@example.com"

    def test_enrichment_data_extraction(self):
        """Test enrichment data unwrapping."""
        from src.database.models import get_enrichment_data
        connection = Connection(
            id="test",
            name="Test",
            raw_enrichment={"data": {"headline": "Engineer"}}
        )
        data = get_enrichment_data(connection)
        assert data["headline"] == "Engineer"
```

**Patterns:**
- Setup: Use `setup_method()` for per-test fixtures or `@pytest.fixture` for reusable ones
- Teardown: Use `teardown_method()` or fixture cleanup
- Assertions: Use `assert condition with message` or `assert x == y`

## Mocking

**Framework (Recommended):**
- `unittest.mock` (standard library) - Built into Python
- `pytest-mock` - If needed for simpler pytest syntax (not in dependencies)

**Patterns to implement:**
```python
from unittest.mock import patch, MagicMock

# Mock external API calls
@patch('src.ingestion.apify_client.ApifyClient')
def test_enrich_connections(mock_apify):
    """Test enrichment without hitting real API."""
    mock_apify.return_value.call_actor.return_value = {
        "resultStructured": [{"data": {"headline": "VP of Product"}}]
    }

    result = enrich_connections_batch(["test-id"])
    assert result["enriched"] == 1

# Mock database session
@patch('src.database.engine.get_session')
def test_prescore_creates_records(mock_session):
    """Test prescore saves to database."""
    mock_db = MagicMock()
    mock_session.return_value.__enter__.return_value = mock_db

    prescore_unscored_connections()

    # Verify session.add() was called
    assert mock_db.add.called
```

**What to Mock:**
- External API calls: `OpenAI`, `ApifyClient`, `RapidAPI`, `Hunter.io`
- Database sessions: Use fixtures with in-memory SQLite for integration tests
- Supabase client: Mock entire `createClient()` in TypeScript tests
- File I/O: Mock `open()` when testing CSV import logic
- HTTP requests: Use `responses` library or `pytest-httpserver`

**What NOT to Mock:**
- Database models and schema validation
- Core business logic (scoring, queue generation)
- Configuration loading (use test .env fixture)
- Module imports and initialization

## Fixtures and Factories

**Test Data (Recommended pattern):**
```python
# tests/fixtures/sample_data.py
import pytest
from datetime import datetime
from src.database.models import Connection, UserProfile

@pytest.fixture
def sample_user_profile():
    """Create test user profile."""
    return UserProfile(
        id=1,
        name="Test User",
        current_role="Product Manager",
        company="TechCo",
        industry="Software",
        goals="Break into product leadership",
        interests="AI, Product Strategy"
    )

@pytest.fixture
def sample_connection():
    """Create test connection with minimal data."""
    return Connection(
        id="conn-1",
        name="Jane Engineer",
        email="jane@example.com",
        linkedin_url="https://linkedin.com/in/janeengineer",
        current_role="Senior Engineer",
        current_company="FinanceApp",
        location="San Francisco",
        reconnect_score=75.0
    )

@pytest.fixture
def sample_connection_with_enrichment():
    """Connection with full enrichment data."""
    return Connection(
        id="conn-2",
        name="John Manager",
        email="john@example.com",
        linkedin_url="https://linkedin.com/in/johnmanager",
        raw_enrichment={
            "data": {
                "headline": "Director of Engineering",
                "skills": ["Python", "Leadership", "Architecture"],
                "experience": [
                    {
                        "title": "Director of Engineering",
                        "company": "BigTech",
                        "years": 3
                    }
                ]
            }
        },
        activity_log=[
            {"type": "post", "date": "2024-03-05", "content": "Excited about our new product launch"},
            {"type": "endorsement", "date": "2024-03-01", "skill": "Leadership"}
        ]
    )

# Factory pattern for generating many test records
def make_connections(count: int, base_name: str = "Contact") -> list[Connection]:
    """Generate N test connections."""
    return [
        Connection(
            id=f"conn-{i}",
            name=f"{base_name} {i}",
            email=f"contact{i}@example.com",
            current_role=f"Role {i % 3}",
            reconnect_score=30 + (i * 2) % 70
        )
        for i in range(count)
    ]
```

**Location:**
- `tests/fixtures/` directory for reusable test data
- Imported via `conftest.py` for pytest auto-discovery: `pytest_plugins = ["tests.fixtures"]`

## Coverage

**Requirements:** Not enforced (no coverage threshold configured)

**View Coverage:**
```bash
pytest --cov=src --cov-report=html    # Generate HTML coverage report
pytest --cov=src --cov-report=term    # Show terminal summary
```

**Areas to prioritize for testing:**
- `src/database/models.py` - Data integrity (helper functions, field validation)
- `src/llm/scoring.py` - Scoring logic, prompt building, LLM parsing
- `src/pipeline/daily_pipeline.py` - Pipeline orchestration, step sequencing
- `src/ingestion/csv_import.py` - CSV parsing, field extraction, data normalization
- `src/sync/push.py` and `src/sync/pull.py` - Sync logic, conflict resolution

## Test Types

**Unit Tests (recommended focus):**
- Scope: Single function or method in isolation
- Approach: Mock all external dependencies
- Example: Test `prescore_unscored_connections()` with mocked database and OpenAI
- Location: `tests/unit/test_llm_*.py`

**Integration Tests (needed):**
- Scope: Multiple modules working together (e.g., database + pipeline)
- Approach: Use temporary SQLite in-memory database for isolation
- Example: Test full pipeline run with mock enrichment APIs
- Setup:
```python
@pytest.fixture
def temp_db():
    """Create temporary in-memory database for testing."""
    from src.database.engine import create_test_engine, init_db
    engine = create_test_engine()  # in-memory SQLite
    init_db(engine)
    yield engine

def test_pipeline_full_run(temp_db):
    """Test complete daily pipeline with temp database."""
    # Setup test data
    # Run pipeline
    # Assert results in database
```

**E2E Tests (not currently implemented):**
- Framework: Not used
- Would test: Streamlit UI workflows, PWA interactions, Supabase sync
- Recommendation: Add when PWA matures or UI stability is critical

## Common Patterns

**Async Testing (not currently used, but pattern if needed):**
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function with pytest-asyncio."""
    result = await some_async_function()
    assert result == expected
```

**Error Testing:**
```python
def test_invalid_date_parsing():
    """Test error handling in date parsing."""
    from src.ingestion.csv_import import parse_linkedin_date

    # Invalid format should return None
    result = parse_linkedin_date("invalid date")
    assert result is None

    # Valid formats should parse
    result = parse_linkedin_date("15 Jan 2024")
    assert result.year == 2024

def test_openai_key_validation():
    """Test missing API key raises ValueError."""
    from src.llm.prose import generate_prose

    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            generate_prose("connection-id")
```

**Database Testing (recommended):**
```python
def test_connection_uniqueness(temp_db):
    """Test LinkedIn URL uniqueness constraint."""
    from sqlalchemy.exc import IntegrityError

    with get_session(engine=temp_db) as session:
        conn1 = Connection(
            id="id1",
            name="Jane",
            linkedin_url="https://linkedin.com/in/jane"
        )
        session.add(conn1)
        session.commit()

        # Duplicate should raise
        conn2 = Connection(
            id="id2",
            name="Jane Duplicate",
            linkedin_url="https://linkedin.com/in/jane"
        )
        session.add(conn2)

        with pytest.raises(IntegrityError):
            session.commit()
```

---

*Testing analysis: 2026-03-08*
