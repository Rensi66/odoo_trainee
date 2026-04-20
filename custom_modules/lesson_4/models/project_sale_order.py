from odoo import api, fields, models


class ProjectSaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()

        for order in self:
            picking = order.picking_ids[-1:]

            if picking:
                for line in order.order_line:
                    if line.is_express:
                        line.express_picking_id = picking.id

        return res