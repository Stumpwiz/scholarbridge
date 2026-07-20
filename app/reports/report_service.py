from __future__ import annotations

import re
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from flask import current_app
from jinja2 import Environment, FileSystemLoader

from app.models import Campaign
from app.reports.registry import ReportDefinition

REPORT_FILENAME_PATTERN = re.compile(r"^[a-z0-9_]+_\d{4}\.pdf$")

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


class ReportGenerationError(RuntimeError):
    pass


def generated_reports_dir() -> Path:
    configured_path = current_app.config.get("GENERATED_REPORTS_DIR")
    if configured_path:
        directory = Path(str(configured_path))
    else:
        directory = Path(current_app.instance_path) / "generated_reports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def report_pdf_filename(report: ReportDefinition, campaign: Campaign) -> str:
    return report.build_filename(campaign)


def report_pdf_path(report: ReportDefinition, campaign: Campaign) -> Path:
    return generated_reports_dir() / report_pdf_filename(report, campaign)


def report_pdf_exists(report: ReportDefinition, campaign: Campaign) -> bool:
    return report_pdf_path(report, campaign).is_file()


def report_path_for_filename(filename: str) -> Path | None:
    if not REPORT_FILENAME_PATTERN.match(filename):
        return None
    return generated_reports_dir() / filename


def generate_report_pdf(report: ReportDefinition, campaign: Campaign) -> Path:
    if report.renderer_type != "latex_pdf":
        raise ReportGenerationError(f"Unsupported report renderer: {report.renderer_type}")

    context = report.build_context(campaign)
    context.setdefault("generated_date", _generated_date())

    pdf_path = report_pdf_path(report, campaign)
    tex_path = pdf_path.with_suffix(".tex")
    output_stem = pdf_path.stem

    rendered_tex = _render_latex_template(report.template_name, context)
    tex_path.write_text(rendered_tex, encoding="utf-8")

    _clean_auxiliary_files(output_stem)
    try:
        _run_xelatex(tex_path, passes=2)
    finally:
        _clean_auxiliary_files(output_stem, include_tex=True)

    if not pdf_path.is_file():
        raise ReportGenerationError(f"XeLaTeX completed but did not produce {pdf_path.name}.")

    return pdf_path


def _render_latex_template(template_name: str, context: dict) -> str:
    template_dir = Path(current_app.root_path) / "reports" / "templates"
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
    env.filters["latex"] = latex_escape
    env.filters["money"] = money
    return env.get_template(template_name).render(**context)


def _run_xelatex(tex_path: Path, passes: int = 2) -> None:
    output_dir = generated_reports_dir()
    command = [
        "xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory",
        str(output_dir),
        str(tex_path),
    ]

    for _ in range(passes):
        result = subprocess.run(
            command,
            cwd=Path(current_app.root_path).parent,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ReportGenerationError(
                "XeLaTeX failed while generating the report.\n\n"
                f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
            )


def _clean_auxiliary_files(output_stem: str, *, include_tex: bool = False) -> None:
    extensions = [".aux", ".log", ".out", ".synctex.gz"]
    if include_tex:
        extensions.append(".tex")

    directory = generated_reports_dir()
    for extension in extensions:
        path = directory / f"{output_stem}{extension}"
        if path.exists():
            path.unlink()


def latex_escape(value: object) -> str:
    if value is None:
        return ""
    return "".join(LATEX_REPLACEMENTS.get(char, char) for char in str(value))


def money(value: Decimal | int | float | str | None) -> str:
    if value is None:
        return "--"
    amount = Decimal(str(value))
    return rf"\${amount:,.0f}"


def _generated_date() -> str:
    try:
        return date.today().strftime("%B %-d, %Y")
    except ValueError:
        return datetime.now().strftime("%B %#d, %Y")
