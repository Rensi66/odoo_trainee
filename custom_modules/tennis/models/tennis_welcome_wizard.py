from odoo import models, fields, api

class TennisWelcomeWizard(models.TransientModel):
    _name = "tennis.welcome.wizard"
    _description = 'Welcome Wizard'

    name = fields.Char(string="Welcome", default=" ")


    def action_become_owner(self):
        if not self.env.user.has_group("tennis.group_tennis_owner"):
            group = self.env.ref("tennis.group_tennis_owner")
            self.env.user.write({"groups_id": [(4, group.id)]})

        return {
            "name": "Action Become Owner",
            "type": "ir.actions.act_window",
            "res_model": "tennis.center",
            "view_mode": "list,form",
            "target": "self"
        }

    def action_check_mail(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/odoo/action-mail.action_discuss',
            'target': 'self',
        }