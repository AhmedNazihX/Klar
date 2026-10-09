"""The report for a lawyer and the inventory report (P25), laid out as `aiact.export` papers.

Never imports `aiact.engine` or `aiact.drafting`: a report reads a result, it doesn't make one.
"""

from aiact.report.inventory import InventoryDuty, InventoryTool, inventory_report
from aiact.report.result import NoClassError, report_id, result_report

__all__ = [
    "InventoryDuty",
    "InventoryTool",
    "NoClassError",
    "inventory_report",
    "report_id",
    "result_report",
]
