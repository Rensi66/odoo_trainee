from odoo import api, fields, models


class ProjectSaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_express = fields.Boolean(default=False, string="Is Express")

    def _prepare_procurement_values(self, group_id=False):
        res = super()._prepare_procurement_values(group_id=group_id)
        if self.is_express:
            group_name = f"{self.order_id.name} [EXP]"
            new_group = self.env['procurement.group'].search([('name', '=', group_name)], limit=1)
            if not new_group:
                new_group = self.env['procurement.group'].create({
                    'name': group_name,
                    'move_type': self.order_id.picking_policy,
                    'sale_id': self.order_id.id,
                    'partner_id': self.order_id.partner_id.id,
                })
            res['origin'] = f"{self.order_id.name} - EXPRESS"
            res['group_id'] = new_group
        return res


class StockMove(models.Model):
    _inherit = "stock.move"

    is_express = fields.Boolean(string="Express")

    def _assign_picking(self):
        for move in self:
            if move.sale_line_id:
                move.is_express = move.sale_line_id.is_express

        express_moves = self.filtered(lambda m: m.is_express)
        standard_moves = self - express_moves

        if express_moves:
            super(StockMove, express_moves)._assign_picking()

        if standard_moves:
            super(StockMove, standard_moves)._assign_picking()

        return True

    def _get_new_picking_values(self):
        res = super()._get_new_picking_values()
        res['is_express'] = self[:1].is_express
        return res

    def _search_picking_for_assignation(self):
        picking = super()._search_picking_for_assignation()

        if picking:
            if picking.is_express != self.sale_line_id.is_express:
                return self.env['stock.picking']
        return picking


class StockPicking(models.Model):
    _inherit = "stock.picking"
    is_express = fields.Boolean(string="Express Delivery", default=False)