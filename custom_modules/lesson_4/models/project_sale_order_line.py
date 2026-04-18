from odoo import api, fields, models


class ProjectSaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    express_picking_id = fields.Many2one("stock.picking")