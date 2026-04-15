from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    selected_product_json = fields.Json(compute='_compute_selected_product_json')

    @api.depends('order_line.product_id')
    def _compute_selected_product_json(self):
        for order in self:
            ids = order.order_line.mapped('product_id').ids
            order.selected_product_json = ids or []
            print(f">>> JSON DATA FOR DOMAIN: {order.selected_product_json}")