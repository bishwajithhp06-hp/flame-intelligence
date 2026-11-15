import textwrap
import unicodedata
from datetime import datetime, timezone
from typing import List

from app.schemas.experiments import ExperimentComparison
from app.schemas.mission import MissionAnalysisResponse


def build_mission_report(
    analysis: MissionAnalysisResponse,
    generated_at: datetime | None = None,
    report_name: str | None = None,
) -> bytes:
    timestamp = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    params = analysis.scenario_parameters
    mission_name = report_name or f"{analysis.environment} Mission Intelligence Analysis"
    lines = [
        "FLAME INTELLIGENCE - MISSION RESEARCH REPORT",
        f"Mission name: {mission_name}",
        f"Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "MISSION SCENARIO AND USER-SUBMITTED PARAMETERS",
        f"Environment: {params.environment}",
        f"Oxygen concentration: {params.oxygen_percent}%",
        f"Pressure: {params.pressure_atm} atm",
        f"Airflow: {params.airflow_cm_s} cm/s",
        f"Gravity scenario: {params.gravity}",
        f"Material / fuel scenario: {params.material}",
        "All scenario values above are hypothetical user inputs, not NASA measurements.",
        "",
        "EVIDENCE STATUS",
        analysis.evidence_status,
        *[f"Limitation: {item}" for item in analysis.evidence_limitations],
        "",
        "FIVE SPECIALIST SUMMARIES",
    ]
    for item in analysis.specialist_analyses:
        lines.extend([
            "",
            item.role,
            f"Evidence status: {item.evidence_status}",
            item.analysis,
            *[f"Assumption: {value}" for value in item.assumptions],
            *[f"Uncertainty: {value}" for value in item.uncertainties],
            *[f"Cited source: {citation.title} | {citation.url or citation.identifier or citation.doi or 'No URL or identifier supplied'}"
              for citation in item.citations],
        ])

    lines.extend(["", "MISSION SAFETY SYNTHESIS", analysis.mission_synthesis])
    details = analysis.synthesis_details
    lines.extend([
        f"Conflict assessment: {details.conflict_assessment}",
        *[f"Conflicting claim: {value}" for value in details.conflicting_claims],
        *[f"Documented finding: {item.finding}" for item in details.main_documented_findings],
        *[f"Synthesis uncertainty: {value}" for value in details.important_uncertainties],
        *[f"Synthesis research gap: {value}" for value in details.research_gaps],
        "",
        "RETRIEVED EVIDENCE AND CONDITION MATCHES",
    ])
    if not analysis.evidence_matches:
        lines.append("No matching investigation records were retrieved.")
    for record in analysis.evidence_matches:
        lines.extend([
            "",
            f"{record.investigation_title} ({record.investigation_acronym})",
            f"Evidence status: {record.evidence_status}",
            f"Provenance class: {record.evidence_class}",
            f"Original source: {record.original_source_url or 'Not supplied'}",
            f"Why retrieved: {record.relevance_explanation}",
        ])
        for match in record.parameter_matches:
            lines.append(
                f"Condition {match.parameter}: {match.status}; scenario={match.scenario_value}; "
                f"record={match.recorded_value or 'unavailable'}; {match.explanation}"
            )
        for publication in record.publications:
            lines.append(f"Related source: {publication.title} | {publication.url or publication.identifier or publication.doi or 'No link supplied'}")

    gaps = analysis.research_gaps
    lines.extend([
        "",
        "RESEARCH GAPS AND ASSUMPTIONS",
        f"Combined scenario status: {gaps.combined_scenario_status}",
        gaps.combined_scenario_explanation,
    ])
    for heading, items in (
        ("Supported parameters", gaps.supported_parameters),
        ("Partially supported parameters", gaps.partially_supported_parameters),
        ("Unsupported parameters", gaps.unsupported_parameters),
    ):
        lines.append(heading + ":")
        lines.extend(
            f"{item.parameter}={item.scenario_value}: {item.explanation}"
            for item in items
        )
    lines.extend(f"Assumption: {item}" for item in gaps.important_assumptions)

    citations = {}
    for citation in analysis.citations + details.supporting_citations:
        citations[citation.citation_id] = citation
    for specialist in analysis.specialist_analyses:
        for citation in specialist.citations:
            citations[citation.citation_id] = citation
    for record in analysis.evidence_matches:
        for citation in record.publications:
            citations[citation.citation_id] = citation
    lines.extend(["", "SOURCE CITATIONS"])
    if citations:
        for citation in citations.values():
            lines.append(
                f"{citation.title} | {citation.source} | status={citation.evidence_status} | "
                f"URL={citation.url or 'not supplied'} | DOI={citation.doi or 'not supplied'} | "
                f"identifier={citation.identifier or 'not supplied'}"
            )
    else:
        lines.append("No citations were supplied in the returned analysis.")

    lines.extend([
        "",
        "PROVENANCE LIMITATIONS",
        "A NASA source link establishes source linkage only; it does not independently verify experimental measurements.",
        "Publication metadata is not experimental measurement data. Related conditions do not establish that a combined scenario was tested.",
        "",
        "DISCLAIMER",
        analysis.disclaimer,
    ])
    return _pdf_from_lines(lines)


