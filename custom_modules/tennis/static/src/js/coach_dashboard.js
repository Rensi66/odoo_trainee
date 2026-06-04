/** @odoo-module */

import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class CoachDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.chartRef = useRef("coachChart");

        this.state = useState({
            coachName: "",
            kpi: {
                total_trainings: 0,
                total_hours: 0,
                total_salary_formatted: "0 $"
            },
            todayTrainings: [],
            chartData: { labels: [], values: [] }
        });

        onWillStart(async () => {
            await this.loadDashboardData();
            await loadJS("/web/static/lib/Chart/Chart.js");
        });

        onMounted(() => {
            this.renderChart();
        });
    }

    async loadDashboardData() {
        const data = await this.orm.call("tennis.coach.report", "get_dashboard_data", []);
        this.state.coachName = data.coach_name;
        this.state.kpi = data.kpi;
        this.state.todayTrainings = data.today_trainings;
        this.state.chartData = data.chart_data;
    }

    onTrainingClick(training) {
        if (!training || !training.id) return;

        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "tennis.training",
            res_id: training.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    renderChart() {
        const ctx = this.chartRef.el;
        if (!ctx || !this.state.chartData.labels || !this.state.chartData.labels.length) {
            return;
        }

        new window.Chart(ctx, {
            type: "line",
            data: {
                labels: this.state.chartData.labels,
                datasets: [{
                    label: "Earnings ($)",
                    data: this.state.chartData.values,
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.1)",
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                resizeDelay: 10,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        animation: false
                    }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: "#f1f5f9" } },
                    x: { grid: { display: false } }
                }
            }
        });
    }
}

CoachDashboard.template = "tennis.CoachDashboard";
registry.category("actions").add("tennis_coach_dashboard", CoachDashboard);