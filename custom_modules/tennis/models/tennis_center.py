import calendar
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError


class TennisCenter(models.Model):
    _name = "tennis.center"
    _description = "Tennis Center"

    name = fields.Char(string="Name", required=True)
    address = fields.Char(string="Address", required=True)
    court = fields.Integer(string="Number of courts", default=1, required=True)
    individual = fields.Monetary(string="Individual", default=100.0, required=True)
    split = fields.Monetary(string="Split", default=50.0, required=True)
    group = fields.Monetary(string="Group", default=30.0, required=True)
    start_time = fields.Float(string="Start Time", required=True)
    end_time = fields.Float(string="End Time", required=True)
    tz = fields.Selection(_tz_get, string="Time Zone", default=lambda self: self.env.user.tz or "UTC", required=True)

    # Filter
    date_from = fields.Date(string="Profit from", default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string="Profit to", default=lambda self: fields.Date.today())

    # Training analytics
    stat_individual_count = fields.Integer(string="Individual (quantity)", readonly=True)
    stat_individual_profit = fields.Monetary(string="Individual (revenue)", readonly=True)
    stat_split_count = fields.Integer(string="Splits (quantity)", readonly=True)
    stat_split_profit = fields.Monetary(string="Splits (revenue)", readonly=True)
    stat_group_count = fields.Integer(string="Group (quantity)", readonly=True)
    stat_group_profit = fields.Monetary(string="Group (revenue)", readonly=True)
    most_popular_training_type = fields.Char(string="Most popular type", readonly=True)

    # Client analytics
    stat_clients_count = fields.Integer(string="Unique clients (quantity)", readonly=True)
    stat_visits_count = fields.Integer(string="Total visits (quantity)", readonly=True)
    client_activity_html = fields.Html(string="Detailing by clients", readonly=True)

    total_center_profit = fields.Monetary(string="Profit center", compute="_compute_center_profit",
                                          currency_field="currency_id")

    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    owner_id = fields.Many2one("res.users", string="Owner", required=True, default=lambda self: self.env.user,
                               ondelete="cascade", readonly=True)
    manager_id = fields.Many2one("hr.employee", string="Manager", required=False, ondelete="set null")
    tennis_coach_ids = fields.One2many("tennis.coach", "center_id", string="Coaches", required=False)

    _sql_constraints = [
        ("unique_manager_id", "UNIQUE(manager_id)",
         "There is already another manager at this center, or this employee is already the manager of another center."),
    ]

    @api.depends("tennis_coach_ids.profit_for_center")
    def _compute_center_profit(self):
        """Calculate the total profit accumulated across all coaches linked to the center."""
        for center_id in self:
            center_id.total_center_profit = sum(center_id.tennis_coach_ids.mapped("profit_for_center"))

    @api.constrains("manager_id")
    def _check_unique_manager(self):
        """Ensure that an employee is not assigned as a manager to multiple centers."""
        for center_id in self:
            if center_id.manager_id:
                duplicate_id = self.search([
                    ("manager_id", "=", center_id.manager_id.id),
                    ("id", "!=", center_id.id)
                ], limit=1)

                if duplicate_id:
                    raise ValidationError(
                        "This employee is already the manager of another tennis center! "
                        "Choose someone else."
                    )

    @api.constrains("court")
    def _check_count_of_court(self):
        """Validate that the center has at least one tennis court available."""
        for center_id in self:
            if center_id.court < 1:
                raise ValidationError("Court cannot be less than 1.")

    @api.model
    def get_manager_dashboard_data(self, center_id=None):
        """Fetch and compile real-time metrics, occupancy, and financial data for the manager dashboard."""
        user_id = self.env.user
        center_ids = []

        if user_id.has_group("tennis.group_tennis_owner"):
            center_ids = user_id.center_ids.ids
        elif user_id.has_group("tennis.group_tennis_manager"):
            center_ids = self.env["tennis.center"].search_fetch([("manager_id", "=", user_id.employee_id.id)],
                                                                field_names=["id"]).ids

        if not center_ids:
            return {
                "metrics": {"approvals": 0, "occupancy": "0%", "new_clients": 0, "revenue": "0 $"},
                "debtors": [],
                "today_trainings": []
            }

        # Approvals
        approvals_count = self.env["tennis.training"].search_count([
            ("center_id", "in", center_ids),
            ("state", "in", ["draft", "to_approve", "to_approve_cancel"])
        ])

        # Occupancy percent
        user_tz = user_id.tz or "UTC"
        local_tz = pytz.timezone(user_tz)
        local_now = datetime.now(local_tz)
        local_date = local_now.date()

        day_start_local = datetime.combine(local_date, datetime.min.time())
        day_end_local = datetime.combine(local_date, datetime.max.time())

        day_start_utc = local_tz.localize(day_start_local).astimezone(pytz.utc).replace(tzinfo=None)
        day_end_utc = local_tz.localize(day_end_local).astimezone(pytz.utc).replace(tzinfo=None)

        total_capacity_hours = 0
        for center_id in self.env["tennis.center"].browse(center_ids):
            working_hours = (center_id.end_time if center_id.end_time != 0 else 24) - center_id.start_time
            total_capacity_hours += (working_hours if working_hours > 0 else 12) * center_id.court

        training_today_ids = self.env["tennis.training"].search([
            ("center_id", "in", center_ids),
            ("start_datetime", ">=", day_start_utc),
            ("start_datetime", "<=", day_end_utc),
            ("state", "in", ["confirmed", "in_progress", "done", "to_approve_cancel"])
        ])

        booked_hours = sum(training_today_ids.mapped("duration"))
        occupancy_pct = int((booked_hours / total_capacity_hours) * 100) if total_capacity_hours > 0 else 0

        # Today's trainings
        today_trainings_data = []
        state_labels = dict(self.env["tennis.training"]._fields["state"].selection)
        state_classes = {
            "confirmed": "bg-primary", "in_progress": "bg-info text-dark",
            "done": "bg-success", "to_approve_cancel": "bg-warning text-dark"
        }

        for training_id in training_today_ids.sorted(key=lambda r: r.start_datetime):
            raw_court = training_id.court or "court_1"
            court_label = f"Court {raw_court.replace('court_', '')}" if "court_" in raw_court else "Court 1"

            today_trainings_data.append({
                "id": training_id.id,
                "time": fields.Datetime.context_timestamp(self, training_id.start_datetime).strftime("%H:%M"),
                "court": court_label,
                "coach": training_id.tennis_coach_id.name,
                "state_label": state_labels.get(training_id.state, training_id.state),
                "state_class": state_classes.get(training_id.state, "bg-secondary")
            })

        # The center's revenue for the month
        start_of_the_local_month = datetime.combine(local_date.replace(day=1), datetime.min.time())
        start_of_the_utc_month = local_tz.localize(start_of_the_local_month).astimezone(pytz.utc).replace(tzinfo=None)

        training_this_month_ids = self.env["tennis.training"].search([
            ("center_id", "in", center_ids),
            ("state", "=", "done"),
            ("start_datetime", ">=", start_of_the_utc_month)
        ])
        total_revenue = sum(training_this_month_ids.mapped("price_total"))

        # Debtors
        debtors_data = []
        debtor_ids = self.env["res.partner"].search([
            ("tennis_balance", "<", 0),
            "|",
            ("training_ids.center_id", "in", center_ids),
            ("training_ids", "=", False)
        ], limit=5, order="tennis_balance asc")

        for debtor_id in debtor_ids:
            debtors_data.append({
                "id": debtor_id.id,
                "name": debtor_id.name,
                "phone": debtor_id.phone or "No phone",
                "balance": int(debtor_id.tennis_balance)
            })

        return {
            "metrics": {
                "approvals": approvals_count,
                "occupancy": f"{occupancy_pct}%",
                "new_clients": self.env["res.partner"].search_count([("is_tennis_client", "=", True)]),
                "revenue": f"{total_revenue:,.0f} $".replace(",", " ")
            },
            "debtors": debtors_data,
            "today_trainings": today_trainings_data
        }

    def button_recalculate_profit(self):
        """Recalculate historical profits and compile HTML activity data for the selected period."""
        for center_id in self:
            if not center_id.date_from or not center_id.date_to:
                continue

            user_tz = self.env.user.tz or "UTC"
            local_tz = pytz.timezone(user_tz)

            date_from = datetime.combine(center_id.date_from, datetime.min.time())
            date_to = datetime.combine(center_id.date_to, datetime.max.time())
            localize_date_from = local_tz.localize(date_from)
            localize_date_to = local_tz.localize(date_to)

            utc_date_from = localize_date_from.astimezone(pytz.utc).replace(tzinfo=None)
            utc_date_to = localize_date_to.astimezone(pytz.utc).replace(tzinfo=None)

            training_ids = self.env["tennis.training"].search([
                ("center_id", "=", center_id.id),
                ("start_datetime", ">=", utc_date_from),
                ("start_datetime", "<=", utc_date_to),
                ("state", "=", "done")
            ])

            counts = {"individual": 0, "split": 0, "group": 0}
            profits = {"individual": 0.0, "split": 0.0, "group": 0.0}
            client_counts = {}

            for training_id in training_ids:
                if training_id.training_type in counts:
                    counts[training_id.training_type] += 1
                    profits[training_id.training_type] += training_id.price_center

                for client_id in training_id.client_ids:
                    client_counts[client_id.name] = client_counts.get(client_id.name, 0) + 1

            unique_clients_count = len(training_ids.mapped("client_ids"))
            total_visits_count = sum(len(training_id.client_ids) for training_id in training_ids)

            rows = ""
            for name, count in sorted(client_counts.items(), key=lambda x: x[1], reverse=True):
                rows += f"<tr><td>{name}</td><td class='text-center'>{count}</td></tr>"

            table_body = rows if rows else "<tr><td colspan='2' class='text-center text-muted'>No completed trainings for the period</td></tr>"
            html_table = f"""
                <table class="table table-sm table-striped mt-2">
                    <thead>
                        <tr>
                            <th>Client (full name)</th>
                            <th class="text-center" style="width: 200px;">Number of trainings</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_body}
                    </tbody>
                </table>
            """
            center_id.write({
                "stat_individual_count": counts["individual"],
                "stat_individual_profit": profits["individual"],
                "stat_split_count": counts["split"],
                "stat_split_profit": profits["split"],
                "stat_group_count": counts["group"],
                "stat_group_profit": profits["group"],
                "stat_clients_count": unique_clients_count,
                "stat_visits_count": total_visits_count,
                "client_activity_html": html_table,
            })

            type_labels = {"individual": "Individual", "split": "Split", "group": "Group"}
            valid_counts = {k: v for k, v in counts.items() if v > 0}

            if valid_counts:
                leader_key = max(valid_counts, key=valid_counts.get)
                center_id.most_popular_training_type = f"{type_labels[leader_key]} (conducted {valid_counts[leader_key]} times)"
            else:
                center_id.most_popular_training_type = "No completed trainings for the period"

        return {
            "effect": {
                "fadeout": "slow",
                "message": "Data updated!",
                "type": "rainbow_man",
            }
        }

    @api.model
    def get_owner_dashboard_data(self):
        """Gather global KPIs and operational analytics across all centers for the owner portal view."""
        user_id = self.env.user
        center_ids = user_id.center_ids
        if not center_ids:
            return {
                "kpis": {
                    "centers": {"value": 0, "trend": "No centers", "is_positive": False},
                    "revenue": {"value": "0 $", "trend": "0%", "is_positive": False},
                    "clients": {"value": 0, "trend": "0 per month", "is_positive": False},
                    "occupancy": {"value": "0%", "trend": "0%", "is_positive": False}
                },
                "centers": [],
                "events": []
            }

        currency_symbol = center_ids[0].currency_id.symbol or "$"
        today = fields.Date.today()
        start_this_month = today.replace(day=1)
        _, days_in_month = calendar.monthrange(today.year, today.month)
        last_day_prev_month = start_this_month - timedelta(days=1)
        start_prev_month = last_day_prev_month.replace(day=1)

        total_centers = len(center_ids)
        training_this_month_ids = self.env["tennis.training"].search([
            ("center_id", "in", center_ids.ids),
            ("state", "=", "done"),
            ("start_datetime", ">=", start_this_month)
        ])
        total_revenue = sum(training_this_month_ids.mapped("price_center"))

        training_prev_month_ids = self.env["tennis.training"].search([
            ("center_id", "in", center_ids.ids),
            ("state", "=", "done"),
            ("start_datetime", ">=", start_prev_month),
            ("start_datetime", "<=", last_day_prev_month)
        ])
        prev_revenue = sum(training_prev_month_ids.mapped("price_center"))

        if prev_revenue > 0:
            revenue_diff = ((total_revenue - prev_revenue) / prev_revenue) * 100
            revenue_trend = f"{'+' if revenue_diff >= 0 else ''}{revenue_diff:.1f}% vs last month"
            revenue_positive = revenue_diff >= 0
        else:
            revenue_trend = "First revenue!" if total_revenue > 0 else "0% vs last month"
            revenue_positive = total_revenue > 0

        unique_clients_count = len(training_this_month_ids.mapped("client_ids"))
        total_potential_hours = 0
        total_actual_hours = 0
        centers_list_data = []

        for center_id in center_ids:
            c_training_ids = training_this_month_ids.filtered(lambda t: t.center_id.id == center_id.id)
            c_clients = len(c_training_ids.mapped("client_ids"))
            c_revenue = sum(c_training_ids.mapped("price_center"))
            working_hours = (center_id.end_time - center_id.start_time) if (
                        center_id.end_time > center_id.start_time) else 12
            center_potential = (center_id.court or 1) * working_hours * days_in_month
            center_actual = sum(c_training_ids.mapped("duration"))
            total_potential_hours += center_potential
            total_actual_hours += center_actual
            center_occupancy = min(int((center_actual / center_potential) * 100), 100) if center_potential else 0

            prev_center_revenue = sum(
                training_prev_month_ids.filtered(lambda t: t.center_id.id == center_id.id).mapped("price_center"))
            centers_list_data.append({
                "id": center_id.id,
                "name": center_id.name,
                "clients": f"{c_clients} clients",
                "revenue": f"{c_revenue:,.2f} {currency_symbol}".replace(",", " "),
                "occupancy": center_occupancy,
                "trend_up": c_revenue >= prev_center_revenue
            })

        global_occupancy = min(int((total_actual_hours / total_potential_hours) * 100),
                               100) if total_potential_hours else 0
        recent_training_ids = self.env["tennis.training"].search([("center_id", "in", center_ids.ids)],
                                                                 order="write_date desc", limit=5)
        events_list_data = []
        state_labels = {"done": "Training completed", "draft": "Schedule update", "cancel": "Canceling a training"}
        state_colors = {"done": "success", "draft": "primary", "cancel": "danger"}

        for training_id in recent_training_ids:
            local_time = fields.Datetime.context_timestamp(self, training_id.write_date)
            time_str = local_time.strftime("%H:%M") if training_id.write_date else "Just now"
            events_list_data.append({
                "title": f"{state_labels.get(training_id.state, 'Changing an entry')} ({training_id.training_type})",
                "center": training_id.center_id.name,
                "time": f"Today, {time_str}",
                "type": state_colors.get(training_id.state, "warning")
            })

        if not events_list_data:
            events_list_data = [{
                "title": "The network is empty",
                "center": "All branches",
                "time": "Synchronously",
                "type": "primary"
            }]

        return {
            "kpis": {
                "centers": {"value": total_centers, "trend": f"+{total_centers} active", "is_positive": True},
                "revenue": {"value": f"{total_revenue:,.0f} {currency_symbol}".replace(",", " "),
                            "trend": revenue_trend, "is_positive": revenue_positive},
                "clients": {"value": unique_clients_count, "trend": f"+{unique_clients_count} this month",
                            "is_positive": True},
                "occupancy": {"value": f"{global_occupancy}%", "trend": "Network plan: 65%",
                              "is_positive": global_occupancy >= 65}
            },
            "centers": centers_list_data,
            "events": events_list_data
        }

    @api.model
    def action_open_dashboard(self):
        """Determine user security groups and open the corresponding interface action dashboard."""
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")
        user_center_id = self.env.user.employee_id.center_id.id

        if is_owner:
            return {"type": "ir.actions.client", "tag": "tennis_owner_dashboard", "name": "Owner Control Panel"}
        elif is_manager:
            return {"type": "ir.actions.client", "tag": "tennis_manager_dashboard",
                    "params": {"center_id": user_center_id}}
        elif is_coach:
            return {"type": "ir.actions.client", "tag": "tennis_coach_dashboard",
                    "params": {"center_id": user_center_id}}
        else:
            return {
                "name": "Getting Started",
                "type": "ir.actions.act_window",
                "res_model": "tennis.welcome.wizard",
                "view_mode": "form",
                "target": "self"
            }