def build_experiment_comparison_report(
    comparison: ExperimentComparison,
    generated_at: datetime | None = None,
) -> bytes:
    """Render the currently selected, source-backed record comparison as a PDF."""
    timestamp = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    left = comparison.left
    right = comparison.right
    lines = [
        "FLAME INTELLIGENCE - EXPERIMENT COMPARISON REPORT",
        f"Experiment comparison: {left.title} vs {right.title}",
        f"Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "SOURCE RECORDS AND DOCUMENTED CONDITIONS",
    ]

    for label, record in (("Record A", left), ("Record B", right)):
        lines.extend([
            "",
            f"{label}: {record.title}",
            f"Source: {record.source_name} | record ID: {record.source_record_id}",
            f"Original source URL: {record.source_url or 'Not supplied'}",
            f"Record type: {record.record_kind}",
            f"Experiment type: {record.experiment_type or 'Unavailable'}",
            f"Experiment context: {record.experiment_context_type or 'Unavailable'}",
            f"Material: {record.material or 'Unavailable'}",
            f"Gravity: {record.gravity_environment or 'Unavailable'}",
            f"Environment: {record.environment or 'Unavailable'}",
            f"Evidence status: {record.evidence_status}",
            f"Provenance: {record.provenance_category}",
            "Source-recorded structured conditions:",
        ])
        if record.condition_values:
            lines.extend(f"{key}: {value}" for key, value in sorted(record.condition_values.items()))
        else:
            lines.append("No structured experimental conditions are available.")
        if record.missing_data:
            lines.append("Unavailable conditions: " + "; ".join(record.missing_data))
        if record.description:
            lines.append(f"Record description: {record.description}")
        lines.append("Source citations:")
        if record.citations:
            lines.extend(
                f"{citation.title} | {citation.evidence_type} | URL={citation.url or 'not supplied'}"
                f" | DOI={citation.doi or 'not supplied'} | identifier={citation.identifier or 'not supplied'}"
                for citation in record.citations
            )
        else:
            lines.append("No source citations were supplied with this record.")

    lines.extend(["", "DOCUMENTED COMPARISON DETAILS"])
    if comparison.categorical_comparisons:
        lines.append("Categorical comparisons:")
        lines.extend(
            f"{item.get('field', 'Field')}: {item.get('left_value') or 'Unavailable'} / "
            f"{item.get('right_value') or 'Unavailable'} ({item.get('relationship') or 'relationship unavailable'})"
            for item in comparison.categorical_comparisons
        )
    if comparison.quantitative_comparisons:
        lines.append("Quantitative comparisons from compatible source-recorded values:")
        lines.extend(
            f"{item.get('field', 'Field')}: {item.get('left_value')} / {item.get('right_value')} "
            f"{item.get('unit') or ''} ({item.get('relationship') or 'relationship unavailable'})"
            for item in comparison.quantitative_comparisons
        )
    if not comparison.categorical_comparisons and not comparison.quantitative_comparisons:
        lines.append("No shared structured conditions were available for comparison.")

    lines.extend([
        "",
        "RESEARCH GAPS, ASSUMPTIONS, AND UNCERTAINTY",
        "This report compares only fields explicitly present in the stored source records.",
        "Unavailable fields are not inferred from narrative text.",
        "No Mission Intelligence specialist analyses are attached to this record-only comparison.",
    ])
    lines.extend(f"Unavailable or unstructured field: {item}" for item in sorted(set(left.missing_data + right.missing_data)))
    lines.extend(f"Comparison limitation: {item}" for item in comparison.limitations)
    lines.extend([
        "",
        "PROVENANCE AND SCIENTIFIC LIMITATIONS",
        "A NASA source link establishes source linkage only; it does not independently verify experimental measurements.",
        "Publication metadata is not measurement data. A raw dataset file is not parsed measurement data.",
        "Comparing records does not show that their combined conditions were tested or establish scientific equivalence.",
        "",
        "DISCLAIMER",
        "Research reference only. This comparison is not a safety certification or operational recommendation.",
    ])
    return _pdf_from_lines(lines)


def _pdf_from_lines(lines: List[str]) -> bytes:
    page_lines = []
    for line in lines:
        normalized = unicodedata.normalize("NFKD", str(line)).encode("ascii", "ignore").decode("ascii")
        if not normalized:
            page_lines.append("")
            continue
        page_lines.extend(textwrap.wrap(normalized, width=92, break_long_words=True, break_on_hyphens=False) or [""])

    chunks = [page_lines[index:index + 54] for index in range(0, len(page_lines), 54)] or [[]]
    object_values = {}
    kids = []
    for index, chunk in enumerate(chunks):
        page_id = 4 + 2 * index
        content_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        content = ["BT", "/F1 9 Tf", "50 790 Td", "12 TL"]
        for line in chunk:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content.append(f"({escaped}) Tj")
            content.append("T*")
        content.append("ET")
        stream = "\n".join(content).encode("ascii")
        object_values[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        object_values[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )

    object_values[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    object_values[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode("ascii")
    object_values[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"

    output = bytearray(b"%PDF-1.4\n%FLAME\n")
    offsets = [0]
    for object_id in range(1, max(object_values) + 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(object_values[object_id])
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)
