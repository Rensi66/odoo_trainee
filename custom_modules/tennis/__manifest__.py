{
    "name": "World Of Tennis",
    "summary": "Module for management and analysis of sports centers",
    "version": "1.0",
    "depends": ["base",
                "base_automation",
                "calendar",
                "hr",
                "mail"],
    "data": ["security/res_groups.xml",
             "security/ir.model.access.csv",
             "security/ir_rules.xml",

             "data/tennis_training_cron.xml",

             "wizard/tennis_welcome_wizard.xml",
             "wizard/tennis_recurring_training_wizard.xml",
             "wizard/tennis_report_wizard_view.xml",

             "views/res_partner.xml",
             "views/tennis_center_views.xml",
             "views/tennis_coach_views.xml",

             "views/tennis_training_coach_statistics.xml",
             "views/tennis_training_views.xml",

             "views/menus.xml",

             "report/tennis_court_analysis_report_views.xml",
             "report/tennis_payroll_report_views.xml",
             "report/tennis_pnl_report_views.xml",
             ],
    "assets": {
        "web.assets_backend": [
            "tennis/static/src/scss/owner_dashboard.scss",
            "tennis/static/src/scss/manager_dashboard.scss",
            "tennis/static/src/scss/coach_dashboard.scss",
            "tennis/static/src/js/owner_dashboard.js",
            "tennis/static/src/js/manager_dashboard.js",
            "tennis/static/src/js/coach_dashboard.js",
            "tennis/static/src/xml/owner_dashboard_template.xml",
            "tennis/static/src/xml/manager_dashboard_template.xml",
            "tennis/static/src/xml/coach_dashboard_template.xml"
        ]
    },
    "application": True
}

