from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    center_ids = fields.One2many("tennis.center", "owner_id", string="Centers")