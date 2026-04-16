from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    selected_product_json = fields.Json(compute='_compute_selected_product_json')

    @api.depends('order_line.product_id')
    def _compute_selected_product_json(self):
        for order in self:
            ids = order.order_line.mapped('product_id').ids
            order.selected_product_json = ids or []

    @api.constrains('order_line')
    def _check_product_id(self):
        for order in self:
            product_ids = order.order_line.mapped("product_id").ids
            if len(product_ids) != len(set(product_ids)):
                raise ValidationError("You can`t add same products")