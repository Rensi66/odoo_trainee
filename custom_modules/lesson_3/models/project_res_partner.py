from odoo import api, fields, models
from odoo.exceptions import UserError


class ProjectResPartner(models.Model):
    _inherit = "res.partner"

    is_primary = fields.Boolean(string="Is Primary")

    def action_toggle_is_primary(self):
        self.ensure_one()

        safe_self = self.with_context(skip_primary_toggle=True)
        safe_self.write({"is_primary": False})
        if safe_self.parent_id:
            safe_self.parent_id.child_ids.write({"is_primary": False})

        safe_self.is_primary = True

    @api.model
    def create(self, vals):
        if vals.get("parent_id") and not vals.get("is_company"):
            parent = self.env["res.partner"].browse(vals.get("parent_id"))
            if len(parent.child_ids) == 0:
                vals["is_primary"] = True

        record = super().create(vals)

        if vals.get("is_primary"):
            record.action_toggle_is_primary()

        return record

    def write(self, vals):
        if self._context.get("skip_primary_toggle"):
            return super().write(vals)

        update = super().write(vals)

        if vals.get("is_primary"):
            for record in self:
                record.action_toggle_is_primary()

        return update

    def unlink(self):
        for record in self:
            if record.is_primary:
                raise UserError("You can't unlink primary partner")

        return super().unlink()