"""
HL7 v2.x Message Stream Parser.
Handles standard delimiter extraction, multi-message streams, and segment tree extraction.
"""

from typing import List, Optional, Union
import io
from .models import HL7Message, HL7Segment, HL7MessageType


def parse_hl7_stream(content_or_path: Union[str, io.StringIO]) -> List[HL7Message]:
    """
    Parses a string or file containing one or more HL7 v2.x messages.
    """
    if isinstance(content_or_path, io.StringIO):
        raw_text = content_or_path.getvalue()
    elif isinstance(content_or_path, str) and "\n" not in content_or_path and len(content_or_path) > 0 and not content_or_path.startswith("MSH"):
        # Treat as file path only if it looks like a path (non-empty, no newlines, not HL7 content)
        with open(content_or_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
            raw_text = f.read()
    elif isinstance(content_or_path, str) and ("\n" in content_or_path or "\r" in content_or_path or content_or_path.startswith("MSH")):
        raw_text = content_or_path
    elif isinstance(content_or_path, str) and len(content_or_path) == 0:
        # Empty string - return empty list
        return []
    else:
        raw_text = str(content_or_path)

    # Normalize line breaks
    normalized_lines = [
        line.strip() for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]

    messages: List[HL7Message] = []
    current_msg: Optional[HL7Message] = None

    for line_num, line in enumerate(normalized_lines, start=1):
        if line.startswith("MSH"):
            if current_msg is not None:
                messages.append(current_msg)

            # MSH segment defines delimiters
            # MSH|^~\&|...
            field_sep = line[3] if len(line) > 3 else "|"
            enc_chars = line[4:8] if len(line) >= 8 else "^~\\&"
            comp_sep = enc_chars[0] if len(enc_chars) > 0 else "^"
            rep_sep = enc_chars[1] if len(enc_chars) > 1 else "~"
            esc_char = enc_chars[2] if len(enc_chars) > 2 else "\\"
            subcomp_sep = enc_chars[3] if len(enc_chars) > 3 else "&"

            raw_fields = line.split(field_sep)
            # In MSH, fields[0] is "MSH", fields[1] is encoding characters "^~\&", fields[2] is Sending App, etc.
            # We standardize fields such that MSH-1 is field_sep, MSH-2 is encoding chars
            msh_fields = ["MSH", field_sep] + raw_fields[1:]

            msg_type_str = msh_fields[9] if len(msh_fields) > 9 else ""
            msg_control_id = msh_fields[10] if len(msh_fields) > 10 else ""

            msg_type = HL7MessageType.UNKNOWN
            for mt in HL7MessageType:
                if mt.value in msg_type_str:
                    msg_type = mt
                    break

            current_msg = HL7Message(
                raw_text=line,
                segments=[HL7Segment(name="MSH", fields=msh_fields, line_num=line_num)],
                message_type=msg_type,
                control_id=msg_control_id,
                field_sep=field_sep,
                comp_sep=comp_sep,
                subcomp_sep=subcomp_sep,
                rep_sep=rep_sep,
                esc_char=esc_char,
            )
        else:
            if current_msg is None:
                continue
            field_sep = current_msg.field_sep
            raw_fields = line.split(field_sep)
            seg_name = raw_fields[0]
            current_msg.segments.append(
                HL7Segment(name=seg_name, fields=raw_fields, line_num=line_num)
            )

    if current_msg is not None:
        messages.append(current_msg)

    return messages
