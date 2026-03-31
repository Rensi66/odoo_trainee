from odoo import api, fields, models


class ModelOrder(models.Model):
    _name = "model.order"
    _description = "Main Model"

    order_no = fields.Char(string="Order Number")
    delivery_cost = fields.Float(string="Delivery Cost")
    global_discount = fields.Float(string="Global Discount")
    final_amount = fields.Float(string="Final Amount", compute="_compute_final_amount", store=True)

    line_ids = fields.One2many(
        "model.order.line",
        "order_id",
        string="Order Lines",
    )

    @api.depends("line_ids.subtotal", "delivery_cost", "global_discount")
    def _compute_final_amount(self):
        for order in self:
            order.final_amount = (sum(order.line_ids.mapped('subtotal')) + order.delivery_cost) * (1 - order.global_discount / 100)

