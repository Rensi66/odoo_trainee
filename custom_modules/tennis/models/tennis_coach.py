from datetime import datetime

import pytz

from odoo import api, fields, models


class TennisCoach(models.Model):
    _name = "tennis.coach"
    _description = "Tennis Coach"
    _inherits = {"hr.employee": "employee_id"}

    individual = fields.Monetary(string="Individual", required=True, default=100)
    group = fields.Monetary(string="Group", required=True, default=30)
    split = fields.Monetary(string="Split", required=True, default=50)
    work_phone = fields.Char(string="Phone", related="employee_id.work_phone", readonly=True)
    work_email = fields.Char(string="Email", related="employee_id.work_email", readonly=True)
    avatar_image = fields.Binary(string="Photo", related="employee_id.image_1920", readonly=True)
    profit_for_center = fields.Monetary(string="Brought to the center", compute="_compute_profit_for_center")

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", string="Employee")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)

    _sql_constraints = [
        ("unique_employee_id", "UNIQUE(employee_id)", "This employee is already a coach")
    ]

    @api.depends("center_id.date_from", "center_id.date_to")
    def _compute_profit_for_center(self):
        """Calculate the total profit brought to the center by the coach within the specified dates."""
        for coach_id in self:
            center_id = coach_id.center_id
            if not center_id or not center_id.date_from or not center_id.date_to:
                coach_id.profit_for_center = 0.0
                continue

            user_tz = self.env.user.tz or "UTC"
            local_tz = pytz.timezone(user_tz)
            day_start = datetime.combine(center_id.date_from, datetime.min.time())
            day_end = datetime.combine(center_id.date_to, datetime.max.time())
            localize_day_start = local_tz.localize(day_start)
            localize_day_end = local_tz.localize(day_end)
            utc_day_start = localize_day_start.astimezone(pytz.utc).replace(tzinfo=None)
            utc_day_end = localize_day_end.astimezone(pytz.utc).replace(tzinfo=None)

            training_ids = self.env["tennis.training"].search([
                ("tennis_coach_id", "=", coach_id.id),
                ("center_id", "=", center_id.id),
                ("state", "=", "done"),
                ("start_datetime", ">=", utc_day_start),
                ("start_datetime", "<=", utc_day_end),
            ])

            coach_id.profit_for_center = sum(training_ids.mapped("price_center"))

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        """Automatically assign the manager's tennis center to the coach upon employee selection."""
        if self.env.user.has_group("tennis.group_tennis_manager"):
            manager_center_id = self.env.user.employee_id.center_id.id
            if manager_center_id:
                self.center_id = manager_center_id

    @api.model
    def default_get(self, fields_list):
        """Set the default tennis center for new coaches based on the current manager's center."""
        res = super().default_get(fields_list=fields_list)

        manager_center_id = self.env.user.employee_id.center_id.id
        if manager_center_id:
            res["center_id"] = manager_center_id

        return res

    @api.model
    def action_open_coach_form(self):
        """Return an action window to open the coach form view or list view depending on access rights."""
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        if is_manager:
            return {
                "name": "Open Coach",
                "type": "ir.actions.act_window",
                "res_model": "tennis.coach",
                "view_mode": "list,form",
                "target": "current",
            }
        else:
            coach_id = self.env["tennis.coach"].search([("employee_id", "=", self.env.user.employee_id.id)], limit=1)

            return {
                "name": "Open Coach",
                "type": "ir.actions.act_window",
                "res_model": "tennis.coach",
                "res_id": coach_id.id if coach_id else False,
                "view_mode": "form",
                "target": "current",
            }