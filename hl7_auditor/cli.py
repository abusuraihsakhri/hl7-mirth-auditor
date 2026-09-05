"""
CLI for hl7-mirth-auditor.
"""

import argparse
import os
import sys
from .parser import parse_hl7_stream
from .auditor import audit_stream
from .sanitizer import sanitize_stream


SAMPLE_HL7_STREAM = """MSH|^~\\&|EPIC_LIS|HOSPITAL_LAB|MIRTH_ROUTER|EMR|20260825080000||ORU^R01|MSG-99201|P|2.5.1
PID|1||MRN-8830129^^^MRN||DOE^JANE^M||19840315|F|||123 MAIN STREET^^BOSTON^MA^02115||617-555-1234|||||123-45-6789
PV1|1|I|ICU^01^A||||10928^SMITH^JOHN^MD
OBR|1|ORD-202401|LAB-9001|24357-6^URINALYSIS COMPLETE^LN|||20260825073000
OBX|1|NM|2888-6^PROTEIN URINE^LN||300|mg/dL|0-14|HH|||F
OBX|2|NM|5804-0^GLUCOSE URINE^LN||50|mg/dL|NEGATIVE|H|||F
OBX|3|ST|5794-3^LEUKOCYTE ESTERASE^LN||TRACE|MODIFIER|NEGATIVE|A|||F
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="hl7-auditor",
        description="Clinical LIS/HIS HL7 v2.x Stream Inspector, Validation Engine & HIPAA PHI Sanitizer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Audit HL7 message stream for syntax errors, LIS issues, and PHI")
    audit_parser.add_argument("-i", "--input", required=True, help="Path to HL7 message file (.hl7, .txt)")

    # Sanitize command
    san_parser = subparsers.add_parser("sanitize", help="De-identify HL7 message stream (HIPAA Safe Harbor)")
    san_parser.add_argument("-i", "--input", required=True, help="Path to HL7 message file")
    san_parser.add_argument("-o", "--output", required=True, help="Output path for sanitized HL7 stream")

    # Sample command
    sample_parser = subparsers.add_parser("sample-hl7", help="Export realistic sample HL7 ORU^R01 stream")
    sample_parser.add_argument("-o", "--output", default=None, help="Filepath to write (or prints to stdout)")

    args = parser.parse_args(argv)

    if args.command == "sample-hl7":
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(SAMPLE_HL7_STREAM)
            print(f"Sample HL7 stream saved to: {args.output}")
        else:
            sys.stdout.write(SAMPLE_HL7_STREAM)
        return 0

    if args.command == "audit":
        if not os.path.isfile(args.input):
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            return 1
        messages = parse_hl7_stream(args.input)
        report = audit_stream(messages)

        print("=" * 80)
        print(f"  HL7 v2.x STREAM AUDIT REPORT: {args.input}")
        print(f"  Total Messages: {report.total_messages} | Valid: {report.valid_messages} | PHI Findings: {report.phi_detected_count}")
        print("=" * 80)

        if not report.issues:
            print("\n  [PASS] No syntax errors or critical issues detected.")
        else:
            print(f"\n[ISSUES & COMPLIANCE FINDINGS ({len(report.issues)})]")
            for issue in report.issues:
                sev_tag = f"[{issue.severity.value}]"
                print(f"  Line {issue.line_number:3d} | {sev_tag:<14} | Seg: {issue.segment:<4} | {issue.message}")
                if issue.raw_value:
                    print(f"            Raw Value: '{issue.raw_value}'")

        print("=" * 80)
        return 0

    if args.command == "sanitize":
        if not os.path.isfile(args.input):
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            return 1
        messages = parse_hl7_stream(args.input)
        sanitized_content = sanitize_stream(messages)
        # Validate output directory exists
        out_dir = os.path.dirname(os.path.abspath(args.output))
        if not os.path.isdir(out_dir):
            print(f"Error: Output directory not found: {out_dir}", file=sys.stderr)
            return 1
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(sanitized_content)
        print(f"Sanitization complete -> {args.output} ({len(messages)} messages de-identified)")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
