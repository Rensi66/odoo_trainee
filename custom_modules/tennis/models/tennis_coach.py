from datetime import datetime
from odoo import api, fields, models

import logging

_logger = logging.getLogger(__name__)


class TennisCoach(models.Model):
    _name = "tennis.coach"
    _description = "Tennis Coach"
    _inherits = {"hr.employee": "employee_id"}

    # Твои базовые поля...
    individual = fields.Monetary(string="Individual", required=True, default=100)
    group = fields.Monetary(string="Group", required=True, default=30)
    split = fields.Monetary(string="Split", required=True, default=50)
    work_phone = fields.Char(string="Телефон", related="employee_id.work_phone", readonly=True)
    work_email = fields.Char(string="Email", related="employee_id.work_email", readonly=True)
    avatar_image = fields.Binary(string="Фото", related="employee_id.image_1920", readonly=True)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade", string="Employee")
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    profit_for_center = fields.Monetary(string="Принес центру", compute="_compute_finance")

    _sql_constraints = [
        ("unique_employee_id", "UNIQUE(employee_id)", "This employee is already a coach")
    ]

    @api.onchange('center_id.date_from', 'center_id.date_to')
    def _compute_finance(self):
        for coach in self:
            center = coach.center_id
            if not center or not center.date_from or not center.date_to:
                coach.profit_for_center = 0.0
                continue

            day_start = datetime.combine(center.date_from, datetime.min.time())
            day_end = datetime.combine(center.date_to, datetime.max.time())

            trainings = self.env['tennis.training'].search([
                ('tennis_coach_id', '=', coach.id),
                ('center_id', '=', center.id),
                ('state', '=', 'done'),
                ('start_datetime', '>=', day_start),
                ('start_datetime', '<=', day_end),
            ])

            _logger.info("Для тренера %s (Employee ID: %s) найдено %s тренировок",
                         coach.name, coach.employee_id.id, len(trainings))

            coach.profit_for_center = sum(trainings.mapped('price_center'))

    @api.model
    def open_coach_form(self):
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        if is_manager:
            return {
                "name": "Open Coach",
                "type": "ir.actions.act_window",
                "res_model": "tennis.coach",
                "view_mode": "list,form",
                "target": "current",
            }
        elif not is_manager:
            coach = self.env["tennis.coach"].search([("employee_id", "=", self.env.user.employee_id.id)])

            return {
                "name": "Open Coach",
                "type": "ir.actions.act_window",
                "res_model": "tennis.coach",
                "res_id": coach.id if coach else False,
                "view_mode": "form",
                "target": "current",
            }
