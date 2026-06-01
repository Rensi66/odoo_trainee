from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_tennis_client = fields.Boolean(string="Is tennis client", default=False)
    tg_chat_id = fields.Char(string="Telegram Chat ID")
    tennis_level = fields.Selection([
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("expert", "Expert"),
    ], string="Уровень игры")
    medical_notes = fields.Text(string="Медицинские противопоказания")
    tennis_balance = fields.Monetary(string="Баланс", default=0.0)
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.user.currency_id)
    coach_private_notes = fields.Html(string="Заметки тренера")
    is_manager = fields.Boolean(compute='_compute_is_manager')

    training_count = fields.Integer(string="Количество посещений", compute="_compute_tennis_client_stats", search="_search_training_count",
                                    groups="tennis.group_tennis_owner,tennis.group_tennis_coach")
    last_training_date = fields.Date(string="Последняя", compute="_compute_tennis_client_stats")
    client_status = fields.Selection([
        ('new', 'Новый'),
        ('active', 'Активен'),
        ('inactive', 'Неактивен')
    ], string="Статус", compute="_compute_tennis_client_stats")

    training_ids = fields.Many2many("tennis.training", "tennis_client_training", "partner_id", "training_id")

    def _search_training_count(self, operator, value):
        is_owner = self.env.user.has_group('tennis.group_tennis_owner')
        is_manager = self.env.user.has_group('tennis.group_tennis_manager')
        if is_owner:
            current_center_id = self.env.user.center_ids.ids
        else:
            current_center_id = self.env.user.employee_id.center_id.id

        if not current_center_id:
            return [('id', 'in', [])]


        # Находим тренировки нашего центра в статусе done
        if is_owner:
            domain = [('center_id', 'in', current_center_id), ('state', '=', 'done')]
        else:
            domain = [('center_id', '=', current_center_id), ('state', '=', 'done')]

        if not (is_manager) and not (is_owner):
            domain.append(("tennis_coach_id.employee_id", "=", self.env.user.employee_id.id))

        trainings = self.env['tennis.training'].search(domain)

        # Собираем всех клиентов, у которых БЫЛИ эти тренировки
        partner_ids = trainings.mapped('client_ids').ids

        # ХЕНДЛИМ УСЛОВИЕ: тренировок БОЛЬШЕ чем 0 (наш случай из XML)
        if (operator == '>' and value == 0) or (operator == '>=' and value == 1) or (operator == '=' and value > 0):
            return [('id', 'in', partner_ids)]

        # ХЕНДЛИМ УСЛОВИЕ: если вдруг в будущем будем искать тех, у кого НЕТ тренировок
        if (operator == '=' and value == 0) or (operator == '<' and value == 1) or (operator == '<=' and value == 0):
            return [('id', 'not in', partner_ids)]

        # На случай остальных экзотических операторов
        return [('id', 'in', [])]

    def _compute_is_manager(self):
        for record in self:
            # Проверяем, входит ли юзер в группу менеджеров
            record.is_manager = self.env.user.has_group('tennis.group_tennis_manager')

    def _compute_tennis_client_stats(self):
        today = fields.Date.today()

        is_manager = self.env.user.has_group('tennis.group_tennis_manager')
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        if is_owner:
            current_center_id = self.env.user.center_ids.ids
        else:
            current_center_id = self.env.user.employee_id.center_id.id

        for partner in self:
            # Если мы не можем определить центр, или это левый системный партнер (например, сама компания)
            if not current_center_id:
                partner.training_count = 0
                partner.last_training_date = False
                partner.client_status = False
                continue

            if is_owner:
                print("ПОИСК ПО ВЛАДЕЛЬЦУ")
                trainings = self.env["tennis.training"].search([
                    ("center_id", "in", current_center_id),
                    ("client_ids", "in", partner.id),
                    ("state", "=", "done"),
                ], order='start_datetime desc')
            elif not is_manager:
                print("ПОИСК ПО ТРЕНЕРАМ ВКЛЮЧЕН")
                trainings = self.env['tennis.training'].search([
                    ('center_id', '=', current_center_id),
                    ('client_ids', 'in', partner.id),
                    ('state', '=', 'done'),
                    ("tennis_coach_id.employee_id", "=", self.env.user.employee_id.id)
                ], order='start_datetime desc')
            elif is_manager:
                print("ПОИСК НЕ ПО ТРЕНЕРАМ")
                trainings = self.env['tennis.training'].search([
                    ('center_id', '=', current_center_id),
                    ('client_ids', 'in', partner.id),
                    ('state', '=', 'done'),
                ], order='start_datetime desc')

            count = len(trainings)
            partner.training_count = count

            if count > 0:
                last_date = trainings[0].start_datetime.date()
                partner.last_training_date = last_date

                if count <= 2:
                    partner.client_status = 'new'
                elif (today - last_date).days <= 14:
                    partner.client_status = 'active'
                else:
                    partner.client_status = 'inactive'
            else:
                # ВАЖНО: Если тренировок в нашем центре НЕТ, то это НЕ "Новый" теннисный клиент.
                # Это вообще левый партнер для этого центра, зануляем его теннисный статус.
                partner.last_training_date = False
                partner.client_status = False

    def action_create_single_training(self):
        """Открывает пустую форму создания ОДНОЙ тренировки с предзаполненным клиентом"""
        self.ensure_one()
        return {
            'name': 'Новая тренировка',
            'type': 'ir.actions.act_window',
            'res_model': 'tennis.training',
            'view_mode': 'form',
            'target': 'current',  # Открываем на полный экран форму тренировки
            'context': {
                'default_client_ids': [(4, self.id)],  # Подставляем текущего клиента в M2M
                "default_training_type": "individual"
            }
        }