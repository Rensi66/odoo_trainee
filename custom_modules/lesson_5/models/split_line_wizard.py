from odoo import api, fields, models
from odoo.exceptions import UserError


class SplitLineWizard(models.TransientModel):
    _name = 'split.line.wizard'

    product_name = fields.Char(string="Product")
    count = fields.Integer(string="Count")
    unit_price = fields.Float(string="Price")
    total = fields.Float(string="Total", compute="_compute_total", store=False)
    is_basic = fields.Boolean(string="Basic")

    wizard_id = fields.Many2one('model.wizard')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        original_order = self.env["sale.order.line"].browse(self._context.get("original_order_id"))

        res.update({"product_name": original_order.product_id.name,
                    "count": 1,
                    "unit_price": original_order.price_unit})

        return res

    @api.depends("count")
    def _compute_total(self):
        for record in self:
            record.total = record.unit_price * record.count