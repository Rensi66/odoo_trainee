from odoo import fields, models, api


class ProjectSaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def action_open_split_wizard(self):
        return {
            'name': 'Split Line Wizard',
            'type': 'ir.actions.act_window',
            'res_model': 'model.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_line_ids': [(0, 0, {
                        'product_name': self.product_id.name,
                        'count': self.product_uom_qty,
                        'unit_price': self.price_unit,
                        'total': self.price_subtotal,
                        'is_basic': True})],
                        'basic_qty': self.product_uom_qty,
                        'original_order_id': self.id}
        }