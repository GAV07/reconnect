"""Phase 7 Plan 01: Signal Foundation tests.

Tests for ContactSignal, ContactNote models, new fields on Connection/OutreachQueueItem/UserProfile,
and the signal_service module.
"""

import pytest
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Task 1: Model field and structure tests
# ---------------------------------------------------------------------------

class TestContactSignalModel:
    """ContactSignal model has correct tablename and required fields."""

    def test_contact_signal_tablename(self):
        from src.database.models import ContactSignal
        cs = ContactSignal(connection_id="test-uuid", signal="WARM_LEAD")
        assert cs.__tablename__ == "contact_signals"

    def test_contact_signal_uuid_pk(self):
        from src.database.models import ContactSignal
        cs1 = ContactSignal(connection_id="x", signal="NURTURE")
        cs2 = ContactSignal(connection_id="x", signal="NURTURE")
        assert cs1.id is not None
        assert cs2.id is not None
        assert cs1.id != cs2.id

    def test_contact_signal_required_fields(self):
        from src.database.models import ContactSignal
        cs = ContactSignal(connection_id="conn-1", signal="ARCHIVE")
        assert cs.connection_id == "conn-1"
        assert cs.signal == "ARCHIVE"

    def test_contact_signal_optional_context(self):
        from src.database.models import ContactSignal
        cs = ContactSignal(connection_id="x", signal="WARM_LEAD", signal_context="Hot intro from meetup")
        assert cs.signal_context == "Hot intro from meetup"

    def test_contact_signal_assigned_by_default(self):
        from src.database.models import ContactSignal
        cs = ContactSignal(connection_id="x", signal="SYNERGY")
        assert cs.assigned_by == "user"

    def test_contact_signal_assigned_at_defaults_to_now(self):
        from src.database.models import ContactSignal
        before = datetime.utcnow()
        cs = ContactSignal(connection_id="x", signal="RECONNECT")
        after = datetime.utcnow()
        assert before <= cs.assigned_at <= after


class TestContactNoteModel:
    """ContactNote model has correct tablename and required fields."""

    def test_contact_note_tablename(self):
        from src.database.models import ContactNote
        cn = ContactNote(connection_id="test-uuid", note_text="This is a note")
        assert cn.__tablename__ == "contact_notes"

    def test_contact_note_uuid_pk(self):
        from src.database.models import ContactNote
        cn1 = ContactNote(connection_id="x", note_text="note 1")
        cn2 = ContactNote(connection_id="x", note_text="note 2")
        assert cn1.id is not None
        assert cn2.id is not None
        assert cn1.id != cn2.id

    def test_contact_note_required_fields(self):
        from src.database.models import ContactNote
        cn = ContactNote(connection_id="conn-1", note_text="Meeting follow-up")
        assert cn.connection_id == "conn-1"
        assert cn.note_text == "Meeting follow-up"

    def test_contact_note_timestamps_default(self):
        from src.database.models import ContactNote
        before = datetime.utcnow()
        cn = ContactNote(connection_id="x", note_text="test")
        after = datetime.utcnow()
        assert before <= cn.created_at <= after
        assert before <= cn.updated_at <= after


