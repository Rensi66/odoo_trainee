from odoo import api, fields, models


class ModelsForActions(models.Model):
    _name = 'model.for.actions'

    field1 = fields.Text(required=False)
