from odoo import api, models


class ProjectBase(models.AbstractModel):
    _inherit = "base"

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views( views=views, options=options)

        for data_values in res.get("views", {}).values():
            if data_values.get("arch"):
                data_values["arch"] = data_values["arch"].replace("string='Customer'", "string='Partner'")

        for model in res.get("models", {}).values():
            if model.get("fields").get("partner_id"):
                model["fields"]["partner_id"]["string"] = "Partner"
        return res