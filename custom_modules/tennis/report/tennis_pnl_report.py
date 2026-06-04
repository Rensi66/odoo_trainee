from datetime import datetime
from odoo import api, fields, models


class ReportTennisPnL(models.AbstractModel):
    _name = "report.tennis.report_pnl_template"
    _description = "Report tennis PnL template"

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for the report."""
        date_from = data.get("date_from")
        date_to = data.get("date_to")

        day_start = datetime.combine(fields.Date.from_string(date_from), datetime.min.time())
        day_end = datetime.combine(fields.Date.from_string(date_to), datetime.max.time())

        centers = self.env["tennis.center"].browse(data.get("center_ids"))
        centers_pnl = []

        for center in centers:
            trainings = self.env["tennis.training"].search([
                ("center_id", "=", center.id),
                ("state", "=", "done"),
                ("start_datetime", ">=", day_start),
                ("start_datetime", "<=", day_end)
            ])

            gross = sum(trainings.mapped("price_total"))
            expenses = sum(trainings.mapped("price_coach"))
            net = sum(trainings.mapped("price_center"))

            centers_pnl.append({
                "name": center.name,
                "address": center.address,
                "trainings_count": len(trainings),
                "gross": gross,
                "expenses": expenses,
                "net": net,
            })

        return {
            "date_from": date_from,
            "date_to": date_to,
            "centers": centers_pnl,
            "total_gross": sum(c["gross"] for c in centers_pnl),
            "total_expenses": sum(c["expenses"] for c in centers_pnl),
            "total_net": sum(c["net"] for c in centers_pnl),
            "total_trainings": sum(c["trainings_count"] for c in centers_pnl),
        }