import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
// В Odoo 18 все хуки и компоненты OWL импортируются строго отсюда:
import { Component, useState, onWillStart } from "@odoo/owl";

class TennisOwnerDashboard extends Component {
    setup() {
        // Проверенный сервис ORM для Odoo 18
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            data: {
                kpis: { centers: {}, revenue: {}, clients: {}, occupancy: {} },
                centers: [],
                events: []
            }
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        const result = await this.orm.call(
            "tennis.center",
            "get_owner_dashboard_data",
            []
        );
        if (result) {
            this.state.data = result;
        }
    }

    openCenterForm(centerId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "tennis.center",
            res_id: centerId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openCreateCenterWizard() {
        this.action.doAction({
            name: "Добавить новый теннисный центр",
            type: "ir.actions.act_window",
            res_model: "tennis.center",
            views: [[false, "form"]],
            target: "new",
        });
    }

    openAllClientsView() {
        this.action.doAction({
            name: "Теннисная клиентская база",
            type: "ir.actions.act_window",
            res_model: "res.partner",
            domain: [["is_tennis_client", "=", true]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openGlobalTrainings() {
        this.action.doAction({
            name: "Все тренировки сети",
            type: "ir.actions.act_window",
            res_model: "tennis.training",
            views: [[false, "calendar"], [false, "list"]],
            target: "current",
        });
    }

    // ==== ГЛОБАЛЬНЫЕ ИНСТРУМЕНТЫ (ОТЧЕТЫ ЧЕРЕЗ ОДИН ВИЗАРД) ====
    openFinancialReport() {
        this.action.doAction({
            name: "Выгрузка сводного P&L сети",
            type: "ir.actions.act_window",
            res_model: "tennis.universal.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { 'default_report_type': 'pnl' } // Изменили тут
        });
    }

    openPayrollReport() {
        this.action.doAction({
            name: "Ведомость выплат сотрудникам",
            type: "ir.actions.act_window",
            res_model: "tennis.universal.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { 'default_report_type': 'payroll' } // Изменили тут
        });
    }

    openCourtAnalysisReport() {
        this.action.doAction({
            name: "Анализ эффективности корт-часа",
            type: "ir.actions.act_window",
            res_model: "tennis.universal.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { 'default_report_type': 'court_analysis' } // Изменили тут
        });
    }
}

// Привязываем шаблон и регистрируем в Odoo 18
TennisOwnerDashboard.template = "tennis.OwnerDashboard";
registry.category("actions").add("tennis_owner_dashboard", TennisOwnerDashboard);