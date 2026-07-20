#!/usr/bin/env -S uv run python
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "app" / "reports" / "templates"
OUTPUT_DIR = REPO_ROOT / "docs" / "report_proofs" / "campaign_by_partner"
TEMPLATE_NAME = "campaign_by_partner.tex.j2"
OUTPUT_BASENAME = "campaign_by_partner_proof"


@dataclass(frozen=True)
class Campaign:
    campaign_year: int


@dataclass(frozen=True)
class ReportRow:
    partner_display_name: str
    status: str
    status_date: date | None
    amount_requested: Decimal | None
    amount_pledged: Decimal | None
    amount_received: Decimal | None

    @property
    def status_date_display(self) -> str | None:
        if self.status_date is None:
            return None
        return f"{self.status_date:%b} {self.status_date.day}"


LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(value: object) -> str:
    if value is None:
        return ""
    return "".join(LATEX_REPLACEMENTS.get(char, char) for char in str(value))


def money(value: Decimal | int | float | str | None) -> str:
    if value is None:
        return "--"
    amount = Decimal(str(value))
    return rf"\${amount:,.0f}"


def total_money(rows: list[ReportRow], field_name: str) -> Decimal:
    return sum(
        (getattr(row, field_name) or Decimal("0") for row in rows),
        Decimal("0"),
    )


def mock_rows() -> list[ReportRow]:
    return [
        ReportRow("Aster & Co.", "Not Contacted", None, Decimal("500"), None, None),
        ReportRow("Briarwood Partners", "Contacted", date(2026, 6, 3), Decimal("1000"), None, None),
        ReportRow("Caldwell Group", "Pledged", date(2026, 6, 6), Decimal("2500"), Decimal("1000"), None),
        ReportRow("Dunhill Associates", "Gift Received", date(2026, 6, 8), Decimal("5000"), Decimal("5000"), Decimal("5000")),
        ReportRow("Elm Street Collective", "Declined", date(2026, 6, 10), Decimal("750"), None, None),
        ReportRow("Fairview Partners", "Not Contacted", None, Decimal("10000"), None, None),
        ReportRow("Glenmore Group", "Contacted", None, Decimal("1500"), None, None),
        ReportRow("Harbor Point Associates", "Pledged", date(2026, 6, 12), Decimal("3000"), Decimal("1500"), Decimal("500")),
        ReportRow("Ivy Ridge Company", "Gift Received", date(2026, 6, 14), Decimal("1000"), Decimal("1000"), Decimal("1000")),
        ReportRow("Juniper Lane Partners", "Contacted", date(2026, 6, 15), Decimal("7500"), None, None),
        ReportRow("Keystone Circle", "Declined", date(2026, 6, 15), Decimal("500"), None, None),
        ReportRow("Larkspur Holdings", "Pledged", None, Decimal("2500"), Decimal("2500"), None),
        ReportRow("Monument Square Group", "Gift Received", date(2026, 6, 17), Decimal("10000"), Decimal("10000"), Decimal("10000")),
        ReportRow("Northgate Partners", "Not Contacted", None, Decimal("1250"), None, None),
        ReportRow("Oak Hill Collaborative", "Contacted", date(2026, 6, 19), Decimal("5000"), None, None),
        ReportRow("Pinecrest Alliance", "Pledged", date(2026, 6, 20), Decimal("3500"), Decimal("2000"), None),
        ReportRow("Quarry Run Group", "Gift Received", date(2026, 6, 22), Decimal("800"), Decimal("800"), Decimal("800")),
        ReportRow("Riverside Circle", "Declined", None, Decimal("600"), None, None),
        ReportRow("St. Bridget Wellness & Rehabilitation Center", "Pledged", date(2026, 6, 24), Decimal("10000"), Decimal("7500"), Decimal("2500")),
        ReportRow("The Very Long Name Foundation for Community Partnerships and Scholarship Support", "Contacted", date(2026, 6, 25), Decimal("10000"), None, None),
    ]


def render_template() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)
    env.filters["latex"] = latex_escape
    env.filters["money"] = money

    rows = mock_rows()
    template = env.get_template(TEMPLATE_NAME)
    rendered = template.render(
        campaign=Campaign(campaign_year=2026),
        generated_date=date(2026, 7, 18).strftime("%B %-d, %Y"),
        rows=rows,
        total_requested=total_money(rows, "amount_requested"),
        total_pledged=total_money(rows, "amount_pledged"),
        total_contributed=total_money(rows, "amount_received"),
    )

    tex_path = OUTPUT_DIR / f"{OUTPUT_BASENAME}.tex"
    tex_path.write_text(rendered, encoding="utf-8")
    return tex_path


def run_xelatex(tex_path: Path, passes: int = 2) -> None:
    command = [
        "xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory",
        str(OUTPUT_DIR),
        str(tex_path),
    ]
    for _ in range(passes):
        subprocess.run(command, cwd=REPO_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a developer-only PDF proof for campaign_by_partner.tex.j2."
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="Only render the .tex file; do not run XeLaTeX.",
    )
    args = parser.parse_args()

    tex_path = render_template()
    if not args.no_compile:
        run_xelatex(tex_path)

    print(f"Rendered TeX: {tex_path}")
    print(f"Proof PDF:    {OUTPUT_DIR / (OUTPUT_BASENAME + '.pdf')}")


if __name__ == "__main__":
    main()
