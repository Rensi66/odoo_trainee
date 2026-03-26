from odoo import models, fields, api


class Lesson1MainModel(models.Model):
    _name = "lesson1.main.model"

    text = fields.Text(string="Текстовое поле")
    check1 = fields.Boolean(string="Test 1", default=False)
    check2 = fields.Boolean(string="Test 2", default=False)
    check_all = fields.Boolean(string="Select all", default=False)
    select1 = fields.Selection([
        ('1', '1'),
        ('2', '2'),
        ('3', '3')
    ])
    select2 = fields.Selection([
        ('1', '4'),
        ('2', '5'),
        ('3', '6')
    ])
    boolean1 = fields.Boolean(string="1")
    boolean2 = fields.Boolean(string="2")
    boolean3 = fields.Boolean(string="3")
    boolean4 = fields.Boolean(string="4")
    boolean5 = fields.Boolean(string="5")
    boolean6 = fields.Boolean(string="6")
    boolean7 = fields.Boolean(string="7")
    boolean8 = fields.Boolean(string="8")
    boolean9 = fields.Boolean(string="9")

    int_field = fields.Integer(string="Add your age")
    float_field = fields.Float(string="10 / 4")
    currency_id = fields.Many2one('res.currency', string="Currency")
    money_field = fields.Monetary(string="Add your salary", currency_field="currency_id")
    date_field = fields.Date(string="Add your date")
    date_time_field = fields.Datetime(string="Add your date and time")
    file_field = fields.Binary(string="Add your file")
    image_field = fields.Image(string="Add your image")

    is_company = fields.Boolean(string="Is Company")


    @api.onchange('check_all')
    def _onchange_check_all(self):
        if self.check_all:
            self.check1 = True
            self.check2 = True
        else:
            if self.check1 and self.check2:
                self.check1 = False
                self.check2 = False


    @api.onchange("check1", "check2")
    def _onchange_check1_check2(self):
        text_string = self.text if self.text else ""
        label1 = f"[{self._fields['check1'].string}] "
        label2 = "{" + f"{self._fields['check2'].string}" + "} "

        if self.check1 and label1 not in text_string:
            self.text = text_string + label1
            text_string = self.text
        elif not self.check1:
            if label1 in text_string:
                self.text = self.text.replace(label1, '')
                text_string = self.text


        if self.check2 and label2 not in text_string:
            self.text = text_string + label2
        elif not self.check2:
            if label2 in text_string:
                self.text = self.text.replace(label2, '')

        if self.check1 and self.check2:
            self.check_all = True
        else:
            self.check_all = False


    def action_create_company(self):
        return {
            "name": "Create Partner",
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "view_mode": "form",
            "target": "new",
            "context": {"default_name": self.text,
                        "default_is_company": self.is_company}
        }

    def action_create_partner(self):
        return {
            "name": "Создать через визард",
            "type": "ir.actions.act_window",
            "res_model": "create.partner",
            "view_mode": "form",
            "target": "new",
        }


class CreatePartner(models.TransientModel):
    _name="create.partner"

    name = fields.Char(string="Partner Name", required=True)
    is_company = fields.Boolean(string="Is Company")


    def action_apply(self):
        partner = self.env['res.partner'].create({
            'name': self.name,
            'is_company': self.is_company,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": partner.id,
            "view_mode": "form",
            "target": "current",
        }