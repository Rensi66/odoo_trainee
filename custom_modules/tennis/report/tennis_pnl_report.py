from odoo import models, api, fields
from datetime import datetime


class ReportTennisPnL(models.AbstractModel):
    # Имя строго по шаблону: report. + техническое_имя_шаблона_отчета
    _name = 'report.tennis.report_pnl_template'
    _description = 'Логика расчета P&L сети'

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        # Конвертируем даты в datetime с границами дня для точного поиска по UTC в БД
        day_start = datetime.combine(fields.Date.from_string(date_from), datetime.min.time())
        day_end = datetime.combine(fields.Date.from_string(date_to), datetime.max.time())

        centers = self.env['tennis.center'].browse(data.get('center_ids'))
        centers_pnl = []

        for center in centers:
            # Ищем закрытые тренировки центра в выбранном периоде
            trainings = self.env['tennis.training'].search([
                ('center_id', '=', center.id),
                ('state', '=', 'done'),
                ('start_datetime', '>=', day_start),
                ('start_datetime', '<=', day_end)
            ])

            # Считаем финансовые потоки на основе твоей бизнес-логики:
            gross = sum(trainings.mapped('price_total'))  # Общий оборот (Грязная выручка)
            expenses = sum(trainings.mapped('price_coach'))  # Расход на тренеров (ФОТ)
            net = sum(trainings.mapped('price_center'))  # Чистый доход СЦ

            centers_pnl.append({
                'name': center.name,
                'address': center.address,
                'trainings_count': len(trainings),
                'gross': gross,
                'expenses': expenses,
                'net': net,
            })

        # Возвращаем контекст, который улетит прямиком в QWeb XML-шаблон
        return {
            'date_from': date_from,
            'date_to': date_to,
            'centers': centers_pnl,
            'total_gross': sum(c['gross'] for c in centers_pnl),
            'total_expenses': sum(c['expenses'] for c in centers_pnl),
            'total_net': sum(c['net'] for c in centers_pnl),
        }