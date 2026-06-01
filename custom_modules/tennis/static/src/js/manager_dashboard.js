import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

export class TennisManagerDashboard extends Component {
    setup() {
        this.actionService = useService("action"); // Подключаем сервис переходов Odoo

        this.state = useState({
            metrics: { approvals: 0, occupancy: "0%", new_clients: 0, revenue: "0 ₽" },
            debtors: [],
            today_trainings: []
        });

        onWillStart(async () => {
            const data = await rpc("/web/dataset/call_kw/res.users/get_manager_dashboard_data", {
                model: "res.users",
                method: "get_manager_dashboard_data",
                args: [],
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

    // Метод для открытия карточки клиента
    openClient(clientId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: clientId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // Метод для открытия карточки тренировки
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