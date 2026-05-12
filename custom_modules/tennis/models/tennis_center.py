from odoo import api, fields, models


class TennisCenter(models.Model):
    _name = 'tennis.center'
    _description = 'Tennis Center'

    name = fields.Char(required=True)
    address = fields.Char(required=True)
    court = fields.Integer(string="Number of courts", default=1, required=True)
    start_time = fields.Float(required=True)
    end_time = fields.Float(required=True)

    owner_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    manager_id = fields.Many2one("hr.employee", required=False)

    _sql_constraints = [
        ("unique_manager_id", "UNIQUE(manager_id)", "This center already has another manager")
    ]

    @api.model
    def action_check_role_and_open_view(self):
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        print(is_owner)
        if is_owner or is_manager or is_coach:
            return self.env.ref("tennis.action_tennis_center").read()[0]
        else:
            return {
                "name": "Getting Started",
                "type": "ir.actions.act_window",
                "res_model": "tennis.welcome.wizard",
                "view_mode": "form",
                "target": "self"
            }