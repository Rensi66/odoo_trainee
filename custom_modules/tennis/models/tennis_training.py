from datetime import datetime, timedelta

from lxml import etree
import pytz
import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..config import BOT_TOKEN


class TennisTraining(models.Model):
    _name = "tennis.training"
    _description = "Tennis Training"
    _inherits = {"calendar.event": "event_id"}
    _inherit = ["mail.thread"]

    state = fields.Selection([
        ("draft", "Draft"),
        ("to_approve", "To approve"),
        ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("to_approve_cancel", "To approve cancel"),
        ("cancel", "Cancelled"),
    ], string="Status", default="draft")
    training_type = fields.Selection([
        ("individual", "Individual"),
        ("split", "Split"),
        ("group", "Group"),
    ], required=True, default="group", string="Training Type")
    court = fields.Selection(selection="_get_court_selection", string="Court", required=True)
    start_datetime = fields.Datetime(string="Training Start", required=True)
    duration = fields.Integer(string="Duration", required=True, default=1)
    end_datetime = fields.Datetime(string="Training End", compute="_compute_end_datetime", store=True)
    price_center = fields.Monetary(string="Center Price", compute="_compute_price_center", store=True, aggregator=False)
    price_coach = fields.Monetary(string="Coach Price", compute="_compute_price_center", aggregator="sum", store=True)
    price_total = fields.Monetary(string="Total Price", compute="_compute_price_center", store=True, aggregator=False)
    display_coach = fields.Char(string="Coach", compute="_compute_display_coach")
    display_clients = fields.Char(string="Clients", compute="_compute_display_coach")
    is_reminder_sent = fields.Boolean(string="Reminder Sent", default=False)
    is_own_training = fields.Boolean(string="Is Own Training", compute="_compute_is_own_training",
                                     search="_search_is_own_training")

    busy_courts_ids = fields.Many2many("tennis.training", compute="_compute_busy_courts_ids", string="Busy Courts")
    event_id = fields.Many2one("calendar.event", string="Event", required=True, ondelete="cascade")
    tennis_coach_id = fields.Many2one("tennis.coach", required=True, ondelete="cascade")
    client_ids = fields.Many2many("res.partner", "tennis_client_training", "training_id", "partner_id", required=True)
    center_id = fields.Many2one("tennis.center", required=True,
                                default=lambda self: self.env.user.employee_id.center_id.id, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)

    @api.depends("tennis_coach_id")
    def _compute_is_own_training(self):
        """Check if the current training session belongs to the logged-in coach or if the user has administrative privileges."""
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        current_coach_id = self.env["tennis.coach"].search([
            ("employee_id", "=", self.env.user.employee_id.id)
        ], limit=1)
        coach_raw_id = current_coach_id.id if current_coach_id else False

        for record in self:
            if not record.tennis_coach_id:
                record.is_own_training = True
                continue

            if is_owner or is_manager or record.tennis_coach_id.id == coach_raw_id:
                record.is_own_training = True
            else:
                record.is_own_training = False

    @api.depends("tennis_coach_id", "client_ids", "is_own_training")
    def _compute_display_coach(self):
        """Anonymize coach and client information on the UI if the training does not belong to the current user."""
        for record in self:
            if record.is_own_training:
                record.display_coach = record.tennis_coach_id.name if record.tennis_coach_id else ""
                record.display_clients = ", ".join(record.client_ids.mapped("name")) if record.client_ids else ""
            else:
                record.display_coach = "Engaged"
                record.display_clients = "Confidentially"

    def _search_is_own_training(self, operator, value):
        """Search architectural implementation for the computed is_own_training field."""
        if operator not in ("=", "!="):
            raise ValueError("Unsupported operator for is_own_training search")

        positive = (operator == "=" and value) or (operator == "!=" and not value)

        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        if is_owner or is_manager:
            return [] if positive else [("id", "=", False)]

        current_coach_id = self.env["tennis.coach"].search([
            ("employee_id", "=", self.env.user.employee_id.id)
        ], limit=1)

        if current_coach_id:
            return [("tennis_coach_id", "=", current_coach_id.id)] if positive else [
                ("tennis_coach_id", "!=", current_coach_id.id)]

        return [("id", "=", False)]

    @api.depends("start_datetime", "court", "center_id")
    def _compute_busy_courts_ids(self):
        """Fetch all other training sessions occupying the same court on the same day."""
        for record in self:
            if not record.start_datetime or not record.court:
                record.busy_courts_ids = self.env["tennis.training"]
            else:
                user_tz = self.env.user.tz or "UTC"
                local_tz = pytz.timezone(user_tz)

                start_utc = pytz.utc.localize(record.start_datetime)
                start_local = start_utc.astimezone(local_tz)

                local_date = start_local.date()
                day_start_local = datetime.combine(local_date, datetime.min.time())
                day_end_local = datetime.combine(local_date, datetime.max.time())

                day_start_with_tz = local_tz.localize(day_start_local)
                day_end_with_tz = local_tz.localize(day_end_local)

                day_start_utc = day_start_with_tz.astimezone(pytz.utc).replace(tzinfo=None)
                day_end_utc = day_end_with_tz.astimezone(pytz.utc).replace(tzinfo=None)

                domain = [
                    ("center_id", "=", record.center_id.id),
                    ("start_datetime", ">=", day_start_utc),
                    ("start_datetime", "<=", day_end_utc),
                    ("court", "=", record.court),
                    ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
                ]

                if record.id:
                    current_id = record._origin.id or record.id
                    domain.append(("id", "!=", current_id))

                record.busy_courts_ids = self.env["tennis.training"].search(domain, order="start_datetime")

    @api.depends("start_datetime", "duration")
    def _compute_end_datetime(self):
        """Calculate end datetime based on start datetime and hours duration."""
        for record in self:
            record.end_datetime = record.start_datetime + timedelta(hours=record.duration)

    @api.depends("training_type", "duration", "tennis_coach_id.individual", "tennis_coach_id.split",
                 "tennis_coach_id.group",
                 "center_id.individual", "center_id.split", "center_id.group")
    def _compute_price_center(self):
        """Calculate the cost share for the center, the coach, and the final sum."""
        for record in self:
            if not record.training_type or not record.duration or not record.tennis_coach_id or not record.center_id:
                record.price_center = 0.0
                record.price_coach = 0.0
                record.price_total = 0.0
                continue

            center_rate = getattr(record.center_id, record.training_type, 0.0) or 0.0
            coach_rate = getattr(record.tennis_coach_id, record.training_type, 0.0) or 0.0

            record.price_center = record.duration * center_rate
            record.price_coach = record.duration * coach_rate
            record.price_total = record.price_center + record.price_coach

    @api.onchange("center_id")
    def _onchange_center_id(self):
        """Reset fields and dynamically update the available courts domain upon center alteration."""
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        vals = {"court": False}
        if not (is_coach and not is_owner):
            vals["tennis_coach_id"] = False

        self.update(vals)
        if self.center_id:
            return {"domain": {"court": [("center_id", "=", self.center_id.id)]}}

    @api.onchange("training_type", "client_ids")
    def _onchange_training_type_or_client_ids(self):
        """Soft validation in UI to warn users about capacity regulations per training type."""
        if self.training_type == "individual" and len(self.client_ids) > 1:
            return {"warning": {
                "title": "Limit the number of clients",
                "message": "Individual training can have only one client. Change count of clients or the type of training"
            }}
        elif self.training_type == "split" and len(self.client_ids) > 2:
            return {"warning": {
                "title": "Limit the number of clients",
                "message": "Split training must have only two clients. Change count of clients or the type of training"
            }}
        elif self.training_type == "group" and len(self.client_ids) > 5:
            return {"warning": {
                "title": "Limit the number of clients",
                "message": "Group training must have max 5 clients. Change count of clients or the type of training"
            }}

    @api.constrains("client_ids")
    def _check_balance(self):
        """Ensure no client with a negative tennis account balance can be registered."""
        for record in self:
            for client_id in record.client_ids:
                if client_id.tennis_balance < 0:
                    raise ValidationError(f"Client {client_id.name} has negative balance")

    @api.constrains("court", "tennis_coach_id", "client_ids", "start_datetime", "duration")
    def _check_unique_training_details(self):
        """Validate overlapping conflicts for courts, coaches, and clients. Prevents scheduling in the past."""
        for record in self:
            if not record.create_date or (record.state == "draft"):
                present_datetime = fields.Datetime.now()
                if record.start_datetime < present_datetime:
                    raise ValidationError("The training cannot be scheduled in the past.")

            overlapping_court_id = self.env["tennis.training"].search(domain=[
                ("id", "!=", record.id),
                ("center_id", "=", record.center_id.id),
                ("end_datetime", ">", record.start_datetime),
                ("start_datetime", "<", record.end_datetime),
                ("court", "=", record.court),
                ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
            ], limit=1)
            if overlapping_court_id:
                raise ValidationError("This court is already occupied")

            overlapping_coach_id = self.env["tennis.training"].search(domain=[
                ("id", "!=", record.id),
                ("tennis_coach_id", "=", record.tennis_coach_id.id),
                ("center_id", "=", record.center_id.id),
                ("end_datetime", ">", record.start_datetime),
                ("start_datetime", "<", record.end_datetime),
                ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
            ], limit=1)
            if overlapping_coach_id:
                raise ValidationError("This coach is already taken")

            overlapping_client_ids = self.env["tennis.training"].search(domain=[
                ("id", "!=", record.id),
                ("client_ids", "in", record.client_ids.ids),
                ("center_id", "=", record.center_id.id),
                ("end_datetime", ">", record.start_datetime),
                ("start_datetime", "<", record.end_datetime),
                ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
            ])
            if overlapping_client_ids:
                busy_client_ids = overlapping_client_ids.client_ids & record.client_ids
                clients = ", ".join(busy_client_ids.mapped("name"))
                raise ValidationError(f"This clients {clients} is already taken")

    @api.constrains("training_type", "client_ids")
    def _check_count_of_clients(self):
        """Hard constraint to enforce strict group size bounds during record save."""
        for record in self:
            if record.training_type == "individual" and len(self.client_ids) != 1:
                raise ValidationError("Individual training can have only one client")
            elif record.training_type == "split" and len(record.client_ids) != 2:
                raise ValidationError("Split training must have only two clients")
            elif record.training_type == "group" and (len(record.client_ids) < 3 or len(record.client_ids) > 5):
                raise ValidationError("Group training must have at least 3 clients and max 5 clients")

    @api.constrains("duration", "start_datetime")
    def _check_duration(self):
        """Verify that training fits perfectly within the center's open hours."""
        for record in self:
            if not record.duration or not record.start_datetime:
                continue

            if record.duration < 1:
                raise ValidationError("Min duration cannot be less than 1")

            if record.center_id.start_time == 0.0 and record.center_id.end_time == 0.0:
                continue

            center_tz_name = record.center_id.tz or "UTC"
            center_tz = pytz.timezone(center_tz_name)

            start_utc = pytz.utc.localize(record.start_datetime)
            start_local = start_utc.astimezone(center_tz)

            hour = start_local.hour
            minute = start_local.minute
            float_time = hour + (minute / 60.0)

            if record.center_id.end_time == 0.0:
                end = 24.0
            else:
                end = record.center_id.end_time

            if float_time < record.center_id.start_time:
                raise ValidationError("Start time can`t be less than center start time")

            if float_time + record.duration > end:
                raise ValidationError("End time must be less than center end time")

    @api.model
    def default_get(self, fields_list):
        """Set default coach if current user is linked to a coach employee record."""
        res = super().default_get(fields_list=fields_list)

        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        if is_coach and not (is_owner or is_manager):
            coach_id = self.env["tennis.coach"].search([
                ("employee_id", "=", self.env.user.employee_id.id)
            ], limit=1)

            if coach_id:
                res["tennis_coach_id"] = coach_id.id

        return res

    @api.model
    def get_views(self, views, options=None):
        """Dynamically inject architectural view modifiers based on user security access groups."""
        res = super().get_views(views=views, options=options)

        if "form" in res["views"]:
            is_owner = self.env.user.has_group("tennis.group_tennis_owner")
            is_manager = self.env.user.has_group("tennis.group_tennis_manager")
            is_coach = self.env.user.has_group("tennis.group_tennis_coach")

            doc = etree.fromstring(res["views"]["form"]["arch"])

            if is_owner:
                for node in doc.xpath("//field[@name='center_id']"):
                    node.attrib.pop("readonly", None)
                    node.set("modifiers", "{'readonly': False}")
                    node.set("domain", f"[('id', 'in', {self.env.user.center_ids.ids})]")

            elif is_manager:
                for node in doc.xpath("//field[@name='center_id']"):
                    node.set("readonly", "1")
                    node.set("modifiers", "{'readonly': True}")
                    node.set("domain", f"[('id', '=', {self.env.user.employee_id.center_id.id})]")

            else:
                for node in doc.xpath("//field[@name='center_id']"):
                    node.set("readonly", "1")
                    node.set("modifiers", "{'readonly': True}")

            if is_coach and not (is_owner or is_manager):
                for node in doc.xpath("//field[@name='tennis_coach_id']"):
                    node.set("readonly", "1")
                    node.set("options", "{'no_open': 'True'}")

            res["views"]["form"]["arch"] = etree.tostring(doc)

        return res

    def write(self, vals):
        """Trigger confirmation actions automatically if essential training parameters change."""
        change_training_ids = []
        for record in self:
            if record.state in ["in_progress", "done"]:
                raise ValidationError("You can`t change trainings in progress or done.")

            if "start_datetime" in vals or "duration" in vals or "court" in vals:
                if record.state == "confirmed":
                    change_training_ids.append(record)

        res = super().write(vals)

        for record_id in change_training_ids:
            record_id.button_confirm()

        return res

    def button_confirm(self):
        """Move workflow status to Confirmed or request manager approval if triggered by coach."""
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        if is_coach and not (is_owner or is_manager):
            self.write({"state": "to_approve"})

            template_id = self.env.ref("tennis.tennis_training_approve_template")

            body_html = template_id._render_field("body_html", [self.id])[self.id]
            subject = template_id._render_field("subject", [self.id])[self.id]
            partner_ids = [self.center_id.sudo().manager_id.user_id.partner_id.id]

            self.message_post(
                body=body_html,
                subject=subject,
                partner_ids=partner_ids,
                message_type="comment",
                subtype_xmlid="mail.mt_comment"
            )
        else:
            self.write({"state": "confirmed"})
            self.sudo().client_ids.write({"is_tennis_client": True})

    def button_cancel(self):
        """Handle cancellation requests, moving directly to 'cancel' or pushing to review state."""
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        if is_coach and not (is_owner or is_manager):
            self.button_confirm()
            self.write({"state": "to_approve_cancel"})
        else:
            self.write({"state": "cancel"})

    def button_accept_training(self):
        """Approve requested actions (creations or cancellations) waiting in the pipeline."""
        if self.state == "to_approve":
            self.write({"state": "confirmed"})
            self.sudo().client_ids.write({"is_tennis_client": True})
        elif self.state == "to_approve_cancel":
            self.write({"state": "cancel"})

    def button_cancel_training(self):
        """Deny approval requests, reverting statuses back to safe fallback options."""
        if self.state == "to_approve":
            self.write({"state": "cancel"})
        elif self.state == "to_approve_cancel":
            self.write({"state": "confirmed"})

    def _get_court_selection(self):
        """Compute dynamically the selection menu choices for court numbers in active center."""
        center_id = self.center_id

        if not center_id:
            user_center_id = self.env.user.employee_id.center_id.id or (
                self.env.user.center_ids[:1].id if self.env.user.center_ids else False)
            center_id = self.env["tennis.center"].browse(user_center_id)

        if center_id and center_id.court > 0:
            return [(f"court_{i}", f"Court {i}") for i in range(1, center_id.court + 1)]

        return [("default_court", "Court 1")]

    @api.model
    def _update_training_state(self):
        """Cron execution context method to switch training states based on elapsed time criteria."""
        training_ids = self.env["tennis.training"].search([("state", "in", ["confirmed", "in_progress"])])

        present_datetime = fields.Datetime.now()

        done_training_obj = self.env["tennis.training"]
        in_progress_training_obj = self.env["tennis.training"]
        for record in training_ids:
            if record.end_datetime <= present_datetime:
                done_training_obj |= record
            elif record.start_datetime <= present_datetime:
                in_progress_training_obj |= record

        done_training_obj.write({"state": "done"})
        for done_record_id in done_training_obj:
            for client_id in done_record_id.client_ids:
                client_id.write({"tennis_balance": client_id.tennis_balance - done_record_id.price_total})
        in_progress_training_obj.write({"state": "in_progress"})

    @api.model
    def _remind_about_training(self):
        """Cron mechanism dispatched to push Telegram alert notifications to clients prior to training."""
        present_datetime = fields.Datetime.now()
        reminder_time = 1
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        training_ids = self.env["tennis.training"].search(
            [("start_datetime", "<=", present_datetime + timedelta(hours=reminder_time)),
             ("start_datetime", ">=", present_datetime),
             ("is_reminder_sent", "=", False),
             ("state", "=", "confirmed"), ])

        for training_id in training_ids:
            raw_court = training_id.court
            court_label = raw_court
            if "court_" in raw_court:
                court_label = f"Court {raw_court.replace('court_', '')}"

            for client_id in training_id.client_ids:

                related_user_id = client_id.user_ids[:1]

                client_tz = related_user_id.tz or self.env.user.tz or "UTC"

                local_tz = pytz.timezone(client_tz)
                local_start_datetime = pytz.utc.localize(training_id.start_datetime).astimezone(local_tz).replace(
                    tzinfo=None)
                time_str = local_start_datetime.strftime("%H:%M")

                message = (
                    f"Training Reminder!\n"
                    f"Your workout will start at {time_str} h.\n"
                    f"Address: {training_id.center_id.address}\n"
                    f"Court: {court_label}"
                )

                if client_id.tg_chat_id:
                    payload = {
                        "chat_id": client_id.tg_chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                    try:
                        requests.post(url, json=payload, timeout=5)
                    except Exception as e:
                        continue

        training_ids.write({"is_reminder_sent": True})

    def button_tennis_recurring_training(self):
        """Return action context to launch the Recurring Training wizard view representation."""
        return {
            "name": "Recurring training",
            "type": "ir.actions.act_window",
            "res_model": "tennis.recurring.training",
            "view_mode": "form",
            "target": "current"
        }