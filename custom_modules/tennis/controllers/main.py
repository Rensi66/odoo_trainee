from odoo.http import Controller, request, route


class TennisController(Controller):

    @route("/tennis/accept_invitation/<int:center_id>", auth="user", type="http", website=True)
    def accept_invitation_manager(self, center_id, **kwargs):
        """Accept manager invitation, assign security group, link employee to the sports center, and redirect to the dashboard."""
        manager_group = request.env.ref("tennis.group_tennis_manager")
        request.env.user.sudo().write({"groups_id": [(4, manager_group.id)]})

        center = request.env['tennis.center'].sudo().browse(int(center_id))
        if not center.exists():
            return "A center with this ID was not found, please contact the administrator."

        employee_id = request.env["hr.employee"].sudo().search(
            [("user_id", "=", request.env.user.id)],
            limit=1
        )

        if employee_id:
            employee_id.write({"center_id": center_id})

        target_url = "/web#action=tennis_manager_dashboard"
        return request.redirect(target_url)

    @route("/tennis/accept_invitation/coach/<int:center_id>", type="http", website=True, auth="user")
    def accept_invitation_coach(self, center_id, **kwargs):
        """Accept coach invitation, assign security group, link coach to the sports center, and redirect to the dashboard."""
        coach_group = request.env.ref("tennis.group_tennis_coach")
        request.env.user.sudo().write({"groups_id": [(4, coach_group.id)]})

        center = request.env['tennis.center'].sudo().browse(int(center_id))
        if not center.exists():
            return "A center with this ID was not found, please contact the administrator."

        coach_id = request.env["tennis.coach"].sudo().search(
            [("user_id", "=", request.env.user.id)],
            limit=1
        )

        if coach_id:
            coach_id.write({"center_id": center_id})

        target_url = "/web#action=tennis_coach_dashboard"
        return request.redirect(target_url)