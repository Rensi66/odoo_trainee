import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class TennisManagerDashboard extends Component {
    setup() {
        this.actionService = useService("action");

        this.state = useState({
            metrics: { approvals: 0, occupancy: "0%", new_clients: 0, revenue: "0 $" },
            debtors: [],
            today_trainings: []
        });

        onWillStart(async () => {
            const centerId = this.props.action?.params?.center_id || false;

            const data = await rpc("/web/dataset/call_kw/tennis.center/get_manager_dashboard_data", {
                model: "tennis.center",
                method: "get_manager_dashboard_data",
                args: [centerId],
                kwargs: {},
            });

            if (data) {
                Object.assign(this.state, data);
            }
        });
    }

    callClient(phone) {
        window.location.href = `tel:${phone}`;
    }

    openClient(clientId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: clientId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTraining(trainingId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "tennis.training",
            res_id: trainingId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

TennisManagerDashboard.template = "tennis.ManagerDashboardTemplate";
registry.category("actions").add("tennis_manager_dashboard", TennisManagerDashboard);