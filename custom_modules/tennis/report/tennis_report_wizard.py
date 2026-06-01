from odoo import models, fields, api


class TennisUniversalReportWizard(models.TransientModel):
    _name = 'tennis.universal.report.wizard'
    _description = 'Универсальный визард для отчетов дашборда'

    date_from = fields.Date(string='Дата с', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Дата по', required=True, default=fields.Date.today())
    center_ids = fields.Many2many('tennis.center', string='Спортивные центры')

    # Скрытое поле для железного сохранения типа отчета
    report_type = fields.Char(string='Тип отчета')

    def action_generate_report(self):
        self.ensure_one()

        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'center_ids': self.center_ids.ids if self.center_ids else self.env['tennis.center'].search([]).ids
        }

        # Читаем тип отчета НАПРЯМУЮ ИЗ ПОЛЯ, а не из контекста
        report_type = self.report_type

        if report_type == 'pnl':
            return self.env.ref('tennis.action_report_pnl_pdf').report_action(self, data=data)
        elif report_type == 'payroll':
            return self.env.ref('tennis.action_report_payroll_pdf').report_action(self, data=data)
        elif report_type == 'court_analysis':
            return self.env.ref('tennis.action_report_court_analysis_pdf').report_action(self, data=data)