class TestExistingModelNewFields:
    """New nullable fields added to Connection, OutreachQueueItem, UserProfile."""

    def test_connection_has_latest_signal(self):
        from src.database.models import Connection
        conn = Connection(name="Alice Smith")
        assert hasattr(conn, "latest_signal")
        assert conn.latest_signal is None

    def test_connection_has_cadence_due_at(self):
        from src.database.models import Connection
        conn = Connection(name="Alice Smith")
        assert hasattr(conn, "cadence_due_at")
        assert conn.cadence_due_at is None

    def test_outreach_queue_item_has_signal(self):
        from src.database.models import OutreachQueueItem
        item = OutreachQueueItem(connection_id="x", channel="email")
        assert hasattr(item, "signal")
        assert item.signal is None

    def test_outreach_queue_item_has_signal_context(self):
        from src.database.models import OutreachQueueItem
        item = OutreachQueueItem(connection_id="x", channel="email")
        assert hasattr(item, "signal_context")
        assert item.signal_context is None

    def test_outreach_queue_item_has_mini_key_factors(self):
        from src.database.models import OutreachQueueItem
        item = OutreachQueueItem(connection_id="x", channel="email")
        assert hasattr(item, "mini_key_factors")
        assert item.mini_key_factors is None

    def test_user_profile_has_current_projects(self):
        from src.database.models import UserProfile
        up = UserProfile(name="Gavin")
        assert hasattr(up, "current_projects")
        assert up.current_projects is None

    def test_user_profile_has_goals_structured(self):
        from src.database.models import UserProfile
        up = UserProfile(name="Gavin")
        assert hasattr(up, "goals_structured")
        assert up.goals_structured is None


class TestDatabaseInit:
    """Both new models are importable from src.database."""

    def test_contact_signal_in_database_init(self):
        from src.database import ContactSignal
        cs = ContactSignal(connection_id="x", signal="WARM_LEAD")
        assert cs.__tablename__ == "contact_signals"

    def test_contact_note_in_database_init(self):
        from src.database import ContactNote
        cn = ContactNote(connection_id="x", note_text="test")
        assert cn.__tablename__ == "contact_notes"

    def test_contact_signal_in_all(self):
        import src.database
        assert "ContactSignal" in src.database.__all__

    def test_contact_note_in_all(self):
        import src.database
        assert "ContactNote" in src.database.__all__

    def test_engagement_signal_not_confused(self):
        """EngagementSignal (existing) is separate from ContactSignal (new)."""
        from src.database.models import EngagementSignal, ContactSignal
        assert EngagementSignal.__tablename__ == "engagement_signals"
        assert ContactSignal.__tablename__ == "contact_signals"


# ---------------------------------------------------------------------------
# Task 2: signal_service module tests
# ---------------------------------------------------------------------------

