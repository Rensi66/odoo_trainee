from datetime import datetime, time
import pytz

from odoo import api, fields, models, tools


class TennisCoachReport(models.Model):
    _name = "tennis.coach.report"
    _auto = False

    tennis_coach_id = fields.Many2one("tennis.coach", string="Coach", required=True)
    month = fields.Date(string="Month", readonly=True)
    total_hours = fields.Integer(string="Total Hours", readonly=True)
    total_salary = fields.Monetary(string="Total Salary", readonly=True, currency_field="currency_id")
    total_trainings = fields.Integer(string="Total Trainings", readonly=True)

    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, "tennis_coach_report")

        self.env.cr.execute(f"""
        CREATE OR REPLACE VIEW {self._table} AS (
            SELECT 
                ROW_NUMBER() OVER() AS id,
                t.tennis_coach_id AS tennis_coach_id,
                DATE_TRUNC('month', t.start_datetime)::date as month,
                COUNT(t.id) AS total_trainings,
                SUM(duration) AS total_hours,
                COALESCE(SUM(t.price_coach), 0) as total_salary,
                (SELECT currency_id FROM res_company WHERE id = 1) AS currency_id
                
            FROM tennis_training t
            WHERE t.state = 'done'
            GROUP BY t.tennis_coach_id,
                    DATE_TRUNC('month', t.start_datetime)::date)
            """)

    @api.model
    def get_dashboard_data(self):
        user = self.env.user
        coach = self.env['tennis.coach'].search([('user_id', '=', user.id)], limit=1)

        if not coach:
            return {
                'coach_name': user.name,
                'kpi': {'total_trainings': 0, 'total_hours': 0, 'total_salary_formatted': "0 ₽"},
                'today_trainings': [],
                'chart_data': {'labels': [], 'values': []}
            }

        # СНАЧАЛА ОПРЕДЕЛЯЕМ ОБЩИЕ ПЕРЕМЕННЫЕ ВРЕМЕНИ (Доступны для Блоков 1, 2 и 3)
        user_tz_string = coach.user_id.tz or self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz_string)
        today_local = datetime.now(local_tz).date()

        # ==========================================
        # 1. KPI ЗА ТЕКУЩИЙ МЕСЯЦ
        # ==========================================
        import calendar
        current_date = today_local  # Теперь переменная определена выше и не упадет!

        # Вычисляем границы месяца в UTC для правильной фильтрации ORM
        m_start = local_tz.localize(datetime.combine(current_date.replace(day=1), time.min)).astimezone(pytz.utc)
        _, last_d = calendar.monthrange(current_date.year, current_date.month)
        m_end = local_tz.localize(datetime.combine(current_date.replace(day=last_d), time.max)).astimezone(pytz.utc)

        # Ищем все выполненные тренировки тренера за месяц через стандартный поиск Odoo
        trainings_this_month = self.env['tennis.training'].search([
            ('tennis_coach_id', '=', coach.id),
            ('state', '=', 'done'),
            ('start_datetime', '>=', fields.Datetime.to_string(m_start)),
            ('start_datetime', '<=', fields.Datetime.to_string(m_end))
        ])

        # Считаем агрегаты средствами Python поверх объектов Odoo
        total_trainings = len(trainings_this_month)
        total_hours = int(sum(trainings_this_month.mapped('duration')))
        salary = sum(trainings_this_month.mapped('price_coach'))

        # Исправлен лишний отступ (был сломан индент)
        salary_formatted = f"{salary:,.0f} ₽".replace(',', ' ')

        # ==========================================
        # 2. ТРЕНИРОВКИ НА СЕГОДНЯ
        # ==========================================
        local_start = datetime.combine(today_local, time.min)
        local_end = datetime.combine(today_local, time.max)
        start_utc = local_tz.localize(local_start).astimezone(pytz.utc)
        end_utc = local_tz.localize(local_end).astimezone(pytz.utc)

        trainings_today = self.env['tennis.training'].search([
            ('tennis_coach_id', '=', coach.id),
            ('start_datetime', '>=', fields.Datetime.to_string(start_utc)),
            ('start_datetime', '<=', fields.Datetime.to_string(end_utc)),
            ('state', 'in', ['confirmed', 'in_progress', 'done', 'cancel']),
        ], order='start_datetime asc')

        status_mapping = {
            'confirmed': {'label': 'Запланирована', 'class': 'text-primary',
                          'style': 'background-color: #e0f2fe; color: #0369a1 !important;'},
            'in_progress': {'label': 'Идет сейчас', 'class': 'text-warning fw-bold',
                            'style': 'background-color: #fef3c7; color: #b45309 !important;'},
            'done': {'label': 'Выполнена ✓', 'class': 'text-success',
                     'style': 'background-color: #dcfce7; color: #15803d !important;'},
            'cancel': {'label': 'Отменена ✕', 'class': 'text-danger',
                       'style': 'background-color: #fee2e2; color: #b91c1c !important;'},
        }

        today_list = []
        for t in trainings_today:
            local_time = fields.Datetime.context_timestamp(self, t.start_datetime).strftime('%H:%M')
            status_info = status_mapping.get(t.state, {'label': t.state, 'class': 'bg-light text-dark'})
            type_label = dict(t._fields['training_type']._description_selection(self.env)).get(t.training_type,
                                                                                               t.training_type)
            court_label = dict(t._fields['court']._description_selection(self.env)).get(t.court, t.court)

            today_list.append({
                'id': t.id,
                'time': local_time,
                'client_name': t.display_clients or "Индивидуальный клиент",
                'court_name': f"Корт: {court_label}",
                'client_level': t.client_ids[
                    0].client_level if t.client_ids and 'client_level' in t.client_ids._fields else 'Любитель',
                'is_group': t.training_type == 'group',
                'type_label': type_label,
                'status_label': status_info['label'],
                'status_class': status_info['class'],
                'status_style': status_info.get('style', '')
            })

        # ==========================================
        # 3. АНАЛИТИКА ПО ДНЯМ ТЕКУЩЕГО МЕСЯЦА (ГРАФИК)
        # ==========================================
        _, last_day = calendar.monthrange(today_local.year, today_local.month)

        month_start_utc = local_tz.localize(datetime.combine(today_local.replace(day=1), time.min)).astimezone(pytz.utc)
        month_end_utc = local_tz.localize(datetime.combine(today_local.replace(day=last_day), time.max)).astimezone(
            pytz.utc)

        monthly_trainings = self.env['tennis.training'].search([
            ('tennis_coach_id', '=', coach.id),
            ('state', '=', 'done'),
            ('start_datetime', '>=', fields.Datetime.to_string(month_start_utc)),
            ('start_datetime', '<=', fields.Datetime.to_string(month_end_utc))
        ])

        daily_earnings = {}
        for t in monthly_trainings:
            t_naive = fields.Datetime.from_string(t.start_datetime)
            t_local = pytz.utc.localize(t_naive).astimezone(local_tz)
            day_num = t_local.day
            daily_earnings[day_num] = daily_earnings.get(day_num, 0.0) + float(t.price_coach)

        chart_labels = []
        chart_values = []
        for day in range(1, today_local.day + 1):
            chart_labels.append(f"{day:02d}")
            chart_values.append(daily_earnings.get(day, 0.0))

        return {
            'coach_name': coach.name,
            'kpi': {
                'total_trainings': total_trainings,
                'total_hours': total_hours,
                'total_salary_formatted': salary_formatted
            },
            'today_trainings': today_list,
            'chart_data': {
                'labels': chart_labels,
                'values': chart_values
            }
        }