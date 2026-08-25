import io
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from hl7_auditor.models import HL7MessageType, AuditSeverity
from hl7_auditor.parser import parse_hl7_stream
from hl7_auditor.auditor import audit_stream, audit_hl7_message
from hl7_auditor.sanitizer import sanitize_stream, sanitize_hl7_message
from hl7_auditor.cli import main


SAMPLE_MSG = """MSH|^~\\&|LAB|HOSP|MIRTH|EMR|20260825||ORU^R01|12345|P|2.5
PID|1||MRN123||SMITH^JOHN||19750512|M|||100 MAIN ST||555-1234|||||111-22-3333
OBR|1|ORD1|LAB1|24357-6^UA
OBX|1|NM|2888-6^PROTEIN||100|mg/dL|0-14|HH|||F
"""


def test_parser():
    messages = parse_hl7_stream(SAMPLE_MSG)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.message_type == HL7MessageType.ORU_R01
    assert msg.control_id == "12345"
    assert len(msg.segments) == 4


def test_auditor_phi_detection():
    messages = parse_hl7_stream(SAMPLE_MSG)
    report = audit_stream(messages)
    assert report.phi_detected_count >= 3  # Name, DOB, SSN
    assert report.abnormal_results_count >= 1  # HH panic flag


def test_sanitizer():
    messages = parse_hl7_stream(SAMPLE_MSG)
    sanitized_text = sanitize_stream(messages)
    assert "SMITH^JOHN" not in sanitized_text
    assert "ANONYMOUS^PATIENT" in sanitized_text
    assert "111-22-3333" not in sanitized_text
    assert "000000000" in sanitized_text


def test_cli(tmp_path):
    hl7_file = tmp_path / "test.hl7"
    hl7_file.write_text(SAMPLE_MSG, encoding="utf-8")
    san_file = tmp_path / "san.hl7"

    assert main(["audit", "-i", str(hl7_file)]) == 0
    assert main(["sanitize", "-i", str(hl7_file), "-o", str(san_file)]) == 0
    assert san_file.exists()
