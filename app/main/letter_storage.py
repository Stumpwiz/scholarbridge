from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from flask import current_app

SOLICITATION_LETTER_PATTERN = re.compile(r"^solicitation_(\d+)\.pdf$")
MAILING_LIST_PATTERN = re.compile(r"^mailing_list_\d{8}_\d{6}_\d{6}\.txt$")


@dataclass(frozen=True)
class GeneratedSolicitationLetterFile:
    solicitation_id: int
    filename: str
    path: Path
    generated_at: datetime


@dataclass(frozen=True)
class GeneratedMailingListFile:
    filename: str
    path: Path
    created_at: datetime


def generated_solicitation_letters_dir() -> Path:
    configured_path = current_app.config.get("GENERATED_LETTERS_DIR")
    if configured_path:
        directory = Path(str(configured_path))
    else:
        directory = Path(current_app.instance_path) / "generated_letters" / "solicitations"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def generated_mailing_lists_dir() -> Path:
    configured_path = current_app.config.get("GENERATED_LETTERS_DIR")
    if configured_path:
        directory = Path(str(configured_path)) / "mailing_lists"
    else:
        directory = Path(current_app.instance_path) / "generated_letters" / "mailing_lists"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def solicitation_letter_filename(solicitation_id: int) -> str:
    return f"solicitation_{solicitation_id}.pdf"


def solicitation_letter_path(solicitation_id: int) -> Path:
    return generated_solicitation_letters_dir() / solicitation_letter_filename(solicitation_id)


def save_solicitation_letter_pdf(solicitation_id: int, pdf_bytes: bytes) -> Path:
    output_path = solicitation_letter_path(solicitation_id)
    output_path.write_bytes(pdf_bytes)
    return output_path


def list_generated_solicitation_letter_files() -> list[GeneratedSolicitationLetterFile]:
    files: list[GeneratedSolicitationLetterFile] = []
    directory = generated_solicitation_letters_dir()

    for path in directory.glob("solicitation_*.pdf"):
        if not path.is_file():
            continue
        match = SOLICITATION_LETTER_PATTERN.match(path.name)
        if not match:
            continue
        solicitation_id = int(match.group(1))
        generated_at = datetime.fromtimestamp(path.stat().st_mtime)
        files.append(
            GeneratedSolicitationLetterFile(
                solicitation_id=solicitation_id,
                filename=path.name,
                path=path,
                generated_at=generated_at,
            )
        )

    return sorted(files, key=lambda item: (item.generated_at, item.filename), reverse=True)


def save_generated_mailing_list(content: str) -> Path:
    directory = generated_mailing_lists_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = directory / f"mailing_list_{timestamp}.txt"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def mailing_list_path_for_filename(filename: str) -> Path | None:
    if not MAILING_LIST_PATTERN.match(filename):
        return None
    return generated_mailing_lists_dir() / filename


def list_generated_mailing_list_files() -> list[GeneratedMailingListFile]:
    files: list[GeneratedMailingListFile] = []
    directory = generated_mailing_lists_dir()

    for path in directory.glob("mailing_list_*.txt"):
        if not path.is_file():
            continue
        if not MAILING_LIST_PATTERN.match(path.name):
            continue
        created_at = datetime.fromtimestamp(path.stat().st_mtime)
        files.append(
            GeneratedMailingListFile(
                filename=path.name,
                path=path,
                created_at=created_at,
            )
        )

    return sorted(files, key=lambda item: (item.created_at, item.filename), reverse=True)
