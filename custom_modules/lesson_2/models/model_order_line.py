from odoo import api, fields, models

from odoo.exceptions import ValidationError


class ModelOrderLine(models.Model):
    _name = "model.order.line"
    _description = "Model Order Line"

    product_name = fields.Char(string="Product Name")
    unit_price = fields.Float(string="Unit Price")
    count = fields.Integer(string="Count")
    discount = fields.Float(string="Discount")
    raw_total = fields.Float(string="Raw Total", compute="_compute_raw_total")
    subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    order_id = fields.Many2one("model.order", string="Order", ondelete="cascade")


    @api.depends("unit_price", "count", "discount")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = (line.unit_price * line.count) * (1 - line.discount / 100)

    @api.depends("unit_price", "count")
    def _compute_raw_total(self):
        for line in self:
            line.raw_total = line.unit_price * line.count

    @api.onchange("unit_price", "count", "discount")
    def _checking_negative_cost_onchange(self):
        if self.unit_price < 0 or self.count < 0 or self.discount < 0:
            return {"warning": {"title": "Wrong input", "message": "Cost can't be negative"}}
        else:
            return {}

    @api.constrains("unit_price", "count", "discount")
    def _checking_cost(self):
        for record in self:
            if record.unit_price < 0 or record.count < 0 or record.discount < 0:
                raise ValidationError("Cost can`t be negative")