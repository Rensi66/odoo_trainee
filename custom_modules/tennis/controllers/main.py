from odoo.http import Controller, request, route


class TennisController(Controller):
    @route("/tennis/accept_invitation/<int:center_id>", auth="user", type="http", website=True)
    def accept_invitation_manager(self, center_id, **kwargs):
        manager_group = request.env.ref("tennis.group_tennis_manager")
        request.env.user.write({"groups_id": [(4, manager_group.id)]})

        Employee = request.env["hr.employee"].sudo()
        employee = Employee.search([("user_id", "=", request.env.user.id)], limit=1)

        employee.write({"center_id": center_id})

        target_url = f"/web#id={center_id}&model=tennis.center&view_type=form"
        return request.redirect(target_url)

    @route("/tennis/accept_invitation/coach/<int:center_id>", type="http", website=True, auth="user")
    def accept_invitation_coach(self, center_id, **kwargs):
        coach_group = request.env.ref("tennis.group_tennis_coach")
        request.env.user.write({"groups_id": [(4, coach_group.id)]})

        Coach = request.env["tennis.coach"].sudo()
        coach = Coach.search([("user_id", "=", request.env.user.id)], limit=1)

        coach.write({"center_id": center_id})

        target_url = f"/web#id={center_id}&model=tennis.center&view_type=form"
        return request.redirect(target_url)
