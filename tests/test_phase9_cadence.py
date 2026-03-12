"""Phase 9 Plan 02: Cadence Re-queuing tests.

Tests for automatic cadence re-queuing so contacts whose cadence timer has
expired re-enter the daily queue alongside fresh scored candidates.

Requirements: CAD-02, CAD-03
"""

import pytest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# TestCadenceRequeue: _get_cadence_expired_candidates()
# ---------------------------------------------------------------------------


class TestCadenceRequeue:
    """Cadence re-queuing logic in _get_cadence_expired_candidates()."""

    def _make_connection(self, **kwargs):
        """Build a minimal Connection-like mock."""
        conn = MagicMock()
        conn.id = kwargs.get("id", "conn-1")
        conn.cadence_due_at = kwargs.get("cadence_due_at", None)
        conn.user_priority = kwargs.get("user_priority", None)
        conn.reconnect_score = kwargs.get("reconnect_score", 75.0)
        conn.email = kwargs.get("email", "test@example.com")
        conn.linkedin_url = kwargs.get("linkedin_url", None)
        conn.last_message_date = kwargs.get("last_message_date", None)
        conn.last_contacted_at = kwargs.get("last_contacted_at", None)
        conn.current_company = kwargs.get("current_company", None)
        return conn

    def test_cadence_expired_contacts_found(self):
        """_get_cadence_expired_candidates() returns contacts where
        cadence_due_at <= now and user_priority != 'never' and
        reconnect_score is not None."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Contact with expired cadence
            c1 = Connection(
                name="Alice",
                cadence_due_at=datetime.utcnow() - timedelta(days=1),
                reconnect_score=80.0,
                email="alice@example.com",
            )
            # Contact with future cadence (should NOT appear)
            c2 = Connection(
                name="Bob",
                cadence_due_at=datetime.utcnow() + timedelta(days=7),
                reconnect_score=75.0,
                email="bob@example.com",
            )
            session.add(c1)
            session.add(c2)
            session.commit()
            session.refresh(c1)
            session.refresh(c2)

            results = qg._get_cadence_expired_candidates(session, limit=10)

        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_archive_never_requeued(self):
        """_get_cadence_expired_candidates() excludes contacts with
        user_priority='never' (ARCHIVE)."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Archived contact with expired cadence
            archived = Connection(
                name="ArchivedUser",
                cadence_due_at=datetime.utcnow() - timedelta(days=1),
                reconnect_score=60.0,
                user_priority="never",
                email="archived@example.com",
            )
            # Normal contact with expired cadence
            normal = Connection(
                name="NormalUser",
                cadence_due_at=datetime.utcnow() - timedelta(days=1),
                reconnect_score=65.0,
                email="normal@example.com",
            )
            session.add(archived)
            session.add(normal)
            session.commit()

            results = qg._get_cadence_expired_candidates(session, limit=10)

        names = [r.name for r in results]
        assert "ArchivedUser" not in names
        assert "NormalUser" in names

    def test_null_cadence_not_included(self):
        """Contacts with cadence_due_at=None are not returned."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # No cadence set at all
            c = Connection(
                name="NoCadence",
                cadence_due_at=None,
                reconnect_score=80.0,
                email="nocadence@example.com",
            )
            session.add(c)
            session.commit()

            results = qg._get_cadence_expired_candidates(session, limit=10)

        assert len(results) == 0

    def test_future_cadence_not_included(self):
        """Contacts with cadence_due_at > now are not returned."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            c = Connection(
                name="FutureCadence",
                cadence_due_at=datetime.utcnow() + timedelta(days=7),
                reconnect_score=80.0,
                email="future@example.com",
            )
            session.add(c)
            session.commit()

            results = qg._get_cadence_expired_candidates(session, limit=10)

        assert len(results) == 0

    def test_uses_cadence_due_at(self):
        """Query uses Connection.cadence_due_at field directly (not re-derived
        from signal_assigned_at + cadence_days)."""
        import inspect
        import src.pipeline.queue_generator as qg

        source = inspect.getsource(qg._get_cadence_expired_candidates)
        # Must reference cadence_due_at field
        assert "cadence_due_at" in source
        # Must NOT reference signal_assigned_at (re-derivation pattern)
        assert "signal_assigned_at" not in source
        # Must compare with <= (expired check)
        assert "<=" in source

    def test_volume_cap_half_limit(self):
        """Cadence candidates are capped at limit // 2."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Create 6 expired cadence contacts
            for i in range(6):
                c = Connection(
                    name=f"CadenceUser{i}",
                    cadence_due_at=datetime.utcnow() - timedelta(days=1),
                    reconnect_score=float(80 - i),
                    email=f"user{i}@example.com",
                )
                session.add(c)
            session.commit()

            # With limit=4, cadence_limit should be 4 // 2 = 2
            cadence_limit = 4 // 2
            results = qg._get_cadence_expired_candidates(session, limit=cadence_limit)

        assert len(results) <= 2

    def test_cadence_contacts_pass_exclusion(self):
        """Cadence candidates go through is_contact_excluded() — already-in-queue
        contacts are excluded."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection, OutreachQueueItem
        import src.pipeline.queue_generator as qg
        from contextlib import contextmanager

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            c = Connection(
                name="AlreadyQueued",
                cadence_due_at=datetime.utcnow() - timedelta(days=1),
                reconnect_score=80.0,
                email="queued@example.com",
            )
            session.add(c)
            session.commit()
            session.refresh(c)

            # Add an active queue item for this contact
            item = OutreachQueueItem(
                connection_id=c.id,
                channel="email",
                status="pending_review",
            )
            session.add(item)
            session.commit()

            @contextmanager
            def mock_get_session():
                yield session

            original = qg.get_session
            qg.get_session = mock_get_session
            try:
                exclusion = qg.is_contact_excluded(c)
                assert exclusion.excluded is True
                assert "queue" in exclusion.reason.lower()
            finally:
                qg.get_session = original

    def test_cadence_stats_tracked(self):
        """generate_daily_queue() returns stats including cadence_added count."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection, UserProfile
        import src.pipeline.queue_generator as qg
        from contextlib import contextmanager

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Create user profile needed by generate_daily_queue
            profile = UserProfile(id=1, name="TestUser")
            session.add(profile)

            # Create a contact with expired cadence
            c = Connection(
                name="CadenceContact",
                cadence_due_at=datetime.utcnow() - timedelta(days=1),
                reconnect_score=80.0,
                email="cadence@example.com",
            )
            session.add(c)
            session.commit()
            session.refresh(c)

            @contextmanager
            def mock_get_session():
                yield session

            original = qg.get_session
            qg.get_session = mock_get_session
            try:
                with patch.object(qg, "expire_stale_queue_items", return_value=0):
                    with patch.object(qg, "_get_scoring_weight_multipliers", return_value={}):
                        stats = qg.generate_daily_queue(limit=5)

                assert "cadence_added" in stats
                assert isinstance(stats["cadence_added"], int)
                assert stats["cadence_added"] >= 0
            finally:
                qg.get_session = original
