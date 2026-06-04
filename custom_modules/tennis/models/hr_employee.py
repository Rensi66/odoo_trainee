from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    center_id = fields.Many2one("tennis.center", ondelete="set null", readonly=True)