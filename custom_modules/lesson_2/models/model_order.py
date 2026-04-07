from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ModelOrder(models.Model):
    _name = "model.order"
    _description = "Main Model"

    order_no = fields.Char(string="Order Number")
    state = fields.Selection([
        ("draft", "Draft"),
        ("confirmed", "Set To Confirmed"),
    ], string="Order Status", default="draft", readonly=True)
    delivery_cost = fields.Float(string="Delivery Cost")
    global_discount = fields.Float(string="Global Discount")
    final_amount = fields.Float(string="Final Amount", compute="_compute_final_amount", store=True)

    line_ids = fields.One2many(
        "model.order.line",
        "order_id",
        string="Order Lines",
    )

    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    def action_set_to_draft(self):
        for record in self:
            record.state = 'draft'

    @api.depends("line_ids", "line_ids.raw_total","line_ids.subtotal", "delivery_cost", "global_discount")
    def _compute_final_amount(self):
        for order in self:
            raw_sum = sum(order.line_ids.mapped('raw_total'))
            raw_discount = raw_sum - sum(order.line_ids.mapped('subtotal'))
            raw_global_discount = (raw_sum + order.delivery_cost) * (order.global_discount / 100)
            order.final_amount = (raw_sum + order.delivery_cost) - raw_global_discount - raw_discount

    @api.onchange("delivery_cost", "global_discount")
    def _checking_negative_cost_onchange(self):
        if self.delivery_cost < 0 or self.global_discount < 0:
            return {"warning": {"title": "Wrong input", "message": "Cost can't be negative"}}
        else:
            return {}

    @api.constrains("delivery_cost", "global_discount")
    def _checking_negative_cost_constrains(self):
        for record in self:
            if record.delivery_cost < 0 or record.global_discount < 0:
                raise ValidationError("Delivery cost or discount can`t be negative")
