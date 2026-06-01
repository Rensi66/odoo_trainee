import calendar
from datetime import timedelta

from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError


class TennisCenter(models.Model):
    _name = 'tennis.center'
    _description = 'Tennis Center'

    name = fields.Char(required=True)
    address = fields.Char(required=True)
    court = fields.Integer(string="Number of courts", default=1, required=True)
    individual = fields.Monetary(string="Individual", default=100, required=True)
    split = fields.Monetary(string="Split", default=50, required=True)
    group = fields.Monetary(string="Group", default=30, required=True)
    start_time = fields.Float(required=True)
    end_time = fields.Float(required=True)
    tz = fields.Selection(_tz_get, string="Time Zone", default=lambda self: self.env.user.tz or "UTC", required=True)

    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    owner_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="cascade")
    manager_id = fields.Many2one("hr.employee", required=False, ondelete="set null")
    tennis_coach_ids = fields.One2many("tennis.coach", "center_id", required=False)

    # ==== НОВЫЕ ПОЛЯ ДЛЯ ФИНАНСОВОЙ ФИЛЬТРАЦИИ ====
    # По умолчанию ставим с 1-го числа текущего месяца по сегодняшний день
    date_from = fields.Date(
        string="Прибыль с",
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(
        string="Прибыль по",
        default=lambda self: fields.Date.today()
    )

    # Поле прибыли центра (store=False обязательно для динамики)
    total_center_profit = fields.Monetary(
        string="Прибыль центра",
        compute="_compute_center_profit",
        currency_field='currency_id'
    )

    most_popular_training_type = fields.Char(string="Самый популярный вид", readonly=True)

    # Статистика по Индивидуальным
    stat_individual_count = fields.Integer(string="Индивидуальные (кол-во)", readonly=True)
    stat_individual_profit = fields.Monetary(string="Индивидуальные (выручка)", readonly=True)

    # Статистика по Сплитам
    stat_split_count = fields.Integer(string="Сплиты (кол-во)", readonly=True)
    stat_split_profit = fields.Monetary(string="Сплиты (выручка)", readonly=True)

    # Статистика по Группам
    stat_group_count = fields.Integer(string="Групповые (кол-во)", readonly=True)
    stat_group_profit = fields.Monetary(string="Групповые (выручка)", readonly=True)

    _sql_constraints = [
        ("unique_manager_id", "UNIQUE(manager_id)",
         "There is already another manager at this center, or this employee is already the manager of another center."),
    ]

    def action_recalculate_profit(self):
        for center in self:
            if not center.date_from or not center.date_to:
                continue

            # Ищем только завершенные тренировки за указанный период (как ты и просил)
            trainings = self.env['tennis.training'].search([
                ('center_id', '=', center.id),
                ('start_datetime', '>=', center.date_from),
                ('start_datetime', '<=', center.date_to),
                ('state', '=', 'done')
            ])

            # Обнуляем показатели перед расчетом
            counts = {'individual': 0, 'split': 0, 'group': 0}
            profits = {'individual': 0.0, 'split': 0.0, 'group': 0.0}

            # Считаем
            for t in trainings:
                if t.training_type in counts:
                    counts[t.training_type] += 1
                    profits[t.training_type] += t.price_center

            # Записываем напрямую в модель центра
            center.write({
                'stat_individual_count': counts['individual'],
                'stat_individual_profit': profits['individual'],
                'stat_split_count': counts['split'],
                'stat_split_profit': profits['split'],
                'stat_group_count': counts['group'],
                'stat_group_profit': profits['group'],
            })

            # Вычисляем лидера по популярности
            type_labels = {'individual': 'Индивидуальная', 'split': 'Сплит', 'group': 'Групповая'}
            valid_counts = {k: v for k, v in counts.items() if v > 0}

            if valid_counts:
                # Сортируем и берем самый частый тип
                leader_key = max(valid_counts, key=valid_counts.get)
                center.most_popular_training_type = f"{type_labels[leader_key]} (проведено {valid_counts[leader_key]} раз)"
            else:
                center.most_popular_training_type = "Нет завершенных тренировок за период"

        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'Данные обновлены!',
                'type': 'rainbow_man',
            }
        }

    @api.depends('tennis_coach_ids.profit_for_center')
    def _compute_center_profit(self):
        for center in self:
            # Просто суммируем уже посчитанные значения из строк
            center.total_center_profit = sum(center.tennis_coach_ids.mapped('profit_for_center'))

    @api.constrains("court")
    def _check_count_of_court(self):
        if self.court < 1:
            raise ValidationError("Court can`t be less than 1")

    @api.model
    def action_check_role_and_open_view(self):
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        user_center_id = self.env.user.employee_id.center_id.id

        if is_owner:
            return {
                "type": "ir.actions.client",
                "tag": "tennis_owner_dashboard",
                "name": "Панель управления владельца"
            }
        elif is_manager:
            return {
                "type": "ir.actions.client",
                "tag": "tennis_manager_dashboard",
                "params": {"center_id": user_center_id},
            }
        elif is_coach:
            return {
                "type": "ir.actions.client",
                "tag": "tennis_coach_dashboard",
                "params": {"center_id": user_center_id},
            }
        else:
            return {
                "name": "Getting Started",
                "type": "ir.actions.act_window",
                "res_model": "tennis.welcome.wizard",
                "view_mode": "form",
                "target": "self"
            }

    @api.model
    def get_owner_dashboard_data(self):

        user = self.env.user
        centers = user.center_ids

        if not centers:
            return {
                "kpis": {
                    "centers": {"value": 0, "trend": "Нет центров", "is_positive": False},
                    "revenue": {"value": "0 $", "trend": "0%", "is_positive": False},
                    "clients": {"value": 0, "trend": "0 за месяц", "is_positive": False},
                    "occupancy": {"value": "0%", "trend": "0%", "is_positive": False},
                },
                "centers": [],
                "events": []
            }

        currency_symbol = centers[0].currency_id.symbol or "$"
        today = fields.Date.today()
        start_this_month = today.replace(day=1)

        # Динамически считаем количество дней в текущем месяце
        _, days_in_month = calendar.monthrange(today.year, today.month)

        # Границы прошлого месяца для расчета тренда выручки
        last_day_prev_month = start_this_month - timedelta(days=1)
        start_prev_month = last_day_prev_month.replace(day=1)

        # 1. РАСЧЕТ KPI
        total_centers = len(centers)

        # Выручка за текущий месяц
        trainings_this_month = self.env['tennis.training'].search([
            ('center_id', 'in', centers.ids),
            ('state', '=', 'done'),
            ('start_datetime', '>=', start_this_month)
        ])
        total_revenue = sum(trainings_this_month.mapped('price_center'))

        # Выручка за прошлый месяц
        trainings_prev_month = self.env['tennis.training'].search([
            ('center_id', 'in', centers.ids),
            ('state', '=', 'done'),
            ('start_datetime', '>=', start_prev_month),
            ('start_datetime', '<=', last_day_prev_month)
        ])
        prev_revenue = sum(trainings_prev_month.mapped('price_center'))

        if prev_revenue > 0:
            revenue_diff = ((total_revenue - prev_revenue) / prev_revenue) * 100
            revenue_trend = f"{'+' if revenue_diff >= 0 else ''}{revenue_diff:.1f}% vs прошлый месяц"
            revenue_positive = revenue_diff >= 0
        else:
            revenue_trend = "Первая выручка!" if total_revenue > 0 else "0% vs прошлый месяц"
            revenue_positive = total_revenue > 0

        # Уникальные клиенты сети за месяц
        unique_clients_count = len(trainings_this_month.mapped('client_ids'))

        # ГЛОБАЛЬНАЯ ЗАГРУЖЕННОСТЬ СЕТИ (Сумма по всем филиалам)
        total_potential_hours = 0
        total_actual_hours = 0

        centers_list_data = []
        for center in centers:
            c_trainings = trainings_this_month.filtered(lambda t: t.center_id.id == center.id)
            c_clients = len(c_trainings.mapped('client_ids'))
            c_revenue = sum(c_trainings.mapped('price_center'))

            # Вычисляем рабочие часы конкретного центра
            working_hours = (center.end_time - center.start_time) if (center.end_time > center.start_time) else 12
            # Потенциал центра = корты * часы в день * дней в месяце
            center_potential = (center.court or 1) * working_hours * days_in_month

            # Фактически отработано часов (если есть поле duration — используй его, иначе считаем по 1 часу на запись)
            center_actual = sum(c_trainings.mapped('duration')) if hasattr(self.env['tennis.training'],
                                                                           'duration') else len(c_trainings)

            # Добавляем в глобальную копилку сети
            total_potential_hours += center_potential
            total_actual_hours += center_actual

            # Локальный процент загрузки центра
            center_occupancy = min(int((center_actual / center_potential) * 100), 100) if center_potential else 0

            centers_list_data.append({
                'id': center.id,
                'name': center.name,
                'clients': f"{c_clients} теннисистов",
                'revenue': f"{c_revenue:,.2f} {currency_symbol}".replace(',', ' '),
                'occupancy': center_occupancy,
                'trend_up': c_revenue >= sum(
                    trainings_prev_month.filtered(lambda t: t.center_id.id == center.id).mapped('price_center'))
            })

        # Итоговый процент по всей сети
        global_occupancy = min(int((total_actual_hours / total_potential_hours) * 100),
                               100) if total_potential_hours else 0

        # 3. ПОСЛЕДНИЕ СОБЫТИЯ (ВОЗВРАЩАЕМ ЕБУЧУЮ ТОЧКУ)
        recent_trainings = self.env['tennis.training'].search([
            ('center_id', 'in', centers.ids)
        ], order='write_date desc', limit=5)

        events_list_data = []
        state_labels = {'done': 'Выполнена тренировка', 'draft': 'Обновление расписания', 'cancel': 'Отмена занятия'}
        # ИСПРАВЛЕНИЕ: Вместо 'muted' используем 'primary' (синий) или 'warning' (желтый), чтобы точка всегда красилась!
        state_colors = {'done': 'success', 'draft': 'primary', 'cancel': 'danger'}

        for t in recent_trainings:
            local_time = fields.Datetime.context_timestamp(self, t.write_date)
            time_str = local_time.strftime('%H:%M') if t.write_date else "Только что"

            events_list_data.append({
                'title': f"{state_labels.get(t.state, 'Изменение записи')} ({t.training_type})",
                'center': t.center_id.name,
                'time': f"Сегодня, {time_str}",
                'type': state_colors.get(t.state, 'warning')  # Если статус неопознан, бахнем оранжевый
            })

        if not events_list_data:
            events_list_data = [
                {"title": "Сеть пуста", "center": "Все филиалы", "time": "Синхронно", "type": "primary"}]

        return {
            "kpis": {
                "centers": {"value": total_centers, "trend": f"+{total_centers} активных", "is_positive": True},
                "revenue": {"value": f"{total_revenue:,.0f} {currency_symbol}".replace(',', ' '),
                            "trend": revenue_trend, "is_positive": revenue_positive},
                "clients": {"value": unique_clients_count, "trend": f"+{unique_clients_count} в этом месяце",
                            "is_positive": True},
                "occupancy": {"value": f"{global_occupancy}%", "trend": "План сети: 65%",
                              "is_positive": global_occupancy >= 65},
            },
            "centers": centers_list_data,
            "events": events_list_data
        }