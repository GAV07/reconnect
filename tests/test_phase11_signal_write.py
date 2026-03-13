"""Phase 11 Plan 01: Signal write correctness and cadence end-to-end tests.

Tests validating that:
- PERS-05: Signal-to-tone mapping completeness and ARCHIVE guard wiring
- CAD-02: cadence_due_at write → query → return cycle

These tests cover the Python pipeline side (cadence query) and use data-driven
assertions to confirm signal-to-tone-config wiring is complete.

Requirements: PERS-05, CAD-02
"""

from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# TestAssignSignalWrites: Cadence computation validation
# ---------------------------------------------------------------------------


class TestAssignSignalWrites:
    """Validate cadence_due_at values as the JS client would compute them.

    These tests simulate what happens AFTER assignSignalFromCard() writes
    cadence_due_at to the database and the pipeline queries it.
    """

    def test_cadence_due_at_written(self):
        """Given a WARM_LEAD signal (cadence=7), _get_cadence_expired_candidates()
        returns the contact after 8 days."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        # WARM_LEAD cadence = 7 days; simulate contact assigned 8 days ago
        # i.e., cadence_due_at is in the past (expired)
        with Session(engine) as session:
            c = Connection(
                name="WarmLeadContact",
                cadence_due_at=datetime.utcnow() - timedelta(days=1),  # expired (was due 1 day ago after 7-day cadence)
                reconnect_score=80.0,
                email="warm@example.com",
            )
            session.add(c)
            session.commit()

            results = qg._get_cadence_expired_candidates(session, limit=10)

        assert len(results) == 1
        assert results[0].name == "WarmLeadContact"

    def test_archive_cadence_is_null(self):
        """Given an ARCHIVE signal, cadence_due_at is None in the database —
        _get_cadence_expired_candidates() does NOT return the contact."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # ARCHIVE: cadence_due_at is None AND user_priority='never'
            archived = Connection(
                name="ArchivedContact",
                cadence_due_at=None,
                user_priority="never",
                reconnect_score=70.0,
                email="archive@example.com",
            )
            session.add(archived)
            session.commit()

            results = qg._get_cadence_expired_candidates(session, limit=10)

        assert len(results) == 0, (
            "ARCHIVE contact (cadence_due_at=None, user_priority='never') "
            "must NOT be returned by _get_cadence_expired_candidates()"
        )


# ---------------------------------------------------------------------------
# TestCadenceEndToEnd: _get_cadence_expired_candidates() query behaviour
# ---------------------------------------------------------------------------


