from odoo import fields, models


class TennisUniversalReportWizard(models.TransientModel):
    _name = "tennis.universal.report.wizard"

    report_type = fields.Char(string="Report Type")
    date_from = fields.Date(string="Date from", required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string="Date to", required=True, default=fields.Date.today())

    center_ids = fields.Many2many("tennis.center", string="Sports Centers")


    def button_generate_report(self):
        """Generate the requested report based on report_type."""
        self.ensure_one()
        data = {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "center_ids": self.center_ids.ids if self.center_ids else self.env["tennis.center"].search([]).ids
        }

        report_type = self.report_type

        if report_type == "pnl":
            return self.env.ref("tennis.action_report_pnl_pdf").report_action(self, data=data)
        elif report_type == "payroll":
            return self.env.ref("tennis.action_report_payroll_pdf").report_action(self, data=data)
        elif report_type == "court_analysis":
            return self.env.ref("tennis.action_report_court_analysis_pdf").report_action(self, data=data)