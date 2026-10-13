"""Regression checks for privacy, stream parsing and audit integrity."""
import csv
import io
from contextlib import redirect_stdout

import pytest

from agents.base import AuditTrail
from hl7_auditor.cli import main as hl7_main
from hl7_auditor.parser import parse_hl7_stream
from hl7_auditor.sanitizer import sanitize_stream
from cli import parse_csv_bool


HEADER = r"MSH|^~\&|LAB|FAC|DEST|EHR|20260101120000||ORU^R01|MSG-1|P|2.5"


def test_tampering_with_signed_metadata_detected():
    trail = AuditTrail(secret_key="test-only-hmac-key")
    trail.log("operator", "unit", "TEST", {"event": "baseline"})
    assert trail.verify_integrity()
    trail.logs[0]["event_type"] = "FORGED"
    assert not trail.verify_integrity()


def test_tampering_with_last_signature_detected():
    trail = AuditTrail(secret_key="test-only-hmac-key")
    trail.log("operator", "unit", "TEST", {"event": "baseline"})
    trail.logs[0]["current_hash"] = "0" * 64
    assert not trail.verify_integrity()


def test_audit_log_reader_cannot_modify_chain():
    trail = AuditTrail(secret_key="test-only-hmac-key")
    trail.log("operator", "unit", "TEST", {"event": "baseline"})
    trail.get_trail()[0]["event_type"] = "FORGED"
    assert trail.verify_integrity()


def test_preserve_spaces_and_full_raw_message():
    stream = HEADER + "\rPID|1||SYNTH-0123||ANONYMOUS^PATIENT||19800101\rOBX|1|ST|C||result with trailing spaces  \r"
    msg, = parse_hl7_stream(stream)
    assert msg.segments[-1].get_field(5) == "result with trailing spaces  "
    assert msg.raw_text.count("\r") == 2
    assert "PID|" in msg.raw_text


def test_single_line_invalid_input_is_not_read_as_path():
    assert parse_hl7_stream("not-an-HL7-message") == []


def test_cli_does_not_print_patient_values_by_default(tmp_path):
    file = tmp_path / "patient.hl7"
    file.write_text(HEADER + "\nPID|1||MRN889900||VERYPRIVATE^NAME||19750512|M\n", encoding="utf-8")
    output = io.StringIO()
    with redirect_stdout(output):
        assert hl7_main(["audit", "-i", str(file)]) == 0
    result = output.getvalue()
    assert "VERYPRIVATE" not in result
    assert "19750512" not in result
    assert "MRN889900" not in result
    assert "PHI" in result


@pytest.mark.parametrize(("raw", "expected"), [
    ("FALSE", False), ("False", False), ("0", False),
    ("", False), ("TRUE", True), ("yes", True), ("1", True),
])
def test_csv_boolean_values(raw, expected):
    assert parse_csv_bool(raw) is expected


def test_invalid_csv_boolean_rejected():
    with pytest.raises(ValueError):
        parse_csv_bool("perhaps")


def test_additional_pid_identifiers_are_masked():
    fields = [""] * 31
    fields[0] = "PID"
    fields[1] = "1"
    fields[2] = "EXT123"
    fields[3] = "MRN5"
    fields[4] = "ALTABC"
    fields[5] = "PRIVATE^NAME"
    fields[6] = "MAIDEN"
    fields[7] = "19750512"
    fields[11] = "123 MAIN"
    fields[14] = "6175550101"
    fields[18] = "ACC-772"
    fields[19] = "123-45-6789"
    fields[23] = "HOMETOWN"
    fields[29] = "20200101"
    source = HEADER + "\r" + "|".join(fields)
    sanitized = sanitize_stream(parse_hl7_stream(source))
    for sensitive in ("EXT123", "MRN5", "ALTABC", "PRIVATE", "MAIDEN", "123 MAIN", "ACC-772", "123-45-6789", "HOMETOWN", "20200101"):
        assert sensitive not in sanitized
