import pytz
from datetime import datetime, date
from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    center_ids = fields.One2many("tennis.center", "owner_id", string="Centers")

    @api.model
    def get_manager_dashboard_data(self):
        user = self.env.user
        center_ids_list = []

        if user.has_group('tennis.group_tennis_owner'):
            center_ids_list = user.center_ids.ids
        elif user.employee_id.center_id:
            center_ids_list = [user.employee_id.center_id.id]

        if not center_ids_list:
            return {
                'metrics': {'approvals': 0, 'occupancy': '0%', 'new_clients': 0, 'revenue': '0 ₽'},
                'debtors': [],
                'today_trainings': []
            }

        # 1. Запросы на аппрув
        approvals_count = self.env['tennis.training'].search_count([
            ('center_id', 'in', center_ids_list),
            ('state', 'in', ['draft', 'to_approve'])
        ])

        # КОРРЕКТНЫЙ РАСЧЕТ ВРЕМЕНИ С УЧЕТОМ TZ ПОЛЬЗОВАТЕЛЯ
        user_tz = user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)
        local_now = datetime.now(local_tz)
        local_date = local_now.date()

        day_start_local = datetime.combine(local_date, datetime.min.time())
        day_end_local = datetime.combine(local_date, datetime.max.time())

        # Переводим локальные границы дня обратно в UTC для точного SQL-запроса
        day_start_utc = local_tz.localize(day_start_local).astimezone(pytz.utc).replace(tzinfo=None)
        day_end_utc = local_tz.localize(day_end_local).astimezone(pytz.utc).replace(tzinfo=None)

        # 2. Математика загрузки кортов
        total_capacity_hours = 0
        for center in self.env['tennis.center'].browse(center_ids_list):
            working_hours = (center.end_time if center.end_time != 0 else 24) - center.start_time
            total_capacity_hours += (working_hours if working_hours > 0 else 12) * center.court

        trainings_today = self.env['tennis.training'].search([
            ('center_id', 'in', center_ids_list),
            ('start_datetime', '>=', day_start_utc),
            ('start_datetime', '<=', day_end_utc),
            ('state', 'in', ['confirmed', 'in_progress', 'done', 'to_approve_cancel'])
        ])

        booked_hours = sum(trainings_today.mapped('duration'))
        occupancy_pct = int((booked_hours / total_capacity_hours) * 100) if total_capacity_hours > 0 else 0

        # 3. Расписание тренировок (добавлен ID для клика)
        today_trainings_data = []
        state_labels = dict(self.env['tennis.training']._fields['state'].selection)
        state_classes = {
            'confirmed': 'bg-primary', 'in_progress': 'bg-info text-dark',
            'done': 'bg-success', 'to_approve_cancel': 'bg-warning text-dark'
        }

        for t in trainings_today.sorted(key=lambda r: r.start_datetime):
            raw_court = t.court or "court_1"
            court_label = f"Корт {raw_court.replace('court_', '')}" if "court_" in raw_court else "Корт 1"

            today_trainings_data.append({
                'id': t.id,  # Передаем ID тренировки
                'time': fields.Datetime.context_timestamp(self, t.start_datetime).strftime('%H:%M'),
                'court': court_label,
                'coach': t.tennis_coach_id.name,
                'state_label': state_labels.get(t.state, t.state),
                'state_class': state_classes.get(t.state, 'bg-secondary')
            })

        # 4. Выручка за месяц
        start_of_month_dt = datetime.combine(date.today().replace(day=1), datetime.min.time())
        trainings_this_month = self.env['tennis.training'].search([
            ('center_id', 'in', center_ids_list),
            ('state', '=', 'done'),
            ('start_datetime', '>=', start_of_month_dt)
        ])
        total_revenue = sum(trainings_this_month.mapped('price_total'))

        # 5. Должники
        debtors_data = []
        debtors = self.env['res.partner'].search([
            ('tennis_balance', '<', 0),
            '|',
            ('training_ids.center_id', 'in', center_ids_list),
            ('training_ids', '=', False)
        ], limit=5, order='tennis_balance asc')

        for d in debtors:
            debtors_data.append({
                'id': d.id,
                'name': d.name,
                'phone': d.phone or 'Нет телефона',
                'balance': int(d.tennis_balance)
            })

        return {
            'metrics': {
                'approvals': approvals_count,
                'occupancy': f"{occupancy_pct}%",
                'new_clients': self.env['res.partner'].search_count([('is_tennis_client', '=', True)]),
                'revenue': f"{total_revenue:,.0f} ₽".replace(',', ' ')
            },
            'debtors': debtors_data,
            'today_trainings': today_trainings_data
        }