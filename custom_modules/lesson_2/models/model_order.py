from odoo import fields, models


class ModelOrder(models.Model):
    _name = "model.order"
    _description = "Main Model"

    order_no = fields.Char(string="Order Number")
    line_ids = fields.One2many(
        "model.order.line",
        "order_id",
        string="Order Lines",
    )




