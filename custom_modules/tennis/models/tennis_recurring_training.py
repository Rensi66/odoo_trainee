from datetime import datetime, timedelta, time

import pytz

from odoo import api, fields, models


class TennisRecurringTraining(models.TransientModel):
    _name = "tennis.recurring.training"
    _description = "Tennis Recurring Training Wizard"

    mo = fields.Boolean(string="Monday", default=False)
    mo_time = fields.Float(string="Monday Time", default=0.0)
    tu = fields.Boolean(string="Tuesday", default=False)
    tu_time = fields.Float(string="Tuesday Time", default=0.0)
    wen = fields.Boolean(string="Wednesday", default=False)
    wen_time = fields.Float(string="Wednesday Time", default=0.0)
    th = fields.Boolean(string="Thursday", default=False)
    th_time = fields.Float(string="Thursday Time", default=0.0)
    fr = fields.Boolean(string="Friday", default=False)
    fr_time = fields.Float(string="Friday Time", default=0.0)
    sat = fields.Boolean(string="Saturday", default=False)
    sat_time = fields.Float(string="Saturday Time", default=0.0)
    sun = fields.Boolean(string="Sunday", default=False)
    sun_time = fields.Float(string="Sunday Time", default=0.0)

    name = fields.Char(string="Training name")
    duration = fields.Integer(string="Duration", required=True, default=1)
    training_type = fields.Selection([
        ("individual", "Individual"),
        ("split", "Split"),
        ("group", "Group"),
    ], required=True, default="group", string="Training Type")
    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)
    is_owner = fields.Boolean(required=True, default=False)
    is_manager = fields.Boolean(required=True, default=False)

    center_id = fields.Many2one("tennis.center", string="Center", required=True, default=lambda self: self.env.user.employee_id.center_id)
    tennis_coach_id = fields.Many2one("tennis.coach", string="Coach", required=True)
    court = fields.Selection(string="Court", selection="_get_court_selection")
    client_id = fields.Many2one("res.partner", string="Clients")

    @api.model
    def default_get(self, fields_list):
        """Set the default configuration for the recurring training wizard."""
        res = super().default_get(fields_list)
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")
        res["is_owner"] = is_owner
        res["is_manager"] = is_manager

        if is_coach and not (is_manager or is_owner):
            coach = self.env["tennis.coach"].search([("user_id", "=", self.env.user.id)], limit=1)
            res["tennis_coach_id"] = coach.id

        return res

    @api.model
    def _get_court_selection(self):
        """Return a selection list of available courts for the current center."""
        center_id = self.env.user.employee_id.center_id
        if center_id:
            if center_id.court > 0:
                return [(f"court_{i}", f"Court {i}") for i in range(1, center_id.court + 1)]

        return [("default_court", "Court 1")]

    def button_generate_series(self):
        """Generate a series of training sessions based on the selected weekly schedule."""
        for recurring_id in self:
            days_of_the_week = {"mo": 0, "tu": 1, "wen": 2, "th": 3, "fr": 4, "sat": 5, "sun": 6}
            time_of_the_week = {0: "mo_time", 1: "tu_time", 2: "wen_time", 3: "th_time", 4: "fr_time", 5: "sat_time", 6: "sun_time"}
            training_days = [value for day, value in days_of_the_week.items() if getattr(recurring_id, day)]

            created_training_ids = self.env["tennis.training"]

            end_date = recurring_id.date_to
            current_date = recurring_id.date_from
            if training_days:
                while current_date <= end_date:
                    if current_date.weekday() in training_days:
                        field_name = time_of_the_week[current_date.weekday()]
                        float_time = getattr(recurring_id, field_name)

                        hours = int(float_time)
                        minutes = int(round((float_time - hours) * 60))

                        local_datetime = datetime.combine(current_date, time(hours, minutes))
                        user_tz = self.env.user.tz or "UTC"
                        local_tz = pytz.timezone(user_tz)

                        local_datetime = local_tz.localize(local_datetime)
                        utc_datetime = local_datetime.astimezone(pytz.utc)
                        training_start = utc_datetime.replace(tzinfo=None)

                        new_training_id = self.env["tennis.training"].create({
                            "name": recurring_id.name,
                            "center_id": recurring_id.center_id.id,
                            "court": recurring_id.court,
                            "tennis_coach_id": recurring_id.tennis_coach_id.id,
                            "client_ids": [(4, recurring_id.client_id.id)] if recurring_id.client_id else False,
                            "training_type": recurring_id.training_type,
                            "duration": recurring_id.duration,
                            "start_datetime": training_start
                        })

                        created_training_ids |= new_training_id

                    current_date += timedelta(days=1)

            if created_training_ids:
                for training_id in created_training_ids:
                    training_id.button_confirm()

        return {
            "name": "Trainings",
            "type": "ir.actions.act_window",
            "res_model": "tennis.training",
            "view_mode": "calendar,list,form",
            "target": "current",
        }