"""The report for a lawyer and the inventory report (P25) and the obligations checklist (P24),
laid out as `aiact.export` papers.

Never imports `aiact.engine` or `aiact.drafting`: a report reads a result, it doesn't make one.
"""

from aiact.report.checklist import ChecklistDuty, ChecklistTool, checklist_report
from aiact.report.common import Name
from aiact.report.inventory import InventoryDuty, InventoryTool, inventory_report
from aiact.report.result import NoClassError, result_report

__all__ = [
    "ChecklistDuty",
    "ChecklistTool",
    "InventoryDuty",
    "InventoryTool",
    "Name",
    "NoClassError",
    "checklist_report",
    "inventory_report",
    "result_report",
]
