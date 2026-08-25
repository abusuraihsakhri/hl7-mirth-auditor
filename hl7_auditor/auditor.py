"""
HL7 Structural, Clinical LIS, and PHI Compliance Auditor.
"""

import re
from typing import List
from .models import (
    AuditReport,
    AuditSeverity,
    HL7Issue,
    HL7Message,
    HL7MessageType,
)


def audit_hl7_message(msg: HL7Message) -> List[HL7Issue]:
    """
    Audits a single HL7 message against clinical standards and HIPAA PHI guidelines.
    """
    issues: List[HL7Issue] = []

    if not msg.segments:
        return [
            HL7Issue(
                line_number=1,
                segment="N/A",
                field_index=0,
                severity=AuditSeverity.ERROR,
                message="Empty message with no segments.",
            )
        ]

    # Check 1: MSH is first segment
    if msg.segments[0].name != "MSH":
        issues.append(
            HL7Issue(
                line_number=msg.segments[0].line_num,
                segment=msg.segments[0].name,
                field_index=0,
                severity=AuditSeverity.ERROR,
                message="Message does not start with MSH header segment.",
            )
        )

    # Check 2: Message Type recognition
    if msg.message_type == HL7MessageType.UNKNOWN:
        issues.append(
            HL7Issue(
                line_number=msg.segments[0].line_num,
                segment="MSH",
                field_index=9,
                severity=AuditSeverity.WARNING,
                message="MSH-9 does not contain standard recognized message type (e.g. ORU^R01, ADT^A01, ORM^O01).",
            )
        )

    seg_names = [s.name for s in msg.segments]

    # Check 3: PID segment presence
    if "PID" not in seg_names:
        issues.append(
            HL7Issue(
                line_number=1,
                segment="PID",
                field_index=0,
                severity=AuditSeverity.WARNING,
                message="Missing PID (Patient Identification) segment in clinical message.",
            )
        )

    # Check 4: ORU^R01 requirements
    if msg.message_type == HL7MessageType.ORU_R01:
        if "OBR" not in seg_names:
            issues.append(
                HL7Issue(
                    line_number=1,
                    segment="OBR",
                    field_index=0,
                    severity=AuditSeverity.ERROR,
                    message="Lab result message (ORU^R01) missing required OBR (Observation Request) segment.",
                )
            )
        if "OBX" not in seg_names:
            issues.append(
                HL7Issue(
                    line_number=1,
                    segment="OBX",
                    field_index=0,
                    severity=AuditSeverity.ERROR,
                    message="Lab result message (ORU^R01) missing required OBX (Observation Result) segment.",
                )
            )

    # Check per-segment details
    for seg in msg.segments:
        # PID PHI Checks
        if seg.name == "PID":
            pid_mrn = seg.get_field(3)
            if pid_mrn and not pid_mrn.startswith("SYNTH-") and pid_mrn not in ("ANONYMOUS", "REDACTED"):
                issues.append(
                    HL7Issue(
                        line_number=seg.line_num,
                        segment="PID",
                        field_index=3,
                        severity=AuditSeverity.CRITICAL_PHI,
                        message="HIPAA PHI: Medical Record Number (MRN) / Patient ID present in PID-3.",
                        raw_value=pid_mrn,
                    )
                )

            pid_name = seg.get_field(5)
            if pid_name and pid_name not in ("ANONYMOUS^PATIENT", "DEIDENTIFIED", "ANON^DOE"):
                issues.append(
                    HL7Issue(
                        line_number=seg.line_num,
                        segment="PID",
                        field_index=5,
                        severity=AuditSeverity.CRITICAL_PHI,
                        message="HIPAA PHI: Plaintext Patient Name present in PID-5.",
                        raw_value=pid_name,
                    )
                )

            pid_dob = seg.get_field(7)
            if pid_dob and len(pid_dob) >= 8 and pid_dob != "19800101":
                issues.append(
                    HL7Issue(
                        line_number=seg.line_num,
                        segment="PID",
                        field_index=7,
                        severity=AuditSeverity.CRITICAL_PHI,
                        message=f"HIPAA PHI: Date of Birth present in PID-7 ({pid_dob}).",
                        raw_value=pid_dob,
                    )
                )

            # Check fields 18 and 19 for SSN pattern
            for ssn_idx in (18, 19):
                pid_ssn = seg.get_field(ssn_idx)
                if pid_ssn and re.search(r"\d{3}-?\d{2}-?\d{4}", pid_ssn) and pid_ssn != "000000000":
                    issues.append(
                        HL7Issue(
                            line_number=seg.line_num,
                            segment="PID",
                            field_index=ssn_idx,
                            severity=AuditSeverity.CRITICAL_PHI,
                            message=f"HIPAA PHI: Social Security Number (SSN) detected in PID-{ssn_idx}.",
                            raw_value=pid_ssn,
                        )
                    )

        # OBX Checks (Lab results validation)
        if seg.name == "OBX":
            val_type = seg.get_field(2)
            obs_id = seg.get_field(3)
            obs_val = seg.get_field(5)
            units = seg.get_field(6)
            ref_range = seg.get_field(7)
            flag = seg.get_field(8)

            if not val_type:
                issues.append(
                    HL7Issue(
                        line_number=seg.line_num,
                        segment="OBX",
                        field_index=2,
                        severity=AuditSeverity.ERROR,
                        message="OBX-2 Value Type is missing (expected NM, ST, CE, etc.).",
                    )
                )

            if val_type == "NM" and obs_val:
                try:
                    float(obs_val)
                except ValueError:
                    issues.append(
                        HL7Issue(
                            line_number=seg.line_num,
                            segment="OBX",
                            field_index=5,
                            severity=AuditSeverity.ERROR,
                            message=f"OBX-2 declared as Numeric ('NM') but OBX-5 has non-numeric value '{obs_val}'.",
                            raw_value=obs_val,
                        )
                    )

            if flag and flag.upper() in ("HH", "LL", "PANIC", "CRITICAL"):
                issues.append(
                    HL7Issue(
                        line_number=seg.line_num,
                        segment="OBX",
                        field_index=8,
                        severity=AuditSeverity.WARNING,
                        message=f"CRITICAL LAB ALERT: Abnormal Panic Flag '{flag}' in OBX-8 for test '{obs_id}'.",
                        raw_value=flag,
                    )
                )

    return issues


def audit_stream(messages: List[HL7Message]) -> AuditReport:
    """
    Audits a batch of HL7 messages and compiles summary audit report.
    """
    total_issues: List[HL7Issue] = []
    valid_count = 0
    phi_count = 0
    abnormal_count = 0

    for msg in messages:
        issues = audit_hl7_message(msg)
        total_issues.extend(issues)
        
        has_error = any(i.severity == AuditSeverity.ERROR for i in issues)
        if not has_error:
            valid_count += 1

        for i in issues:
            if i.severity == AuditSeverity.CRITICAL_PHI:
                phi_count += 1
            if "CRITICAL LAB ALERT" in i.message:
                abnormal_count += 1

    return AuditReport(
        total_messages=len(messages),
        valid_messages=valid_count,
        issues=total_issues,
        phi_detected_count=phi_count,
        abnormal_results_count=abnormal_count,
    )
