from datetime import datetime, timedelta, time
import pytz

from odoo import api, fields, models


class TennisRecurringTraining(models.TransientModel):
    _name = "tennis.recurring.training"

    mo = fields.Boolean(string="Monday", default=False)
    mo_time = fields.Float()
    tu = fields.Boolean(string="Tuesday", default=False)
    tu_time = fields.Float()
    wen = fields.Boolean(string="Wednesday", default=False)
    wen_time = fields.Float()
    th = fields.Boolean(string="Thursday", default=False)
    th_time = fields.Float()
    fr = fields.Boolean(string="Friday", default=False)
    fr_time = fields.Float()
    sat = fields.Boolean(string="Saturday", default=False)
    sat_time = fields.Float()
    sun = fields.Boolean(string="Sunday", default=False)
    sun_time = fields.Float()

    name = fields.Char(string="Training name")
    duration = fields.Integer(string="Duration", required=True, default=1)
    training_type = fields.Selection([
        ("individual", "Individual"),
        ("split", "Split"),
        ("group", "Group"),
    ], required=True, default='group', string="Training Type")
    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)

    center_id = fields.Many2one("tennis.center", string="Center", required=True, readonly=True, default=lambda self: self.env.user.employee_id.center_id)
    tennis_coach_id = fields.Many2one("tennis.coach", string="Coach", required=True)
    court = fields.Selection(string="Court", selection="_get_court_selection")
    client_id = fields.Many2one("res.partner", string="Clients")

    @api.model
    def _get_court_selection(self):
        center_id = self.env.user.employee_id.center_id.id
        if center_id:
            center = self.env["tennis.center"].browse(center_id)
            if center.court > 0:
                return [(f"court_{i}", f"Court {i}") for i in range(1, center.court + 1)]

        return [(f"default_court", f"Court 1")]

    def action_generate_series(self):
        for record in self:
            days_of_the_week = {"mo": 0, "tu": 1, "wen": 2, "th": 3, "fr": 4, "sat": 5, "sun": 6}
            time_of_the_week = {0: "mo_time", 1: "tu_time", 2: "wen_time", 3: "th_time", 4: "fr_time", 5: "sat_time", 6: "sun_time"}
            training_days = [value for day, value in days_of_the_week.items() if getattr(record, day)]

            created_trainings = self.env["tennis.training"]

            end_date = record.date_to
            current_date = record.date_from
            if training_days:
                while current_date <= end_date:
                    if current_date.weekday() in training_days:
                        field_name = time_of_the_week[current_date.weekday()]
                        float_time = getattr(record, field_name)

                        hours = int(float_time)
                        minutes = int(round((float_time - hours) * 60))

                        local_datetime = datetime.combine(current_date, time(hours, minutes))
                        user_tz = self.env.user.tz or 'UTC'
                        local_tz = pytz.timezone(user_tz)

                        local_datetime = local_tz.localize(local_datetime)
                        utc_datetime = local_datetime.astimezone(pytz.utc)
                        training_start = utc_datetime.replace(tzinfo=None)

                        new_training = self.env["tennis.training"].create(
                                            {"name": record.name,
                                            "center_id": record.center_id.id,
                                            "court": record.court,
                                            "tennis_coach_id": record.tennis_coach_id.id,
                                            "client_ids": [(4, record.client_id.id)] if record.client_id else False,
                                            "training_type": record.training_type,
                                            "duration": record.duration,
                                            "start_datetime": training_start})

                        created_trainings |= new_training

                    current_date += timedelta(days=1)

            if created_trainings:
                for training in created_trainings:
                    training.action_confirm()

        return {
            "name": "Trainings",
            "type": "ir.actions.act_window",
            "res_model": "tennis.training",
            "view_mode": "calendar,list,form",
            "target": "current",
        }