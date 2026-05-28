#!/usr/bin/env python3
"""
ScholarBridge Phase 0.5 Spreadsheet Analyzer
=============================================

Purpose:
- Explore legacy Excel data conservatively.
- Produce human-readable summaries for discovery and modeling.
- Avoid any mutation, cleaning, migration, or schema lock-in.

Important:
- This script is intentionally exploratory.
- It does not modify source spreadsheets.
- It does not write to databases.
- It does not build ORM or app code.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype


# Common token values that often represent "missing" in manually maintained spreadsheets.
MISSING_TOKENS = {
    "",
    "na",
    "n/a",
    "none",
    "null",
    "unknown",
    "-",
    "--",
}


# Column-name keyword maps used for broad field grouping.
CONTACT_KEYWORDS = {
    "contact",
    "first",
    "last",
    "name",
    "email",
    "phone",
    "mobile",
    "title",
}
PARTNER_KEYWORDS = {
    "partner",
    "org",
    "vendor",
    "company",
    "business",
    "institution",
}
CAMPAIGN_KEYWORDS = {
    "campaign",
    "cycle",
    "year",
    "solicit",
    "appeal",
    "donation",
    "gift",
    "pledge",
    "amount",
    "status",
}


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[\d\-\+\(\)\.\s]{7,}$")


@dataclass
class ColumnProfile:
    """Container for per-column profiling details used in markdown output."""

    name: str
    inferred_type: str
    non_null_count: int
    missing_count: int
    missing_pct: float
    unique_non_null: int
    suspicious_notes: list[str]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments with sensible project defaults."""
    parser = argparse.ArgumentParser(
        description="Analyze a legacy ScholarBridge spreadsheet without modifying data."
    )
    parser.add_argument(
        "spreadsheet",
        nargs="?",
        type=Path,
        help="Path to spreadsheet file. If omitted, script searches data/original/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/analysis"),
        help="Directory for markdown analysis reports.",
    )
    return parser.parse_args()


def find_default_spreadsheet() -> Path:
    """Pick the first spreadsheet found in data/original as a convenience fallback."""
    source_dir = Path("data/original")
    candidates = []
    for ext in ("*.xlsx", "*.xlsm", "*.xls"):
        candidates.extend(sorted(source_dir.glob(ext)))
    if not candidates:
        raise FileNotFoundError(
            "No spreadsheet found in data/original/. "
            "Copy the legacy Excel file there or pass a path explicitly."
        )
    return candidates[0]


