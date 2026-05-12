{
    "name": "World Of Tennis",
    "summary": "Module for management and analysis of sports centers",
    "version": "1.0",
    "depends": ["base",
                "hr",
                "mail",
                "base_automation"],
    "data": [#SECURITY
             "security/res_groups.xml",
             "security/ir.model.access.csv",
            #WELCOME FORM
            "wizard/tennis_owner_welcome_wizard.xml",
            "views/menus.xml",
             #OWNER
             "views/tennis_center_views.xml"],
    "application": True
}

