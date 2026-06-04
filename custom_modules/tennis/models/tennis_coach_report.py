import calendar
from datetime import datetime, time

import pytz

from odoo import api, fields, models, tools


class TennisCoachReport(models.Model):
    _name = "tennis.coach.report"
    _description = "Tennis Coach Report"
    _auto = False

    month = fields.Date(string="Month", readonly=True)
    total_hours = fields.Integer(string="Total Hours", readonly=True)
    total_salary = fields.Monetary(string="Total Salary", readonly=True, currency_field="currency_id")
    total_trainings = fields.Integer(string="Total Trainings", readonly=True)

    tennis_coach_id = fields.Many2one("tennis.coach", string="Coach", required=True)
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)

    def init(self):
        """Initialize the PostgreSQL view for the coach report."""
        tools.drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute(f"""
        CREATE OR REPLACE VIEW {self._table} AS (
            SELECT 
                ROW_NUMBER() OVER() AS id,
                t.tennis_coach_id AS tennis_coach_id,
                DATE_TRUNC('month', t.start_datetime)::date as month,
                COUNT(t.id) AS total_trainings,
                SUM(duration) AS total_hours,
                COALESCE(SUM(t.price_coach), 0) as total_salary,
                (SELECT currency_id FROM res_company WHERE id = 1) AS currency_id

            FROM tennis_training t
            WHERE t.state = 'done'
            GROUP BY t.tennis_coach_id,
                    DATE_TRUNC('month', t.start_datetime)::date)
            """)

    @api.model
    def get_dashboard_data(self):
        """Fetch KPI, today's schedule, and monthly chart statistics for the coach dashboard."""
        user_id = self.env.user
        coach_id = self.env["tennis.coach"].search([("user_id", "=", user_id.id)], limit=1)

        if not coach_id:
            return {
                "coach_name": user_id.name,
                "kpi": {"total_trainings": 0, "total_hours": 0, "total_salary_formatted": "0 $"},
                "today_trainings": [],
                "chart_data": {"labels": [], "values": []}
            }

        user_tz_string = coach_id.user_id.tz or self.env.user.tz or "UTC"
        local_tz = pytz.timezone(user_tz_string)
        today_local = datetime.now(local_tz).date()

        current_date = today_local

        # KPI calculation
        m_start = local_tz.localize(datetime.combine(current_date.replace(day=1), time.min)).astimezone(pytz.utc)
        _, last_d = calendar.monthrange(current_date.year, current_date.month)
        m_end = local_tz.localize(datetime.combine(current_date.replace(day=last_d), time.max)).astimezone(pytz.utc)

        training_this_month_ids = self.env["tennis.training"].search([
            ("tennis_coach_id", "=", coach_id.id),
            ("state", "=", "done"),
            ("start_datetime", ">=", fields.Datetime.to_string(m_start)),
            ("start_datetime", "<=", fields.Datetime.to_string(m_end))
        ])

        total_trainings = len(training_this_month_ids)
        total_hours = int(sum(training_this_month_ids.mapped("duration")))
        salary = sum(training_this_month_ids.mapped("price_coach"))
        salary_formatted = f"{salary:,.0f} $".replace(",", " ")

        # Today trainings calculation
        local_start = datetime.combine(today_local, time.min)
        local_end = datetime.combine(today_local, time.max)
        start_utc = local_tz.localize(local_start).astimezone(pytz.utc)
        end_utc = local_tz.localize(local_end).astimezone(pytz.utc)

        training_today_ids = self.env["tennis.training"].search([
            ("tennis_coach_id", "=", coach_id.id),
            ("start_datetime", ">=", fields.Datetime.to_string(start_utc)),
            ("start_datetime", "<=", fields.Datetime.to_string(end_utc)),
            ("state", "in", ["confirmed", "in_progress", "done", "cancel"]),
        ], order="start_datetime asc")

        status_mapping = {
            "confirmed": {"label": "Confirmed", "class": "text-primary",
                          "style": "background-color: #e0f2fe; color: #0369a1 !important;"},
            "in_progress": {"label": "In progress", "class": "text-warning fw-bold",
                            "style": "background-color: #fef3c7; color: #b45309 !important;"},
            "done": {"label": "Done ✓", "class": "text-success",
                     "style": "background-color: #dcfce7; color: #15803d !important;"},
            "cancel": {"label": "Canceled ✕", "class": "text-danger",
                       "style": "background-color: #fee2e2; color: #b91c1c !important;"},
        }

        today_list = []
        for training_id in training_today_ids:
            local_time = fields.Datetime.context_timestamp(self, training_id.start_datetime).strftime("%H:%M")
            status_info = status_mapping.get(training_id.state,
                                             {"label": training_id.state, "class": "bg-light text-dark"})
            type_label = dict(training_id._fields["training_type"]._description_selection(self.env)).get(
                training_id.training_type,
                training_id.training_type)
            court_label = dict(training_id._fields["court"]._description_selection(self.env)).get(training_id.court,
                                                                                                  training_id.court)

            client_level = "Beginner"
            if training_id.client_ids and "client_level" in training_id.client_ids._fields:
                client_id = training_id.client_ids[0]
                client_level = client_id.client_level

            today_list.append({
                "id": training_id.id,
                "time": local_time,
                "client_name": training_id.display_clients or "Individual client",
                "court_name": f"Court: {court_label}",
                "client_level": client_level,
                "is_group": training_id.training_type == "group",
                "type_label": type_label,
                "status_label": status_info["label"],
                "status_class": status_info["class"],
                "status_style": status_info.get("style", "")
            })

        # Chart analytics calculation
        _, last_day = calendar.monthrange(today_local.year, today_local.month)

        month_start_utc = local_tz.localize(datetime.combine(today_local.replace(day=1), time.min)).astimezone(pytz.utc)
        month_end_utc = local_tz.localize(datetime.combine(today_local.replace(day=last_day), time.max)).astimezone(
            pytz.utc)

        monthly_training_ids = self.env["tennis.training"].search([
            ("tennis_coach_id", "=", coach_id.id),
            ("state", "=", "done"),
            ("start_datetime", ">=", fields.Datetime.to_string(month_start_utc)),
            ("start_datetime", "<=", fields.Datetime.to_string(month_end_utc))
        ])

        daily_earnings = {}
        for training_id in monthly_training_ids:
            t_naive = fields.Datetime.from_string(training_id.start_datetime)
            t_local = pytz.utc.localize(t_naive).astimezone(local_tz)
            day_num = t_local.day
            daily_earnings[day_num] = daily_earnings.get(day_num, 0.0) + float(training_id.price_coach)

        chart_labels = []
        chart_values = []
        for day in range(1, today_local.day + 1):
            chart_labels.append(f"{day:02d}")
            chart_values.append(daily_earnings.get(day, 0.0))

        return {
            "coach_name": coach_id.name,
            "kpi": {
                "total_trainings": total_trainings,
                "total_hours": total_hours,
                "total_salary_formatted": salary_formatted
            },
            "today_trainings": today_list,
            "chart_data": {
                "labels": chart_labels,
                "values": chart_values
            }
        }