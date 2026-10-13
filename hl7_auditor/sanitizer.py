"""
HL7 HIPAA De-Identification & PHI Sanitization Engine.
"""

import hashlib
import hmac
import secrets
from typing import List
from .models import HL7Message, HL7Segment


_PSEUDONYM_KEY = secrets.token_bytes(32)


def _pseudo_id(raw: str) -> str:
    if not raw:
        return "ANON-001"
    h = hmac.new(_PSEUDONYM_KEY, raw.encode("utf-8"), hashlib.sha256).hexdigest()[:12].upper()
    return f"SYNTH-{h}"


def sanitize_hl7_message(msg: HL7Message) -> HL7Message:
    """
    Masks commonly identifying fields in a deep copy of the HL7 message.
    This is not a complete Safe Harbor de-identification procedure.
    """
    sep = msg.field_sep
    sanitized_segments: List[HL7Segment] = []

    for seg in msg.segments:
        fields_copy = list(seg.fields)

        if seg.name == "PID":
            # PID-3: Patient Identifier / MRN
            if len(fields_copy) > 3 and fields_copy[3]:
                fields_copy[3] = _pseudo_id(fields_copy[3])

            # PID-5: Patient Name -> "ANONYMOUS^PATIENT"
            if len(fields_copy) > 5 and fields_copy[5]:
                fields_copy[5] = f"ANONYMOUS{msg.comp_sep}PATIENT"

            # PID-7: Date of Birth -> "19800101"
            if len(fields_copy) > 7 and fields_copy[7]:
                fields_copy[7] = "19800101"

            # PID-11: Address -> Redacted
            if len(fields_copy) > 11 and fields_copy[11]:
                fields_copy[11] = f"REDACTED{msg.comp_sep}{msg.comp_sep}REDACTED{msg.comp_sep}XX{msg.comp_sep}00000"

            # PID-13: Phone -> "555-0199"
            if len(fields_copy) > 13 and fields_copy[13]:
                fields_copy[13] = "5550199"

            # Additional direct identifiers defined in PID (alternate IDs,
            # mother's maiden name, alias, county, business phone, accounts,
            # driver's license, birthplace and death date). Do not rely on
            # a nine-digit pattern: many identifiers are alphanumeric.
            for idx in (2, 4):
                if len(fields_copy) > idx and fields_copy[idx]:
                    fields_copy[idx] = _pseudo_id(fields_copy[idx])
            for idx in (6, 9, 12, 20, 21, 23, 29):
                if len(fields_copy) > idx and fields_copy[idx]:
                    fields_copy[idx] = "REDACTED"
            if len(fields_copy) > 14 and fields_copy[14]:
                fields_copy[14] = "5550199"
            for idx in (18, 19):
                if len(fields_copy) > idx and fields_copy[idx]:
                    fields_copy[idx] = "000000000"
            for idx in range(30, len(fields_copy)):
                if fields_copy[idx]:
                    fields_copy[idx] = "REDACTED"

        elif seg.name in ("PV1", "OBR"):
            # Sanitize Attending / Ordering Doctor (PV1-7, OBR-16)
            doc_idx = 7 if seg.name == "PV1" else 16
            if len(fields_copy) > doc_idx and fields_copy[doc_idx]:
                fields_copy[doc_idx] = f"99999{msg.comp_sep}PROVIDER{msg.comp_sep}CLINICAL"

        sanitized_segments.append(
            HL7Segment(name=seg.name, fields=fields_copy, line_num=seg.line_num)
        )

    # Reconstruct raw text
    reconstructed_lines = []
    for seg in sanitized_segments:
        if seg.name == "MSH":
            reconstructed_lines.append(seg.fields[0] + sep + sep.join(seg.fields[2:]))
        else:
            reconstructed_lines.append(sep.join(seg.fields))

    return HL7Message(
        raw_text="\r\n".join(reconstructed_lines),
        segments=sanitized_segments,
        message_type=msg.message_type,
        control_id=msg.control_id,
        field_sep=msg.field_sep,
        comp_sep=msg.comp_sep,
        subcomp_sep=msg.subcomp_sep,
        rep_sep=msg.rep_sep,
        esc_char=msg.esc_char,
    )


def sanitize_stream(messages: List[HL7Message]) -> str:
    """
    Sanitizes all messages in the stream and returns raw string ready to write to file.
    """
    sanitized_msgs = [sanitize_hl7_message(m) for m in messages]
    return "\r\n".join(m.raw_text for m in sanitized_msgs)
