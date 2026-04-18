import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";

class MyActionComponent extends Component {
    static template = xml`
        <div class="o_action_manager p-5">
            <h1 class="text-primary">Хэй, это мой Client Action!</h1>
            <p>Тут можно нарисовать вообще всё, что угодно на JS.</p>
            <button class="btn btn-success" t-on-click="() => alert('Работает!')">Нажми меня</button>
        </div>
    `;
}

registry.category("actions").add("my_custom_client_ac   tion_tag", MyActionComponent);