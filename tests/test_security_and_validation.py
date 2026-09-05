"""
Security, validation, and error handling tests for hl7-mirth-auditor.
"""
import os
import sys
import warnings
from pathlib import Path
from io import StringIO

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from hl7_auditor.models import HL7MessageType, AuditSeverity
from hl7_auditor.parser import parse_hl7_stream
from hl7_auditor.auditor import audit_stream, audit_hl7_message
from hl7_auditor.sanitizer import sanitize_stream, sanitize_hl7_message
from hl7_auditor.cli import main as hl7_cli_main


# ---------------------------------------------------------------------------
# File-not-found handling
# ---------------------------------------------------------------------------

def test_hl7_cli_audit_missing_file():
    """CLI audit command returns non-zero exit code for missing files."""
    exit_code = hl7_cli_main(["audit", "-i", "nonexistent_file.hl7"])
    assert exit_code == 1


def test_hl7_cli_sanitize_missing_file():
    """CLI sanitize command returns non-zero exit code for missing files."""
    exit_code = hl7_cli_main(["sanitize", "-i", "nonexistent_file.hl7", "-o", "out.hl7"])
    assert exit_code == 1


# ---------------------------------------------------------------------------
# Parser edge cases
# ---------------------------------------------------------------------------

def test_parser_empty_stream():
    """Parser handles empty string input."""
    messages = parse_hl7_stream("")
    assert messages == []


def test_parser_no_msh():
    """Parser handles content without MSH segment (multiline input)."""
    content = "PID|1||MRN123||DOE^JOHN\r\nOBR|1|ORD1|LAB1\r\n"
    messages = parse_hl7_stream(content)
    assert messages == []


def test_parser_multiple_messages():
    """Parser splits multiple HL7 messages correctly."""
    content = (
        "MSH|^~\\&|LAB|HOSP|MIRTH|EMR|20260825||ORU^R01|MSG001|P|2.5\r\n"
        "PID|1||MRN001||DOE^JOHN\r\n"
        "MSH|^~\\&|LAB|HOSP|MIRTH|EMR|20260825||ORU^R01|MSG002|P|2.5\r\n"
        "PID|1||MRN002||DOE^JANE\r\n"
    )
    messages = parse_hl7_stream(content)
    assert len(messages) == 2
    assert messages[0].control_id == "MSG001"
    assert messages[1].control_id == "MSG002"


def test_parser_stringio_input():
    """Parser accepts StringIO input."""
    content = "MSH|^~\\&|LAB|HOSP|MIRTH|EMR|20260825||ORU^R01|12345|P|2.5\r\n"
    messages = parse_hl7_stream(StringIO(content))
    assert len(messages) == 1


# ---------------------------------------------------------------------------
# Auditor edge cases
# ---------------------------------------------------------------------------

def test_auditor_empty_message():
    """Auditor handles message with no segments."""
    from hl7_auditor.models import HL7Message
    msg = HL7Message(raw_text="", segments=[])
    issues = audit_hl7_message(msg)
    assert len(issues) == 1
    assert issues[0].severity == AuditSeverity.ERROR


def test_auditor_missing_pid():
    """Auditor flags missing PID segment."""
    content = (
        "MSH|^~\\&|LAB|HOSP|MIRTH|EMR|20260825||ORU^R01|12345|P|2.5\r\n"
        "OBR|1|ORD1|LAB1\r\n"
        "OBX|1|NM|2888-6^PROTEIN||100|mg/dL|0-14|N|||F\r\n"
    )
    messages = parse_hl7_stream(content)
    report = audit_stream(messages)
    pid_warnings = [i for i in report.issues if "Missing PID" in i.message]
    assert len(pid_warnings) >= 1


def test_auditor_obx_numeric_validation():
    """Auditor flags non-numeric value when type is NM."""
    content = (
        "MSH|^~\\&|LAB|HOSP|MIRTH|EMR|20260825||ORU^R01|12345|P|2.5\r\n"
        "PID|1||SYNTH-001||ANONYMOUS^PATIENT||19800101|M\r\n"
        "OBR|1|ORD1|LAB1\r\n"
        "OBX|1|NM|2888-6^PROTEIN||not_a_number|mg/dL|0-14|N|||F\r\n"
    )
    messages = parse_hl7_stream(content)
    report = audit_stream(messages)
    numeric_errors = [i for i in report.issues if "non-numeric" in i.message.lower() or "Numeric" in i.message]
    assert len(numeric_errors) >= 1


# ---------------------------------------------------------------------------
# HMAC Audit Trail security
# ---------------------------------------------------------------------------

def test_audit_trail_requires_secret_or_warns():
    """AuditTrail generates a random key and warns when no secret is set."""
    from agents.base import AuditTrail
    # Ensure env var is not set for this test
    original = os.environ.pop("AUDIT_SECRET_KEY", None)
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            trail = AuditTrail()
            # Should have issued a RuntimeWarning about the key
            runtime_warnings = [x for x in w if issubclass(x.category, RuntimeWarning)]
            assert len(runtime_warnings) >= 1
            assert "AUDIT_SECRET_KEY" in str(runtime_warnings[0].message)
    finally:
        if original is not None:
            os.environ["AUDIT_SECRET_KEY"] = original


def test_audit_trail_with_explicit_key():
    """AuditTrail uses provided key without warning."""
    from agents.base import AuditTrail
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        trail = AuditTrail(secret_key="test-secret-key-for-unit-test")
        runtime_warnings = [x for x in w if issubclass(x.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0
    # Verify it can log and verify
    trail.log("test", "unit", "TEST_EVENT", {"status": "ok"})
    assert trail.verify_integrity() is True


def test_audit_trail_tamper_detection():
    """AuditTrail detects broken chain when entries are inserted/removed."""
    from agents.base import AuditTrail
    trail = AuditTrail(secret_key="tamper-test-key")
    trail.log("actor", "tier", "EVENT_1", {"data": "first"})
    trail.log("actor", "tier", "EVENT_2", {"data": "second"})
    assert trail.verify_integrity() is True
    # Remove the first entry - breaks the chain for entry 2
    trail.logs.pop(0)
    assert trail.verify_integrity() is False


# ---------------------------------------------------------------------------
# PHI Guard edge cases
# ---------------------------------------------------------------------------

def test_phi_guard_empty_string():
    """PHI guard allows empty strings."""
    from agents.base import PHIGuard
    PHIGuard.assert_no_phi("")
    PHIGuard.assert_no_phi(None)


def test_phi_guard_redaction():
    """PHI guard redacts sensitive patterns."""
    from agents.base import PHIGuard
    text = "Patient MRN-1234567 has phone 555-123-4567"
    redacted = PHIGuard.redact_phi(text)
    assert "MRN-1234567" not in redacted
    assert "555-123-4567" not in redacted
    assert "REDACTED" in redacted or "[REDACTED" in redacted