class TestSignalActions:
    """SIGNAL_ACTIONS dict has exactly 7 signals with correct values per CONTEXT.md."""

    def test_signal_actions_has_7_signals(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        assert len(SIGNAL_ACTIONS) == 7

    def test_all_7_signals_present(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        expected = {"WARM_LEAD", "NURTURE", "VALUE_DROP", "SYNERGY", "RECONNECT", "FUTURE_PIVOT", "ARCHIVE"}
        assert set(SIGNAL_ACTIONS.keys()) == expected

    def test_warm_lead_values(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        sig = SIGNAL_ACTIONS["WARM_LEAD"]
        assert sig.cadence_days == 7
        assert sig.queue_status == "approved"
        assert sig.priority_boost == 15

    def test_nurture_values(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        sig = SIGNAL_ACTIONS["NURTURE"]
        assert sig.cadence_days == 21
        assert sig.queue_status == "pending_review"
        assert sig.priority_boost == 0

    def test_value_drop_values(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        sig = SIGNAL_ACTIONS["VALUE_DROP"]
        assert sig.cadence_days == 14
        assert sig.queue_status == "skipped"
        assert sig.priority_boost == 0

    def test_synergy_values(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        sig = SIGNAL_ACTIONS["SYNERGY"]
        assert sig.cadence_days == 14
        assert sig.queue_status == "approved"
        assert sig.priority_boost == 10

    def test_reconnect_values(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        sig = SIGNAL_ACTIONS["RECONNECT"]
        assert sig.cadence_days == 14
        assert sig.queue_status == "approved"
        assert sig.priority_boost == 5

    def test_future_pivot_values(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        sig = SIGNAL_ACTIONS["FUTURE_PIVOT"]
        assert sig.cadence_days == 60
        assert sig.queue_status == "pending_review"
        assert sig.priority_boost == 0

    def test_archive_values(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        sig = SIGNAL_ACTIONS["ARCHIVE"]
        assert sig.cadence_days is None
        assert sig.queue_status == "skipped"
        assert sig.priority_boost == 0


class TestApplySignal:
    """apply_signal() creates ContactSignal and updates Connection fields."""

    def _make_connection(self, session, name="Test User"):
        from src.database.models import Connection
        conn = Connection(name=name)
        session.add(conn)
        session.commit()
        session.refresh(conn)
        return conn

    def test_apply_signal_raises_on_unknown(self):
        from src.services.signal_service import apply_signal
        with pytest.raises(ValueError, match="Unknown signal"):
            apply_signal("nonexistent-conn", "NOT_A_SIGNAL")

    def test_apply_signal_creates_contact_signal(self):
        from sqlmodel import create_engine, SQLModel, Session, select
        from src.database.models import Connection, ContactSignal
        from src.services.signal_service import apply_signal

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            conn = Connection(name="Alice")
            session.add(conn)
            session.commit()
            session.refresh(conn)

            # Monkey-patch get_session for this test
            import src.services.signal_service as ss
            from contextlib import contextmanager

            @contextmanager
            def mock_session():
                yield session

            original = ss.get_session
            ss.get_session = mock_session
            try:
                result = apply_signal(conn.id, "WARM_LEAD")
                assert result.signal == "WARM_LEAD"
                assert result.connection_id == conn.id
                assert result.assigned_by == "user"
            finally:
                ss.get_session = original

    def test_apply_signal_updates_latest_signal(self):
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        from src.services.signal_service import apply_signal
        from contextlib import contextmanager

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            conn = Connection(name="Bob")
            session.add(conn)
            session.commit()
            session.refresh(conn)

            import src.services.signal_service as ss

            @contextmanager
            def mock_session():
                yield session

            original = ss.get_session
            ss.get_session = mock_session
            try:
                apply_signal(conn.id, "NURTURE")
                session.refresh(conn)
                assert conn.latest_signal == "NURTURE"
            finally:
                ss.get_session = original

    def test_apply_signal_sets_cadence_due_at(self):
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        from src.services.signal_service import apply_signal, SIGNAL_ACTIONS
        from contextlib import contextmanager

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            conn = Connection(name="Carol")
            session.add(conn)
            session.commit()
            session.refresh(conn)

            import src.services.signal_service as ss

            @contextmanager
            def mock_session():
                yield session

            original = ss.get_session
            ss.get_session = mock_session
            try:
                before = datetime.utcnow()
                apply_signal(conn.id, "WARM_LEAD")
                session.refresh(conn)
                expected_due = before + timedelta(days=7)
                assert conn.cadence_due_at is not None
                # Allow a 5-second window for test execution
                assert abs((conn.cadence_due_at - expected_due).total_seconds()) < 5
            finally:
                ss.get_session = original

    def test_apply_signal_archive_sets_user_priority_never(self):
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        from src.services.signal_service import apply_signal
        from contextlib import contextmanager

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            conn = Connection(name="Dave")
            session.add(conn)
            session.commit()
            session.refresh(conn)

            import src.services.signal_service as ss

            @contextmanager
            def mock_session():
                yield session

            original = ss.get_session
            ss.get_session = mock_session
            try:
                apply_signal(conn.id, "ARCHIVE")
                session.refresh(conn)
                assert conn.user_priority == "never"
                assert conn.cadence_due_at is None
                assert conn.latest_signal == "ARCHIVE"
            finally:
                ss.get_session = original

    def test_apply_signal_archive_sets_cadence_none(self):
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        from src.services.signal_service import apply_signal
        from contextlib import contextmanager

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            conn = Connection(name="Eve")
            session.add(conn)
            session.commit()
            session.refresh(conn)

            import src.services.signal_service as ss

            @contextmanager
            def mock_session():
                yield session

            original = ss.get_session
            ss.get_session = mock_session
            try:
                apply_signal(conn.id, "ARCHIVE")
                session.refresh(conn)
                assert conn.cadence_due_at is None
            finally:
                ss.get_session = original

    def test_apply_signal_with_context(self):
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        from src.services.signal_service import apply_signal
        from contextlib import contextmanager

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            conn = Connection(name="Frank")
            session.add(conn)
            session.commit()
            session.refresh(conn)

            import src.services.signal_service as ss

            @contextmanager
            def mock_session():
                yield session

            original = ss.get_session
            ss.get_session = mock_session
            try:
                result = apply_signal(conn.id, "SYNERGY", signal_context="Mutual contacts at AWS")
                assert result.signal_context == "Mutual contacts at AWS"
            finally:
                ss.get_session = original


class TestBackfillSkippedSignals:
    """backfill_skipped_signals() maps existing skipped items to correct signals."""

    def _setup_in_memory(self):
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection, OutreachQueueItem
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        session = Session(engine)
        return session

    def test_backfill_maps_queue_reset_to_reconnect(self):
        from src.database.models import Connection, OutreachQueueItem
        from src.services.signal_service import backfill_skipped_signals
        from contextlib import contextmanager
        import src.services.signal_service as ss

        session = self._setup_in_memory()
        conn = Connection(name="Grace")
        session.add(conn)
        session.commit()
        session.refresh(conn)

        item = OutreachQueueItem(
            connection_id=conn.id,
            channel="email",
            status="skipped",
            skip_reason="Queue reset - new batch",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        @contextmanager
        def mock_session():
            yield session

        original = ss.get_session
        ss.get_session = mock_session
        try:
            counts = backfill_skipped_signals()
            session.refresh(item)
            assert item.signal == "RECONNECT"
            assert counts["reconnect"] >= 1
        finally:
            ss.get_session = original
            session.close()

    def test_backfill_maps_auto_expired_to_reconnect(self):
        from src.database.models import Connection, OutreachQueueItem
        from src.services.signal_service import backfill_skipped_signals
        from contextlib import contextmanager
        import src.services.signal_service as ss

        session = self._setup_in_memory()
        conn = Connection(name="Henry")
        session.add(conn)
        session.commit()
        session.refresh(conn)

        item = OutreachQueueItem(
            connection_id=conn.id,
            channel="email",
            status="skipped",
            skip_reason="Auto-expired after 14 days",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        @contextmanager
        def mock_session():
            yield session

        original = ss.get_session
        ss.get_session = mock_session
        try:
            counts = backfill_skipped_signals()
            session.refresh(item)
            assert item.signal == "RECONNECT"
            assert counts["reconnect"] >= 1
        finally:
            ss.get_session = original
            session.close()

    def test_backfill_maps_explicit_user_skip_to_future_pivot(self):
        from src.database.models import Connection, OutreachQueueItem
        from src.services.signal_service import backfill_skipped_signals
        from contextlib import contextmanager
        import src.services.signal_service as ss

        session = self._setup_in_memory()
        conn = Connection(name="Iris")
        session.add(conn)
        session.commit()
        session.refresh(conn)

        item = OutreachQueueItem(
            connection_id=conn.id,
            channel="email",
            status="skipped",
            skip_reason="Not right now",
            reviewed_at=datetime.utcnow(),
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        @contextmanager
        def mock_session():
            yield session

        original = ss.get_session
        ss.get_session = mock_session
        try:
            counts = backfill_skipped_signals()
            session.refresh(item)
            assert item.signal == "FUTURE_PIVOT"
            assert counts["future_pivot"] >= 1
        finally:
            ss.get_session = original
            session.close()

    def test_backfill_skips_already_set_signals(self):
        from src.database.models import Connection, OutreachQueueItem
        from src.services.signal_service import backfill_skipped_signals
        from contextlib import contextmanager
        import src.services.signal_service as ss

        session = self._setup_in_memory()
        conn = Connection(name="Jack")
        session.add(conn)
        session.commit()
        session.refresh(conn)

        item = OutreachQueueItem(
            connection_id=conn.id,
            channel="email",
            status="skipped",
            skip_reason="Queue reset",
            signal="ARCHIVE",  # already set
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        @contextmanager
        def mock_session():
            yield session

        original = ss.get_session
        ss.get_session = mock_session
        try:
            counts = backfill_skipped_signals()
            session.refresh(item)
            assert item.signal == "ARCHIVE"  # unchanged
            assert counts.get("already_set", 0) >= 1
        finally:
            ss.get_session = original
            session.close()

    def test_backfill_returns_counts_dict(self):
        from src.services.signal_service import backfill_skipped_signals
        from contextlib import contextmanager
        from sqlmodel import create_engine, SQLModel, Session
        import src.services.signal_service as ss

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        session = Session(engine)

        @contextmanager
        def mock_session():
            yield session

        original = ss.get_session
        ss.get_session = mock_session
        try:
            counts = backfill_skipped_signals()
            assert "reconnect" in counts
            assert "future_pivot" in counts
            assert "already_set" in counts
        finally:
            ss.get_session = original
            session.close()


class TestSignalServiceExports:
    """signal_service exports the correct symbols."""

    def test_exports_signal_actions(self):
        from src.services.signal_service import SIGNAL_ACTIONS
        assert SIGNAL_ACTIONS is not None

    def test_exports_signal_action_dataclass(self):
        from src.services.signal_service import SignalAction
        assert SignalAction is not None

    def test_exports_apply_signal(self):
        from src.services.signal_service import apply_signal
        assert callable(apply_signal)

    def test_exports_backfill_skipped_signals(self):
        from src.services.signal_service import backfill_skipped_signals
        assert callable(backfill_skipped_signals)


# ---------------------------------------------------------------------------
# Plan 02: Sync field and model import tests
# ---------------------------------------------------------------------------

class TestSyncFieldUpdates:
    """CONNECTION_SYNC_FIELDS includes the new signal foundation fields (Plan 02)."""

    def test_connection_sync_fields_updated(self):
        from src.sync.push import CONNECTION_SYNC_FIELDS
        assert "latest_signal" in CONNECTION_SYNC_FIELDS, (
            "latest_signal must be in CONNECTION_SYNC_FIELDS for cloud sync"
        )
        assert "cadence_due_at" in CONNECTION_SYNC_FIELDS, (
            "cadence_due_at must be in CONNECTION_SYNC_FIELDS for cloud sync"
        )

    def test_contact_signal_sync_stats_key(self):
        """push.py stats dict must include contact_signals key."""
        import inspect
        import src.sync.push as push_mod
        source = inspect.getsource(push_mod)
        assert '"contact_signals": 0' in source or "'contact_signals': 0" in source, (
            "contact_signals must be initialized in push_to_cloud stats dict"
        )

    def test_contact_notes_sync_stats_key(self):
        """push.py stats dict must include contact_notes key."""
        import inspect
        import src.sync.push as push_mod
        source = inspect.getsource(push_mod)
        assert '"contact_notes": 0' in source or "'contact_notes': 0" in source, (
            "contact_notes must be initialized in push_to_cloud stats dict"
        )


class TestModelsImportable:
    """ContactSignal and ContactNote are importable with correct tablenames."""

    def test_models_importable(self):
        from src.database.models import ContactSignal, ContactNote
        assert ContactSignal.__tablename__ == "contact_signals"
        assert ContactNote.__tablename__ == "contact_notes"

    def test_contact_signal_importable_from_push(self):
        """push.py must import ContactSignal for sync sections."""
        import src.sync.push as push_mod
        assert hasattr(push_mod, "ContactSignal"), (
            "ContactSignal must be imported in push.py for sync"
        )

    def test_contact_note_importable_from_push(self):
        """push.py must import ContactNote for sync sections."""
        import src.sync.push as push_mod
        assert hasattr(push_mod, "ContactNote"), (
            "ContactNote must be imported in push.py for sync"
        )
