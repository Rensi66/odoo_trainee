from odoo import models, fields

class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    sequence = fields.Integer(default=10)
    _order = 'sequence, id'