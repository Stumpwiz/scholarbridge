from __future__ import annotations

from datetime import date

from app.main.solicitation_status import (
    canonical_solicitation_status,
    solicitation_status_for_storage,
)
from app.models import Solicitation


class SolicitationWorkflowService:
    @staticmethod
    def update_status(solicitation: Solicitation, status: str | None) -> bool:
        new_status = solicitation_status_for_storage(status)
        if new_status == solicitation.status:
            return False

        solicitation.status = new_status
        solicitation.status_date = date.today()
        return True

    @staticmethod
    def can_edit_solicitation_letter(solicitation: Solicitation) -> bool:
        return canonical_solicitation_status(solicitation.status) == "not_contacted"
