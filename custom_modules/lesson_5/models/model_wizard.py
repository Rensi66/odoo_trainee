from odoo import api, fields, models
from odoo.exceptions import UserError


class ModelWizard(models.TransientModel):
    _name = "model.wizard"

    line_ids = fields.One2many("split.line.wizard", "wizard_id" ,string="Line IDs")

    @api.onchange("line_ids")
    def _onchange_line_ids(self):
        basic_line = self.line_ids.filtered(lambda line: line.is_basic)
        other_lines = self.line_ids.filtered(lambda line: not line.is_basic)

        other_lines_qty = sum(other_lines.mapped("count"))
        basic_line_qty = self._context.get("basic_qty") - other_lines_qty

        if basic_line_qty >= 1:
            basic_line.count = basic_line_qty
        else:
            raise UserError("You can`t split a line which has less than one quantity")

    def action_save_changes(self):
        original_line = self.env['sale.order.line'].browse(self._context.get('original_order_id'))
        order = original_line.order_id

        for line in self.line_ids:
            if line.is_basic:
                original_line.write({'product_uom_qty': line.count})
            else:
                original_line.copy({
                    'product_uom_qty': line.count,
                    'order_id': original_line.order_id.id
                })

        message = f"Splited into {len(self.line_ids)} lines by {self.env.user.name}"

        order.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

        return {'type': 'ir.actions.act_window_close'}


