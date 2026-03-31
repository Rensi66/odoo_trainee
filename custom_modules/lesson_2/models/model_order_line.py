from odoo import api, fields, models


class ModelOrderLine(models.Model):
    _name = "model.order.line"
    _description = "Model Order Line"

    product_name = fields.Char(string="Product Name")
    unit_price = fields.Float(string="Unit Price")
    count = fields.Integer(string="Count")
    discount = fields.Float(string="Discount")
    subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    order_id = fields.Many2one("model.order", string="Order", ondelete="cascade")


    @api.depends("unit_price", "count", "discount")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.unit_price * line.count * (1 - line.discount / 100)

