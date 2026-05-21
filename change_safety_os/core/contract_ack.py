from __future__ import annotations

from typing import Iterable, Optional

from change_safety_os.core.change_context import ChangeContext
from change_safety_os.core.report_writer import ReportWriter


def ack_contracts(context: ChangeContext, contract_names: Optional[Iterable[str]] = None, *, note: str = "") -> None:
    reviews = dict(context.state.get("contract_reviews") or {})
    if contract_names is None:
        names = list(reviews.keys())
    else:
        names = [str(name) for name in contract_names]
    for name in names:
        item = dict(reviews.get(name) or {})
        item["status"] = "reviewed"
        if note:
            item["note"] = note
        reviews[name] = item
    ReportWriter(context).update_state(contract_reviews=reviews)
