import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

class TennisOwnerDashboard extends Component {
    setup() {
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
            name: "Add a New Tennis Center",
            type: "ir.actions.act_window",
            res_model: "tennis.center",
            views: [[false, "form"]],
            target: "new",
        });
    }

    openAllClientsView() {
        this.action.doAction({
            name: "Tennis Client Base",
            type: "ir.actions.act_window",
            res_model: "res.partner",
            domain: [["is_tennis_client", "=", true]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openGlobalTrainings() {
        this.action.doAction({
            name: "All Network Workouts",
            type: "ir.actions.act_window",
            res_model: "tennis.training",
            views: [[false, "calendar"], [false, "list"]],
            target: "current",
        });
    }

    openFinancialReport() {
        this.action.doAction({
            name: "Export of Consolidated Network P&L",
            type: "ir.actions.act_window",
            res_model: "tennis.universal.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { "default_report_type": "pnl" }
        });
    }

    openPayrollReport() {
        this.action.doAction({
            name: "Employee Payroll Register",
            type: "ir.actions.act_window",
            res_model: "tennis.universal.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { "default_report_type": "payroll" }
        });
    }

    openCourtAnalysisReport() {
        this.action.doAction({
            name: "Analysis of Court-Hour Efficiency",
            type: "ir.actions.act_window",
            res_model: "tennis.universal.report.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { "default_report_type": "court_analysis" }
        });
    }
}

TennisOwnerDashboard.template = "tennis.OwnerDashboard";
registry.category("actions").add("tennis_owner_dashboard", TennisOwnerDashboard);