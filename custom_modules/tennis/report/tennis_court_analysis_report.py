from odoo import models, api, fields
from datetime import datetime

class ReportTennisCourtAnalysis(models.AbstractModel):
    # Имя строго мапится на будущий XML-шаблон: report. + ID шаблона
    _name = 'report.tennis.report_court_analysis_template'
    _description = 'Логика анализа загрузки и доходности кортов'

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        day_start = datetime.combine(fields.Date.from_string(date_from), datetime.min.time())
        day_end = datetime.combine(fields.Date.from_string(date_to), datetime.max.time())

        # Ищем закрытые тренировки на кортах выбранных центров
        trainings = self.env['tennis.training'].search([
            ('center_id', 'in', data.get('center_ids')),
            ('state', '=', 'done'),
            ('start_datetime', '>=', day_start),
            ('start_datetime', '<=', day_end),
            ('court', '!=', False)  # Исключаем ошибки, если корт не указан
        ])

        # Агрегируем данные по кортам
        court_data = {}
        for training in trainings:
            # Так как court — это строка, делаем уникальный ключ: (ID центра, корт)
            court_key = (training.center_id.id, training.court)

            if court_key not in court_data:
                raw_court = training.court
                # Красиво форматируем техническое имя: 'court_1' -> 'Корт 1'
                court_label = f"Корт {raw_court.replace('court_', '')}" if 'court_' in raw_court else raw_court

                court_data[court_key] = {
                    'court_name': court_label,
                    'center_name': training.center_id.name,
                    'hours_count': 0,
                    'revenue': 0.0
                }

            # Плюсуем реальную длительность тренировки в часах и общую стоимость
            court_data[court_key]['hours_count'] += training.duration
            court_data[court_key]['revenue'] += training.price_total

        return {
            'date_from': date_from,
            'date_to': date_to,
            'courts': list(court_data.values()),
            'total_revenue': sum(c['revenue'] for c in court_data.values())
        }