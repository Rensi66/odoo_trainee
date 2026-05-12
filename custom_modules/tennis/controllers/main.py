from odoo.http import Controller, request, route


class TennisController(Controller):
    @route("/tennis/accept_invitation/<int:center_id>", auth="user", type="http", website=True)
    def accept_invitation(self, center_id, **kwargs):
        manager_group = request.env.ref("tennis.group_tennis_manager")
        request.env.user.write({"groups_id": [(4, manager_group.id)]})

        target_url = f"/web#id={center_id}&model=tennis.center&view_type=form"
        return request.redirect(target_url)