def normalize_missing_markers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a normalized copy of the DataFrame where text missing markers are converted to NA.
    This improves consistency for exploratory missing-value checks.
    """
    normalized = df.copy()
    object_cols = normalized.select_dtypes(include=["object"]).columns
    for col in object_cols:
        # Normalize whitespace and known placeholder tokens in text columns only.
        series = normalized[col].astype("string").str.strip()
        lowered = series.str.lower()
        normalized[col] = series.mask(lowered.isin(MISSING_TOKENS), pd.NA)
    return normalized


def infer_type(series: pd.Series, column_name: str) -> str:
    """Infer a practical field type label for exploratory documentation."""
    if is_datetime64_any_dtype(series):
        return "datetime"
    if is_bool_dtype(series):
        return "boolean"
    if is_numeric_dtype(series):
        lowered = column_name.lower()
        if any(token in lowered for token in {"amount", "donation", "gift", "pledge", "total"}):
            return "currency_or_amount"
        return "numeric"

    # Text-only heuristics begin here.
    non_null = series.dropna().astype(str).str.strip()
    if non_null.empty:
        return "empty"

    email_ratio = non_null.str.match(EMAIL_RE, na=False).mean()
    if email_ratio >= 0.6:
        return "email_like"

    phone_ratio = non_null.str.match(PHONE_RE, na=False).mean()
    if phone_ratio >= 0.6:
        return "phone_like"

    parsed_dates = pd.to_datetime(non_null, errors="coerce")
    date_ratio = parsed_dates.notna().mean()
    if date_ratio >= 0.7:
        return "date_like_text"

    bool_tokens = {"yes", "no", "true", "false", "y", "n", "0", "1"}
    bool_ratio = non_null.str.lower().isin(bool_tokens).mean()
    if bool_ratio >= 0.8:
        return "boolean_like_text"

    unique_ratio = non_null.nunique(dropna=True) / max(len(non_null), 1)
    if unique_ratio <= 0.2:
        return "categorical_text"

    avg_len = non_null.str.len().mean()
    if avg_len > 80:
        return "long_text"

    return "text"


def suspicious_value_checks(series: pd.Series, inferred_type: str, column_name: str) -> list[str]:
    """Collect conservative suspicious-data indicators for human review."""
    notes: list[str] = []
    non_null = series.dropna()
    if non_null.empty:
        return notes

    as_text = non_null.astype(str)

    # Leading/trailing whitespace is a common quality issue in manually edited sheets.
    whitespace_issues = (as_text != as_text.str.strip()).sum()
    if whitespace_issues > 0:
        notes.append(f"{whitespace_issues} value(s) have leading/trailing whitespace")

    # Field-specific checks remain advisory and non-destructive.
    if inferred_type == "email_like":
        invalid = (~as_text.str.match(EMAIL_RE, na=False)).sum()
        if invalid > 0:
            notes.append(f"{invalid} email-like value(s) do not match a simple email format")

    if inferred_type == "phone_like":
        invalid = (~as_text.str.match(PHONE_RE, na=False)).sum()
        if invalid > 0:
            notes.append(f"{invalid} phone-like value(s) do not match basic phone patterns")

    lowered = column_name.lower()
    if any(token in lowered for token in {"amount", "gift", "donation", "pledge", "total"}):
        numeric_coerce = pd.to_numeric(as_text.str.replace(",", "", regex=False), errors="coerce")
        non_numeric = numeric_coerce.isna().sum()
        if non_numeric > 0:
            notes.append(f"{non_numeric} value(s) in amount-like column are non-numeric")

    if any(token in lowered for token in {"date", "sent", "received", "created", "updated"}):
        parsed = pd.to_datetime(as_text, errors="coerce")
        failed = parsed.isna().sum()
        if failed > 0:
            notes.append(f"{failed} value(s) in date-like column failed date parsing")

    return notes


def classify_column(column_name: str) -> set[str]:
    """Classify a column into one or more broad business groupings by keyword."""
    lowered = column_name.lower()
    labels: set[str] = set()
    if any(token in lowered for token in CONTACT_KEYWORDS):
        labels.add("contact")
    if any(token in lowered for token in PARTNER_KEYWORDS):
        labels.add("partner")
    if any(token in lowered for token in CAMPAIGN_KEYWORDS):
        labels.add("campaign")
    return labels


def profile_sheet(df: pd.DataFrame, sheet_name: str) -> dict[str, Any]:
    """Run sheet-level profiling and return structured results for console + markdown output."""
    normalized = normalize_missing_markers(df)
    row_count = len(normalized)
    col_count = len(normalized.columns)

    empty_columns = [col for col in normalized.columns if normalized[col].isna().all()]
    duplicate_rows = int(normalized.duplicated(keep=False).sum())

    missing_by_column: list[tuple[str, int, float]] = []
    profiles: list[ColumnProfile] = []
    type_counts: dict[str, int] = {}
    suspicious_columns: dict[str, list[str]] = {}

    for col in normalized.columns:
        series = normalized[col]
        missing_count = int(series.isna().sum())
        missing_pct = (missing_count / row_count * 100.0) if row_count else 0.0
        missing_by_column.append((col, missing_count, missing_pct))

        inferred = infer_type(series, col)
        type_counts[inferred] = type_counts.get(inferred, 0) + 1

        suspicious = suspicious_value_checks(series, inferred, col)
        if suspicious:
            suspicious_columns[col] = suspicious

        profiles.append(
            ColumnProfile(
                name=col,
                inferred_type=inferred,
                non_null_count=int(series.notna().sum()),
                missing_count=missing_count,
                missing_pct=missing_pct,
                unique_non_null=int(series.nunique(dropna=True)),
                suspicious_notes=suspicious,
            )
        )

    missing_by_column.sort(key=lambda item: item[1], reverse=True)
    top_missing = [item for item in missing_by_column if item[1] > 0][:10]

    # Candidate normalization signals:
    # 1) Any values that appear to contain multiple items in one cell.
    multi_value_columns = []
    for col in normalized.columns:
        series = normalized[col].dropna().astype(str)
        if series.empty:
            continue
        delimiter_ratio = series.str.contains(r"[;,/|]").mean()
        if delimiter_ratio >= 0.2:
            multi_value_columns.append(col)

    # 2) Columns with very low cardinality are often lookup/reference candidates.
    lookup_candidates = []
    for p in profiles:
        if p.non_null_count == 0:
            continue
        if p.unique_non_null <= 10 and (p.unique_non_null / max(p.non_null_count, 1)) <= 0.2:
            lookup_candidates.append(p.name)

    return {
        "sheet_name": sheet_name,
        "row_count": row_count,
        "col_count": col_count,
        "columns": [str(c) for c in normalized.columns.tolist()],
        "empty_columns": empty_columns,
        "duplicate_rows": duplicate_rows,
        "top_missing": top_missing,
        "type_counts": type_counts,
        "profiles": profiles,
        "suspicious_columns": suspicious_columns,
        "multi_value_columns": multi_value_columns,
        "lookup_candidates": lookup_candidates,
    }


def build_markdown_report(
    workbook_path: Path, sheet_results: list[dict[str, Any]], generated_at: str
) -> str:
    """Assemble a single markdown report for maintainers and future assistants."""
    all_columns: list[str] = []
    shared_columns_counter: dict[str, int] = {}
    inferred_groups: dict[str, set[str]] = {"contact": set(), "partner": set(), "campaign": set()}
    suspicious_rollup: list[str] = []
    normalization_rollup: list[str] = []

    for result in sheet_results:
        for col in result["columns"]:
            all_columns.append(col)
            shared_columns_counter[col] = shared_columns_counter.get(col, 0) + 1
            for label in classify_column(col):
                inferred_groups[label].add(col)

        if result["multi_value_columns"]:
            normalization_rollup.append(
                f"- `{result['sheet_name']}` has possible multi-value columns: "
                + ", ".join(f"`{c}`" for c in result["multi_value_columns"])
            )
        if result["lookup_candidates"]:
            normalization_rollup.append(
                f"- `{result['sheet_name']}` has possible lookup/reference fields: "
                + ", ".join(f"`{c}`" for c in result["lookup_candidates"])
            )
        if result["duplicate_rows"] > 0:
            normalization_rollup.append(
                f"- `{result['sheet_name']}` includes {result['duplicate_rows']} likely duplicate row(s)."
            )

        for col, notes in result["suspicious_columns"].items():
            for note in notes:
                suspicious_rollup.append(f"- `{result['sheet_name']}.{col}`: {note}")

    shared_columns = sorted([col for col, count in shared_columns_counter.items() if count > 1])
    if shared_columns:
        normalization_rollup.append(
            "- Shared column names across sheets (potential key/reference alignment): "
            + ", ".join(f"`{c}`" for c in shared_columns)
        )

    report_lines: list[str] = [
        "# Spreadsheet Analysis Report",
        "",
        f"- Workbook: `{workbook_path}`",
        f"- Generated: `{generated_at}`",
        "",
        "## Scope",
        "",
        "This report is exploratory and non-destructive. It supports data understanding only.",
        "",
        "## Inferred Entities (Heuristic)",
        "",
        "- Contact-related fields: "
        + (", ".join(f"`{c}`" for c in sorted(inferred_groups["contact"])) or "none detected"),
        "- Partner-related fields: "
        + (", ".join(f"`{c}`" for c in sorted(inferred_groups["partner"])) or "none detected"),
        "- Campaign-cycle-related fields: "
        + (", ".join(f"`{c}`" for c in sorted(inferred_groups["campaign"])) or "none detected"),
        "",
        "## Candidate Normalization Opportunities",
        "",
    ]

    if normalization_rollup:
        report_lines.extend(normalization_rollup)
    else:
        report_lines.append("- No clear normalization signals detected from current heuristics.")

    report_lines.extend(
        [
            "",
            "## Suspicious or Inconsistent Values",
            "",
        ]
    )
    if suspicious_rollup:
        report_lines.extend(suspicious_rollup)
    else:
        report_lines.append("- No suspicious-value signals detected by current checks.")

    report_lines.extend(["", "## Worksheet Profiles", ""])

    for result in sheet_results:
        report_lines.extend(
            [
                f"### {result['sheet_name']}",
                "",
                f"- Row count: **{result['row_count']}**",
                f"- Column count: **{result['col_count']}**",
                f"- Likely duplicate rows: **{result['duplicate_rows']}**",
                "- Empty columns: "
                + (", ".join(f"`{c}`" for c in result["empty_columns"]) if result["empty_columns"] else "none"),
                "",
                "**Inferred field types (column counts):**",
            ]
        )
        for field_type, count in sorted(result["type_counts"].items()):
            report_lines.append(f"- `{field_type}`: {count}")

        report_lines.extend(["", "**Columns (quick profile):**", ""])
        report_lines.append(
            "| Column | Inferred Type | Non-Null | Missing | Missing % | Unique (Non-Null) |"
        )
        report_lines.append("|---|---:|---:|---:|---:|---:|")
        for p in result["profiles"]:
            report_lines.append(
                f"| `{p.name}` | `{p.inferred_type}` | {p.non_null_count} | "
                f"{p.missing_count} | {p.missing_pct:.2f}% | {p.unique_non_null} |"
            )

        report_lines.extend(["", "**Top missing-value columns:**"])
        if result["top_missing"]:
            for col, miss_count, miss_pct in result["top_missing"]:
                report_lines.append(f"- `{col}`: {miss_count} missing ({miss_pct:.2f}%)")
        else:
            report_lines.append("- none")

        report_lines.append("")

    return "\n".join(report_lines).strip() + "\n"


def print_console_summary(workbook_path: Path, sheet_results: list[dict[str, Any]]) -> None:
    """Emit concise, console-friendly profiling output for immediate review."""
    print(f"\n=== ScholarBridge Spreadsheet Analysis ===")
    print(f"Workbook: {workbook_path}")
    print(f"Worksheets discovered: {len(sheet_results)}")
    print("------------------------------------------")

    for result in sheet_results:
        print(f"\nSheet: {result['sheet_name']}")
        print(f"- Rows: {result['row_count']}")
        print(f"- Columns: {result['col_count']}")
        print(f"- Duplicate rows (likely): {result['duplicate_rows']}")
        print(f"- Empty columns: {', '.join(result['empty_columns']) if result['empty_columns'] else 'none'}")
        print("- Column names:")
        for col in result["columns"]:
            print(f"  - {col}")
        print("- Inferred field types:")
        for field_type, count in sorted(result["type_counts"].items()):
            print(f"  - {field_type}: {count}")
        if result["top_missing"]:
            print("- Top missing-value columns:")
            for col, miss_count, miss_pct in result["top_missing"]:
                print(f"  - {col}: {miss_count} ({miss_pct:.2f}%)")
        else:
            print("- Top missing-value columns: none")


def main() -> None:
    """Main script entrypoint."""
    args = parse_args()
    workbook_path = args.spreadsheet if args.spreadsheet else find_default_spreadsheet()
    workbook_path = workbook_path.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not workbook_path.exists():
        raise FileNotFoundError(f"Spreadsheet not found: {workbook_path}")

    # Read workbook metadata first so we can enumerate worksheets clearly.
    excel_file = pd.ExcelFile(workbook_path)
    sheet_names = excel_file.sheet_names

    sheet_results: list[dict[str, Any]] = []
    for sheet_name in sheet_names:
        # dtype=object keeps original values as-is for conservative profiling.
        df = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object)
        result = profile_sheet(df, sheet_name)
        sheet_results.append(result)

    # Console output supports quick iterative exploration.
    print_console_summary(workbook_path, sheet_results)

    # Markdown output supports durable handoff and decision-making.
    generated_at = datetime.now().isoformat(timespec="seconds")
    report_text = build_markdown_report(workbook_path, sheet_results, generated_at)
    report_filename = f"{workbook_path.stem}_analysis.md"
    report_path = output_dir / report_filename
    report_path.write_text(report_text, encoding="utf-8")

    # Keep a stable path for quick reference in future sessions.
    latest_path = output_dir / "latest_analysis.md"
    latest_path.write_text(report_text, encoding="utf-8")

    print("\nReport written:")
    print(f"- {report_path}")
    print(f"- {latest_path}")


if __name__ == "__main__":
    main()
