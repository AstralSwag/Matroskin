from flask import Flask, request
from jira import JIRA
from addict import Dict
import requests
import re

app = Flask(__name__)

JIRA_SERVER = "https://jira.it4retail.tech"
JIRA_AUTH = ""  # Тут должен быть токен Jira
OKDESK_AUTH = ""  # Тут должен быть токен Okdesk

jira = JIRA(server=JIRA_SERVER, token_auth=JIRA_AUTH)


@app.route('/jira_webhook', methods=['POST'])
def handle_jira_webhook():
    data = Dict(request.json)
    if data.issue_event_type_name == "issue_generic":
        print("Получено событие обновления задачи")
        send_request_to_okdesk(data)
    else:
        print("что то получено от jira")


def send_request_to_okdesk(data):
    # Сначала находим ключ задачи okdesk в description задачи в jira

    jira_issue_key = data.issue.key
    okdesk_issue_key = ""
    jira_issue = jira.issue(jira_issue_key, fields='description,status')
    pattern = r"https://zrp.okdesk.ru/issues/(\d+)"
    match = re.search(pattern, jira_issue.description)
    display_status = ""
    okdesk_status = ""
    if match:
        okdesk_issue_key = match.group(1)
    else:
        print("Не найден id задачи okdesk")

    # Определяем статус задачи Jira и шлём аналогичный в okdesk

    if jira.status == "3":
        display_status = "взял в работу"
        okdesk_status = "in_progress"
    elif jira.status == "10402":
        display_status = "закрыл задачу"
        okdesk_status = "completed"
    else:
        display_status = "Статус задачи не найден"

    route = f"https://zrp.okdesk.ru/api/v1/issues/{okdesk_issue_key}/statuses?api_token={OKDESK_AUTH}"
    body = {"code": okdesk_status}
    response = requests.post(route, json=body)
    print(response.status_code)


@app.route('/okdesk_webhook', methods=['POST'])
def handle_okdesk_webhook():
    data = Dict(request.json)
    if data.event.event_type == "new_ticket_status":
        print("Получено событие обновления задачи")
        send_request_to_jira(data)
    else:
        print("что то получено от okdesk")


def send_request_to_jira(data):
    okdesk_issue_key = data.issue.id
    status = data.event.new_status.name
    display_status = None
    jira_status = None

    # Для получения ключа задачи в Jira придётся сделать запрос к okdesk, т.к. ключ задачи хранится в комментарии

    jira_issue_key = ""
    route = f"https://zrp.okdesk.ru/api/v1/issues/{okdesk_issue_key}/comments?api_token={OKDESK_AUTH}"
    response = requests.get(route)

    if response.status_code == 200:
        pattern = r"Внешняя заявка https://jira.it4retail.tech/browse/(\w+-\d+)"
        for comment in response.json():
            content = comment.get("content", "")
            match = re.search(pattern, content)
            if match:
                jira_issue_key = match.group(1)
            else:
                print("Не найден ключ задачи Jira")
    else:
        print(response.status_code)

    # Определяем статус задачи в okdesk и шлём аналогичный в Jira

    if status == "В работе":
        display_status = "взял в работу"
        jira_status = "11"
    elif status == "Решена":
        display_status = "решил задачу"
        jira_status = "91"
    elif status == "Закрыта":
        display_status = "закрыл задачу"
    elif status == "Открыта":
        display_status = "вновь открыл"
        jira_status = "111"
    else:
        display_status = "Статус задачи не найден"

    route = f"https://jira.it4retail.tech/rest/api/latest/issue/{jira_issue_key}/transitions"
    body = {"transition": {"id": jira_status}}
    response = requests.post(route, json=body)
    print(response.status_code)


if __name__ == '__main__':
    app.run(debug=True)