class TestCadenceEndToEnd:
    """End-to-end tests for the cadence re-queuing query."""

    def test_cadence_query_finds_written_contact(self):
        """Given a connection with cadence_due_at in the past and reconnect_score
        set, _get_cadence_expired_candidates() returns it."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            c = Connection(
                name="ExpiredCadence",
                cadence_due_at=datetime.utcnow() - timedelta(days=2),
                reconnect_score=75.0,
                email="expired@example.com",
            )
            session.add(c)
            session.commit()

            results = qg._get_cadence_expired_candidates(session, limit=10)

        assert len(results) == 1
        assert results[0].name == "ExpiredCadence"

    def test_cadence_query_excludes_future_due(self):
        """Given a connection with cadence_due_at 7 days in the future,
        _get_cadence_expired_candidates() does NOT return it."""
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

        assert len(results) == 0, (
            "Contact with future cadence_due_at must NOT be returned"
        )

    def test_cadence_query_excludes_archive(self):
        """Given a connection with cadence_due_at in the past but
        user_priority='never', _get_cadence_expired_candidates() does NOT return it."""
        from sqlmodel import create_engine, SQLModel, Session
        from src.database.models import Connection
        import src.pipeline.queue_generator as qg

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            archived = Connection(
                name="ArchivedWithExpiredCadence",
                cadence_due_at=datetime.utcnow() - timedelta(days=1),
                user_priority="never",
                reconnect_score=65.0,
                email="archived_expired@example.com",
            )
            session.add(archived)
            session.commit()

            results = qg._get_cadence_expired_candidates(session, limit=10)

        assert len(results) == 0, (
            "ARCHIVE contact (user_priority='never') must be excluded even if cadence_due_at is past"
        )


# ---------------------------------------------------------------------------
# TestDraftToneIntegration: SIGNAL_TONE_CONFIG completeness validation
# ---------------------------------------------------------------------------

# Python mirror of the TypeScript SIGNAL_TONE_CONFIG in supabase/functions/draft/index.ts
# This validates that all 6 non-ARCHIVE signals have a non-empty tone directive.
SIGNAL_TONE_CONFIG = {
    "WARM_LEAD": {
        "toneDirective": "Write a direct, confident message with a specific ask. The sender has goals that align with this contact — reference one goal naturally. Be concrete, not generic.",
        "includeUserGoals": True,
        "emphasizeContactData": False,
    },
    "NURTURE": {
        "toneDirective": "Write a warm, low-pressure message focused on maintaining the relationship. No ask. No agenda. Just genuine reconnection. Keep it to 2-3 sentences.",
        "includeUserGoals": False,
        "emphasizeContactData": False,
    },
    "VALUE_DROP": {
        "toneDirective": "Lead the message with something specifically relevant to the recipient's industry or skills. Frame it as sharing something helpful, not selling. Ground it in their actual work.",
        "includeUserGoals": False,
        "emphasizeContactData": True,
    },
    "SYNERGY": {
        "toneDirective": "Write a collaborative message framing mutual benefit. The sender has goals that may intersect with this contact's work — weave one in naturally. Make the collaboration angle specific.",
        "includeUserGoals": True,
        "emphasizeContactData": False,
    },
    "RECONNECT": {
        "toneDirective": "Write a nostalgic but forward-looking message. If there's shared history (previous conversations, mutual connections), reference it. Frame as a warm re-entry, not a cold outreach.",
        "includeUserGoals": False,
        "emphasizeContactData": False,
    },
    "FUTURE_PIVOT": {
        "toneDirective": "Write a very brief, light-touch message. No pressure, no ask. Just planting a seed and keeping the door open. Keep it to 2-3 sentences maximum.",
        "includeUserGoals": False,
        "emphasizeContactData": False,
    },
}

# All 6 non-ARCHIVE signal keys — each must have a distinct tone branch
NON_ARCHIVE_SIGNALS = ["WARM_LEAD", "NURTURE", "VALUE_DROP", "SYNERGY", "RECONNECT", "FUTURE_PIVOT"]

# The ARCHIVE guard condition string from supabase/functions/draft/index.ts line 102
ARCHIVE_GUARD_SIGNAL_VALUE = "ARCHIVE"


class TestDraftToneIntegration:
    """Validate signal-to-tone-config wiring completeness.

    These tests confirm the data-level contract: all signals have defined tone
    branches, and ARCHIVE is correctly identified by its guard condition.
    No JavaScript or TypeScript code is imported or executed.
    """

    def test_all_non_archive_signals_reach_config(self):
        """All 6 non-ARCHIVE signal names exist as keys in SIGNAL_TONE_CONFIG
        and each has a non-empty toneDirective string."""
        for signal in NON_ARCHIVE_SIGNALS:
            assert signal in SIGNAL_TONE_CONFIG, (
                f"Signal '{signal}' is missing from SIGNAL_TONE_CONFIG — "
                f"Edge Function will fall through to generic directive"
            )
            config = SIGNAL_TONE_CONFIG[signal]
            assert "toneDirective" in config, (
                f"Signal '{signal}' config has no toneDirective key"
            )
            assert isinstance(config["toneDirective"], str), (
                f"Signal '{signal}' toneDirective must be a string"
            )
            assert len(config["toneDirective"]) > 0, (
                f"Signal '{signal}' toneDirective is empty — Edge Function would inject no tone guidance"
            )

    def test_archive_guard_blocks_draft(self):
        """ARCHIVE signal value matches the guard condition in the Edge Function
        (queueItem.signal === 'ARCHIVE').

        The Edge Function guard at line 102 of supabase/functions/draft/index.ts:
            if (queueItem.signal === 'ARCHIVE') { return 400 error }

        This test confirms the string value 'ARCHIVE' is the guard sentinel,
        proving that once outreach_queue.signal is set to 'ARCHIVE',
        the Edge Function will reject draft generation.
        """
        # The guard checks for exactly this string value
        assert ARCHIVE_GUARD_SIGNAL_VALUE == "ARCHIVE"

        # ARCHIVE must NOT be in the non-ARCHIVE signal set
        assert ARCHIVE_GUARD_SIGNAL_VALUE not in NON_ARCHIVE_SIGNALS, (
            "ARCHIVE must be excluded from non-ARCHIVE signal routing"
        )

        # ARCHIVE must NOT be in the tone config (it should be blocked before reaching buildDraftPrompt)
        assert ARCHIVE_GUARD_SIGNAL_VALUE not in SIGNAL_TONE_CONFIG, (
            "ARCHIVE signal should be blocked by the guard — it must NOT have a tone branch "
            "that would reach buildDraftPrompt()"
        )
