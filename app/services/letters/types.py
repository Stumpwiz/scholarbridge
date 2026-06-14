from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.services.docx_template_service import DocxRenderPlan


@dataclass(frozen=True)
class LetterTemplate:
    key: str
    template_filename: str
    build_render_plan: Callable[[dict], DocxRenderPlan]

    def resolve_template_path(self, *, app_root_path: str) -> Path:
        project_root = Path(app_root_path).parent
        return project_root / "docs" / "private" / "letter_templates" / self.template_filename
