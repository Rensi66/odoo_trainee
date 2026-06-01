from datetime import datetime, timedelta
import pytz
import requests

from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..config import BOT_TOKEN


class TennisTraining(models.Model):
    _name = 'tennis.training'
    _description = 'Tennis Training'
    _inherits = {'calendar.event': 'event_id'}
    _inherit = ["mail.thread"]

    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_approve', 'To approve'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('to_approve_cancel', 'To approve cancel'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')
    training_type = fields.Selection([
        ("individual", "Individual"),
        ("split", "Split"),
        ("group", "Group"),
    ], required=True, default='group', string="Training Type")
    court = fields.Selection(selection="_get_court_selection", string="Court", required=True)
    start_datetime = fields.Datetime(string="Training Start", required=True)
    duration = fields.Integer(string="Duration", required=True, default=1)
    end_datetime = fields.Datetime(string="Training End", compute="_compute_end_time", store=True)
    price_center = fields.Monetary(string="Center Price", compute="_get_price", store=True, aggregator=False)
    price_coach = fields.Monetary(string="Coach Price", compute="_get_price", aggregator="sum", store=True)
    price_total = fields.Monetary(string="Total Price", compute="_get_price", store=True, aggregator=False)
    display_coach = fields.Char(string="Coach", compute="_compute_display_fields")
    display_clients = fields.Char(string="Clients", compute="_compute_display_fields")
    display_name_calendar = fields.Char(compute="_compute_display_name_calendar")
    is_reminder_sent = fields.Boolean(string="Reminder Sent", default=False)
    is_own_training = fields.Boolean(
        compute="_compute_own_training",
        search="_search_own_training",
        string="Is Own Training"
    )

    busy_courts_ids = fields.Many2many("tennis.training", compute="_compute_busy_courts", string="Busy Courts")
    event_id = fields.Many2one('calendar.event', string='Event', required=True, ondelete='cascade')
    tennis_coach_id = fields.Many2one("tennis.coach", required=True, ondelete="cascade")
    client_ids = fields.Many2many("res.partner", "tennis_client_training", "training_id", "partner_id", required=True)
    center_id = fields.Many2one("tennis.center", required=True, default=lambda self: self.env.user.employee_id.center_id.id, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)

    @api.depends('is_own_training', 'training_type', 'display_coach')
    def _compute_display_name_calendar(self):
        for record in self:
            if record.is_own_training:
                # Если своя — пишем как есть: "Групповая (Имя Тренера)" или оригинальное имя
                type_label = dict(self._fields['training_type'].selection).get(record.training_type, '')
                record.display_name_calendar = f"{type_label} — {record.display_coach}"
            else:
                # Если чужая — жесткая заглушка для сетки календаря
                record.display_name_calendar = "Занято (Чужая тренировка)"

    @api.depends("tennis_coach_id")
    def _compute_own_training(self):
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        # Заранее находим ID карточки тренера, которая принадлежит текущему пользователю
        current_coach = self.env["tennis.coach"].search([
            ("employee_id", "=", self.env.user.employee_id.id)
        ], limit=1)
        current_coach_id = current_coach.id if current_coach else False

        for record in self:
            # Защита от NewId при создании записи в календаре
            if not record.tennis_coach_id:
                record.is_own_training = True
                continue

            # Сравниваем ID карточек тренеров напрямую — это не требует прав на модель hr.employee!
            if is_owner or is_manager or record.tennis_coach_id.id == current_coach_id:
                record.is_own_training = True
            else:
                record.is_own_training = False

    def _search_own_training(self, operator, value):
        if operator not in ('=', '!='):
            raise ValueError("Unsupported operator for is_own_training search")

        # Определяем, ищем мы "свои" (True) или "чужие" (False)
        positive = (operator == '=' and value) or (operator == '!=' and not value)

        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")

        # Менеджеры и владельцы видят вообще всё как "своё"
        if is_owner or is_manager:
            return [] if positive else [('id', '=', False)]

        # Для обычного тренера ищем его карточку
        current_coach = self.env["tennis.coach"].search([
            ("employee_id", "=", self.env.user.employee_id.id)
        ], limit=1)

        if current_coach:
            return [('tennis_coach_id', '=', current_coach.id)] if positive else [
                ('tennis_coach_id', '!=', current_coach.id)]

        # Если это какой-то левый юзер без карточки тренера
        return [('id', '=', False)] if positive else []

    @api.depends('tennis_coach_id', 'client_ids', 'is_own_training')
    def _compute_display_fields(self):
        """Динамически скрывает данные чужих тренировок от тренеров"""
        for record in self:
            if record.is_own_training:
                # Если тренировка наша — берем оригинальные данные (с проверкой на пустоту)
                record.display_coach = record.tennis_coach_id.name if record.tennis_coach_id else ""
                record.display_clients = ", ".join(record.client_ids.mapped("name")) if record.client_ids else ""
            else:
                # Читаем имя тренера через sudo(), так как это чужая запись
                sudo_record = record.sudo()
                coach_name = sudo_record.tennis_coach_id.name if sudo_record.tennis_coach_id else "Чужой тренер"

                record.display_coach = f"Занято"
                record.display_clients = "Конфиденциально"

    @api.constrains("client_ids")
    def _check_balance(self):
        for record in self:
            for client in record.client_ids:
                if client.tennis_balance < 0:
                    raise ValidationError(f"Client {client.name} has negative balance")

    @api.depends("start_datetime", "court", "center_id")
    def _compute_busy_courts(self):
        for record in self:
            if not record.start_datetime or not record.court:
                record.busy_courts_ids = self.env["tennis.training"]
            else:
                user_tz = self.env.user.tz or 'UTC'
                local_tz = pytz.timezone(user_tz)

                start_utc = pytz.utc.localize(record.start_datetime)
                start_local = start_utc.astimezone(local_tz)

                local_date = start_local.date()
                day_start_local = datetime.combine(local_date, datetime.min.time())
                day_end_local = datetime.combine(local_date, datetime.max.time())

                day_start_with_tz = local_tz.localize(day_start_local)
                day_end_with_tz = local_tz.localize(day_end_local)

                day_start_utc = day_start_with_tz.astimezone(pytz.utc).replace(tzinfo=None)
                day_end_utc = day_end_with_tz.astimezone(pytz.utc).replace(tzinfo=None)

                domain = [
                    ("center_id", "=", record.center_id.id),
                    ("start_datetime", ">=", day_start_utc),
                    ("start_datetime", "<=", day_end_utc),
                    ("court", "=", record.court),
                    ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
                ]

                if record.id:
                    current_id = record._origin.id or record.id
                    domain.append(("id", "!=", current_id))

                # Теперь поиск вернет ВСЕ записи центра, так как мы исправим правила доступа ниже
                record.busy_courts_ids = self.env["tennis.training"].search(domain, order="start_datetime")

    @api.constrains("court", "tennis_coach_id", "client_ids", "start_datetime", "duration")
    def check_unique_of_training_details(self):
        for record in self:
            if not record.create_date or (record.state == 'draft'):
                present_datetime = fields.Datetime.now()
                if record.start_datetime < present_datetime:
                    raise ValidationError("The training cannot be scheduled in the past.")
            overlapping_court = self.env["tennis.training"].search(domain=[
                ("id", "!=", record.id),
                ("center_id", "=", record.center_id.id),
                ("end_datetime", ">", record.start_datetime),
                ("start_datetime", "<", record.end_datetime),
                ("court", "=", record.court),
                ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
            ], limit=1)
            if overlapping_court:
                raise ValidationError("This court is already occupied")

            overlapping_coach = self.env["tennis.training"].search(domain=[
                ("id", "!=", record.id),
                ("tennis_coach_id", "=", record.tennis_coach_id.id),
                ("center_id", "=", record.center_id.id),
                ("end_datetime", ">", record.start_datetime),
                ("start_datetime", "<", record.end_datetime),
                ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
            ], limit=1)
            if overlapping_coach:
                raise ValidationError("This coach is already taken")

            overlapping_client = self.env["tennis.training"].search(domain=[
                ("id", "!=", record.id),
                ("client_ids", "in", record.client_ids.ids),
                ("center_id", "=", record.center_id.id),
                ("end_datetime", ">", record.start_datetime),
                ("start_datetime", "<", record.end_datetime),
                ("state", "in", ["to_approve", "confirmed", "in_progress", "done", "to_approve_cancel"])
            ])
            if overlapping_client:
                busy_clients = overlapping_client.client_ids & record.client_ids
                clients = ", ".join(busy_clients.mapped("name"))
                raise ValidationError(f"This clients {clients} is already taken")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list=fields_list)

        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        if is_coach and not (is_owner or is_manager):
            # Ищем тренера по его связи с employee_id текущего пользователя
            coach = self.env["tennis.coach"].search([
                ("employee_id", "=", self.env.user.employee_id.id)
            ], limit=1)

            if coach:
                res["tennis_coach_id"] = coach.id

        return res

    @api.model
    def get_views(self, views, options=None):
        res = super().get_views(views=views, options=options)

        if "form" in res["views"]:
            is_owner = self.env.user.has_group("tennis.group_tennis_owner")
            is_manager = self.env.user.has_group("tennis.group_tennis_manager")
            is_coach = self.env.user.has_group("tennis.group_tennis_coach")

            doc = etree.fromstring(res["views"]["form"]["arch"])

            # === ЛОГИКА ДЛЯ ПОЛЯ КЛУБА (center_id) ===
            if is_owner:
                # Владелец: полное редактирование, видит только свои центры
                for node in doc.xpath("//field[@name='center_id']"):
                    node.attrib.pop("readonly", None)
                    node.set("modifiers", '{"readonly": false}')
                    node.set("domain", f"[('id', 'in', {self.env.user.center_ids.ids})]")

            elif is_manager:
                # Менеджер: не может менять центр (readonly), жесткий домен на его родной центр
                for node in doc.xpath("//field[@name='center_id']"):
                    node.set("readonly", "1")
                    node.set("modifiers", '{"readonly": true}')
                    node.set("domain", f"[('id', '=', {self.env.user.employee_id.center_id.id})]")

            else:
                # Чистый тренер или рядовой персонал: центр менять нельзя
                for node in doc.xpath("//field[@name='center_id']"):
                    node.set("readonly", "1")
                    node.set("modifiers", '{"readonly": true}')

            # === ЛОГИКА ДЛЯ ПОЛЯ ТРЕНЕРА (tennis_coach_id) ===
            # Владелец (is_owner) и Менеджер (is_manager) сюда НЕ заходят.
            # Им поле доступно для редактирования — они могут назначать любых тренеров на корт.
            if is_coach and not (is_owner or is_manager):
                # Только чистый тренер намертво привязывается к своей карточке
                for node in doc.xpath("//field[@name='tennis_coach_id']"):
                    node.set("readonly", "1")
                    node.set("options", "{'no_open': 'True'}")

            res["views"]["form"]["arch"] = etree.tostring(doc)

        return res

    @api.depends("start_datetime", "duration")
    def _compute_end_time(self):
        for record in self:
            record.end_datetime = record.start_datetime + timedelta(hours=record.duration)

    @api.depends(
        "training_type",
        "duration",
        "tennis_coach_id.individual", "tennis_coach_id.split", "tennis_coach_id.group",
        "center_id.individual", "center_id.split", "center_id.group"
    )
    def _get_price(self):
        for record in self:
            # Если хотя бы одного ключевого поля нет — строго пишем нули
            if not record.training_type or not record.duration or not record.tennis_coach_id or not record.center_id:
                record.price_center = 0.0
                record.price_coach = 0.0
                record.price_total = 0.0
                continue

            # Безопасно вытягиваем ставки (если поля в связанных моделях не заполнены, вернет 0.0)
            center_rate = getattr(record.center_id, record.training_type, 0.0) or 0.0
            coach_rate = getattr(record.tennis_coach_id, record.training_type, 0.0) or 0.0

            # Финальный расчет
            record.price_center = record.duration * center_rate
            record.price_coach = record.duration * coach_rate
            record.price_total = record.price_center + record.price_coach

    @api.onchange("center_id")
    def _onchange_center_id(self):
        """Сбрасываем зависимые поля при смене центра"""
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        # Сбрасываем тренера только для менеджеров и владельцев.
        # Чистому тренеру оставляем его карточку, которую подкинул default_get
        if not (is_coach and not (is_owner or is_manager)):
            self.tennis_coach_id = False

        self.court = False
        return {'domain': {'court': []}}

    def _get_court_selection(self):
        """
        Теперь этот метод вызывается при рендеринге поля,
        используя текущий center_id записи (self)
        """
        # Если record уже существует, берем center_id из него
        center = self.center_id

        # Если это новая запись, может быть еще не сохранена,
        # тогда берем из текущего пользователя как fallback
        if not center:
            user_center_id = self.env.user.employee_id.center_id.id or (
                self.env.user.center_ids[:1].id if self.env.user.center_ids else False)
            center = self.env["tennis.center"].browse(user_center_id)

        if center and center.court > 0:
            return [(f"court_{i}", f"Court {i}") for i in range(1, center.court + 1)]

        return [("default_court", "Court 1")]


    @api.onchange("training_type", "client_ids")
    def _onchange_check_count_of_clients(self):
        if self.training_type == "individual" and len(self.client_ids) > 1:
            return {"warning": {
                "title": "Limit the number of clients",
                "message": "Individual training can have only one client. Change count of clients or the type of training"
            }}
        elif self.training_type == "split" and len(self.client_ids) > 2:
            return {"warning": {
                "title": "Limit the number of clients",
                "message": "Split training must have only two clients. Change count of clients or the type of training"
            }}
        elif self.training_type == "group" and len(self.client_ids) > 5:
            return {"warning": {
                "title": "Limit the number of clients",
                "message": "Group training must have max 5 clients. Change count of clients or the type of training"
            }}

    @api.constrains('training_type', "client_ids")
    def _check_count_of_clients(self):
        for record in self:
            if record.training_type == "individual" and len(self.client_ids) != 1:
                raise ValidationError("Individual training can have only one client")
            elif record.training_type == "split" and len(record.client_ids) != 2:
                raise ValidationError("Split training must have only two clients")
            elif record.training_type == "group" and (len(record.client_ids) < 3 or len(record.client_ids) > 5):
                raise ValidationError("Group training must have at least 3 clients and max 5 clients")

    @api.constrains("duration", "start_datetime")
    def _check_duration(self):
        for record in self:
            # Защита от пустых значений
            if not record.duration or not record.start_datetime:
                continue

            # 1. Минимальная длительность проверяется всегда, независимо от графика центра
            if record.duration < 1:
                raise ValidationError("Min duration cannot be less than 1")

            if record.center_id.start_time == 0.0 and record.center_id.end_time == 0.0:
                continue

            center_tz_name = record.center_id.tz or 'UTC'
            center_tz = pytz.timezone(center_tz_name)

            # Локализуем UTC-время из базы и переводим в часовой пояс центра
            start_utc = pytz.utc.localize(record.start_datetime)
            start_local = start_utc.astimezone(center_tz)

            hour = start_local.hour
            minute = start_local.minute
            float_time = hour + (minute / 60.0)

            if record.center_id.end_time == 0.0:
                end = 24.0
            else:
                end = record.center_id.end_time

            # 4. Проверки для центров с ограниченным графиком работы
            if float_time < record.center_id.start_time:
                raise ValidationError("Start time can`t be less than center start time")

            if float_time + record.duration > end:
                raise ValidationError("End time must be less than center end time")

    def action_confirm(self):
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        if is_coach and not(is_owner or is_manager):
            self.write({"state": "to_approve"})

            template = self.env.ref("tennis.tennis_training_approve_template")

            body_html = template._render_field("body_html", [self.id])[self.id]
            subject = template._render_field("subject", [self.id])[self.id]
            partner_ids = [self.center_id.sudo().manager_id.user_id.partner_id.id]

            self.message_post(
                body=body_html,
                subject=subject,
                partner_ids=partner_ids,
                message_type="comment",
                subtype_xmlid="mail.mt_comment"
            )
        else:
            self.write({"state": "confirmed"})
            self.sudo().client_ids.write({"is_tennis_client": True})

    def action_cancel(self):
        is_owner = self.env.user.has_group("tennis.group_tennis_owner")
        is_manager = self.env.user.has_group("tennis.group_tennis_manager")
        is_coach = self.env.user.has_group("tennis.group_tennis_coach")

        if is_coach and not(is_owner or is_manager):
            self.action_confirm()
            self.write({"state": "to_approve_cancel"})
        else:
            self.write({"state": "cancel"})


    def accept_training(self):
        if self.state == "to_approve":
            self.write({"state": "confirmed"})
            self.sudo().client_ids.write({"is_tennis_client": True})
        elif self.state == "to_approve_cancel":
            self.write({"state": "cancel"})

    def cancel_training(self):
        if self.state == "to_approve":
            self.write({"state": "cancel"})
        elif self.state == "to_approve_cancel":
            self.write({"state": "confirmed"})

    def write(self, vals):
        new_datetime = []
        for record in self:
            if "start_datetime" in vals:
                if record.state == "confirmed":
                    new_datetime.append(self)

        res = super().write(vals)

        for record in new_datetime:
            record.action_confirm()

        return res

    @api.model
    def _update_training_state(self):
        records = self.env["tennis.training"].search([("state", "in", ["confirmed", "in_progress"])])

        present_datetime = fields.Datetime.now()

        done_records = self.env["tennis.training"]
        in_progress_records = self.env["tennis.training"]
        for record in records:
            if record.end_datetime <= present_datetime:
                done_records |= record
            elif record.start_datetime <= present_datetime:
                in_progress_records |= record

        done_records.write({"state": "done"})
        for done_record in done_records:
            for client in done_record.client_ids:
                client.write({"tennis_balance": client.tennis_balance - done_record.price_total})
        in_progress_records.write({"state": "in_progress"})

    @api.model
    def _remind_about_training(self):
        print("НАЧАЛО ОТПРАВКИ")
        present_datetime = fields.Datetime.now()
        reminder_time = 1
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        trainings = self.env["tennis.training"].search([("start_datetime", "<=", present_datetime + timedelta(hours=reminder_time)),
                                                        ("start_datetime", ">=", present_datetime),
                                                        ("is_reminder_sent", "=", False),
                                                        ("state", "=", "confirmed"),])


        for training in trainings:
            raw_court = training.court or "default_court"
            court_label = raw_court
            if "court_" in raw_court:
                court_label = f"Court {raw_court.replace('court_', '')}"

            for client in training.client_ids:

                related_user = client.user_ids[:1]

                client_tz = related_user.tz or self.env.user.tz or "UTC"

                local_tz = pytz.timezone(client_tz)
                local_start_datetime = pytz.utc.localize(training.start_datetime).astimezone(local_tz).replace(
                    tzinfo=None)
                time_str = local_start_datetime.strftime('%H:%M')

                message = (
                    f"Напоминание о тренировке!\n"
                    f"Ваша тренировка начнется в {time_str} ч.\n"
                    f"Адрес: {training.center_id.address}\n"
                    f"Корт: {court_label}"
                )

                if client.tg_chat_id:
                    payload = {
                        "chat_id": client.tg_chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    }
                    try:
                        requests.post(url, json=payload, timeout=5)
                    except Exception as e:
                        continue

        trainings.write({"is_reminder_sent": True})

    def action_tennis_recurring_training(self):
        return {
            "name": "Recurring training",
            "type": "ir.actions.act_window",
            "res_model": "tennis.recurring.training",
            "view_mode": "form",
            "target": "current"
        }



