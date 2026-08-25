"""
hl7-mirth-auditor: HL7 v2.x Clinical Message Data Models & Segment Standards.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class HL7MessageType(str, Enum):
    ORU_R01 = "ORU^R01"  # Observation Report / Lab Results
    ORM_O01 = "ORM^O01"  # Order Message
    ADT_A01 = "ADT^A01"  # Patient Admission
    ADT_A08 = "ADT^A08"  # Patient Update
    MDM_T02 = "MDM^T02"  # Medical Document Management
    UNKNOWN = "UNKNOWN"


class AuditSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL_PHI = "CRITICAL_PHI"


@dataclass
class HL7Issue:
    line_number: int
    segment: str
    field_index: int
    severity: AuditSeverity
    message: str
    raw_value: str = ""


@dataclass
class HL7Segment:
    name: str
    fields: List[str]  # fields[0] is segment name (e.g. "PID")
    line_num: int = 1

    def get_field(self, idx: int) -> str:
        # HL7 1-indexed field notation (e.g. PID-3 is fields[3])
        if 0 <= idx < len(self.fields):
            return self.fields[idx]
        return ""


@dataclass
class HL7Message:
    raw_text: str
    segments: List[HL7Segment] = field(default_factory=list)
    message_type: HL7MessageType = HL7MessageType.UNKNOWN
    control_id: str = ""
    field_sep: str = "|"
    comp_sep: str = "^"
    subcomp_sep: str = "&"
    rep_sep: str = "~"
    esc_char: str = "\\"


@dataclass
class AuditReport:
    total_messages: int
    valid_messages: int
    issues: List[HL7Issue]
    phi_detected_count: int
    abnormal_results_count: int
