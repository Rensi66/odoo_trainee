from odoo import models, api, fields
from datetime import datetime


class ReportTennisPayroll(models.AbstractModel):
    # Имя строго мапится на будущий XML-шаблон: report. + ID шаблона
    _name = 'report.tennis.report_payroll_template'
    _description = 'Логика расчета выплат тренерскому составу'

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        # Приводим даты к границам дня для корректной фильтрации datetime в SQL
        day_start = datetime.combine(fields.Date.from_string(date_from), datetime.min.time())
        day_end = datetime.combine(fields.Date.from_string(date_to), datetime.max.time())

        # Находим все проведенные тренировки в выбранных теннисных центрах
        trainings = self.env['tennis.training'].search([
            ('center_id', 'in', data.get('center_ids')),
            ('state', '=', 'done'),
            ('start_datetime', '>=', day_start),
            ('start_datetime', '<=', day_end),
            ('tennis_coach_id', '!=', False)  # Считаем только те, где был тренер
        ])

        # Агрегируем данные по тренерам через Python-словарь
        coach_data = {}
        for training in trainings:
            coach = training.tennis_coach_id
            if coach.id not in coach_data:
                coach_data[coach.id] = {
                    'name': coach.name,
                    'trainings_count': 0,
                    'total_payout': 0.0
                }
            coach_data[coach.id]['trainings_count'] += 1
            coach_data[coach.id]['total_payout'] += training.price_coach

        return {
            'date_from': date_from,
            'date_to': date_to,
            'coaches': list(coach_data.values()),
            'total_amount': sum(c['total_payout'] for c in coach_data.values())
        }