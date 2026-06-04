from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_tennis_client = fields.Boolean(string="Is tennis client", default=False)
    tennis_level = fields.Selection([
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("expert", "Expert"),
    ], string="Game Level", default="beginner")
    medical_notes = fields.Text(string="Medical contraindications")
    tennis_balance = fields.Monetary(string="Balance", default=0.0)
    coach_private_notes = fields.Html(string="Trainer's Notes")
    tg_chat_id = fields.Char(string="Telegram Chat ID")
    is_manager = fields.Boolean(compute="_compute_is_manager")

    training_count = fields.Integer(string="Training count", compute="_compute_client_stats", search="_search_training_count",
                                    groups="tennis.group_tennis_owner,tennis.group_tennis_coach")
    last_training_date = fields.Date(string="Last", compute="_compute_client_stats")
    client_status = fields.Selection([
        ("new", "New"),
        ("active", "Active"),
        ("inactive", "Inactive")
    ], string="Status", compute="_compute_client_stats")

    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.user.currency_id)
    training_ids = fields.Many2many("tennis.training", "tennis_client_training", "partner_id", "training_id")

    def _compute_is_manager(self):
        """Check the manager to change your personal data"""
        for record in self:
            record.is_manager = self.env.user.has_group("tennis.group_tennis_manager")

    def _compute_client_stats(self):
        """Collecting data to form the Clients window"""
        today = fields.Date.today()

        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        if is_owner:
            current_center_id = self.env.user.center_ids.ids
        else:
            current_center_id = self.env.user.employee_id.center_id.id

        for partner in self:
            if not current_center_id:
                partner.training_count = 0
                partner.last_training_date = False
                partner.client_status = False
                continue

            if is_owner:
                trainings = self.env["tennis.training"].search([
                    ("center_id", "in", current_center_id),
                    ("client_ids", "in", partner.id),
                    ("state", "=", "done"),
                ], order="start_datetime desc")
            elif not is_manager:
                trainings = self.env["tennis.training"].search([
                    ("center_id", "=", current_center_id),
                    ("client_ids", "in", partner.id),
                    ("state", "=", "done"),
                    ("tennis_coach_id.employee_id", "=", self.env.user.employee_id.id)
                ], order="start_datetime desc")
            elif is_manager:
                trainings = self.env["tennis.training"].search([
                    ("center_id", "=", current_center_id),
                    ("client_ids", "in", partner.id),
                    ("state", "=", "done"),
                ], order="start_datetime desc")

            count = len(trainings)
            partner.training_count = count

            if count > 0:
                last_date = trainings[0].start_datetime.date()
                partner.last_training_date = last_date

                if count <= 2:
                    partner.client_status = "new"
                elif (today - last_date).days <= 14:
                    partner.client_status = "active"
                else:
                    partner.client_status = "inactive"
            else:
                partner.last_training_date = False
                partner.client_status = False

    def _search_training_count(self, operator, value):
        """Dynamically generate a selection of courts from the sports center."""
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        if is_owner:
            current_center_id = self.env.user.center_ids.ids
        else:
            current_center_id = self.env.user.employee_id.center_id.id

        if not current_center_id:
            return [("id", "in", [])]

        if is_owner:
            domain = [("center_id", "in", current_center_id), ("state", "=", "done")]
        else:
            domain = [("center_id", "=", current_center_id), ("state", "=", "done")]

        if not (is_manager) and not (is_owner):
            domain.append(("tennis_coach_id.employee_id", "=", self.env.user.employee_id.id))

        trainings = self.env["tennis.training"].search(domain)
        partner_ids = trainings.mapped("client_ids").ids

        return [("id", "in", partner_ids)]

    def button_create_single_training(self):
        """Open a new individual training form view with the current client pre-filled"""
        self.ensure_one()
        return {
            "name": "New training",
            "type": "ir.actions.act_window",
            "res_model": "tennis.training",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_client_ids": [(4, self.id)],
                "default_training_type": "individual"
            }
        }