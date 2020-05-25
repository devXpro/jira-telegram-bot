from jira import JIRA
from jira.resources import Group
from jira.resources import Resource
from jira.resources import Role

from aiohttp import web
import ssl
import sys

import datetime
from telegramcalendar import create_calendar
import telebot
bot = telebot.TeleBot('1112147029:AAFdCrgVW7VNIvzrgsG7v7E5G7sPUII35fw');

WEBHOOK_LISTEN = "0.0.0.0"
WEBHOOK_PORT = 8443

# WEBHOOK_SSL_CERT = "/etc/letsencrypt/live/YOUR.DOMAIN/fullchain.pem"
# WEBHOOK_SSL_PRIV = "/etc/letsencrypt/live/YOUR.DOMAIN/privkey.pem"

app = web.Application()
# process only requests with correct bot token
async def handle(request):
    if request.match_info.get("token") == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)

app.router.add_post("/{token}/", handle)

jira_options = {'server': 'https://jira.ejaw.net'}
jira = JIRA(options=jira_options, basic_auth=("jira_bot", "1=20-c_78My/t*fd$8lu//YgutdIO"))
trusted_users = ['shroombratan', 'Pablito_Po', 'yaroslava_hr', 'maxliulchuk', 'aRe_10']
current_shown_dates = dict()
current_options = dict()
SECONDS_IN_7_HOURS = 25200
SECONDS_IN_9_HOURS = 32400


def send_reports(report_date, chat_id, no_report=False, busy=None):
    if no_report:
        msg = ['No report:\n']
    else:
        msg = [f'Daily reports for {report_date} :']
    users = jira.group_members('daily_reports')
    for user in users:
        issues = jira.search_issues(f'worklogDate={report_date} and worklogAuthor={user}', fields=('worklog',))
        if not no_report:
            if busy is not None:
                log_seconds = 0
            else:
                msg.append(f'\n{users[user]["fullname"]}')
                if not issues:
                    msg.append('has no report')
            log_issue = list()
            for issue in issues:
                log_time = ''
                for w in filter(lambda w: w.started[:10] == report_date, issue.fields.worklog.worklogs):
                    if busy is not None:
                        log_seconds += w.timeSpentSeconds
                    if log_time == '':
                        log_time = w.timeSpent
                    else:
                        log_time = log_time + ' + ' + w.timeSpent
                log_issue.append(f'/report_details_{issue.key.replace("-", "_")} {issue.key} - time: {log_time}')
            if busy is None:
                msg.extend(log_issue)
            elif busy:
                if log_seconds >= SECONDS_IN_9_HOURS:
                    msg.append(f'\n{users[user]["fullname"]}')
                    msg.extend(log_issue)
            else:
                if log_issue and log_seconds <= SECONDS_IN_7_HOURS:
                    msg.append(f'\n{users[user]["fullname"]}')
                    msg.extend(log_issue)
        else:
            if not issues:
                msg.append(f'{users[user]["fullname"]}')
    bot.send_message(chat_id, '\n'.join(msg))


@bot.message_handler(regexp=r"report_details")
def report_details_regex(message):
    message_list = message.text.split("_")
    message.text = f"{message_list[-2]}-{message_list[-1]}"
    get_report_details(message)


def get_report_details(message):
    current_issue = jira.issue(message.text)
    msg = [f'Report details for {message.text} :']
    for w in current_issue.fields.worklog.worklogs:
        msg.extend((f'{w.author.name} : {w.timeSpent}', w.comment, '----------------------------'))
    bot.send_message(message.from_user.id, '\n'.join(msg))


@bot.message_handler(func=lambda message: True, content_types=['text'])
def start(message):
    if message.text == '/start':
        if message.from_user.username in trusted_users:
            markup = telebot.types.InlineKeyboardMarkup()
            markup.row(telebot.types.InlineKeyboardButton(text="rep_busy", callback_data="rep_busy"),
                telebot.types.InlineKeyboardButton(text="rep_lazy", callback_data="rep_lazy"))
            markup.row(telebot.types.InlineKeyboardButton(text="rep_empty", callback_data="rep_empty"),
                telebot.types.InlineKeyboardButton(text="daily_report", callback_data="daily_report"))
            markup.row(telebot.types.InlineKeyboardButton(text="report_details", callback_data="report_details"))

            bot.send_message(message.chat.id, 'Чаво нада, хазяин?', reply_markup=markup)
        else:
            bot.send_message(message.from_user.id, "Наш Гендальф тебя дальше не пустит" +
                             b'\xF0\x9F\x9A\xB7'.decode('utf-8'))
    else:
        bot.send_message(message.from_user.id, 'Напиши /start')      

@bot.callback_query_handler(lambda query: query.data == "report_details")
def options_callback(query):
    bot.send_message(query.message.chat.id, "Введи номер таски")
    bot.register_next_step_handler(query.message, get_report_details)

@bot.callback_query_handler(lambda query: query.data in ["rep_busy", "rep_lazy", "rep_empty", "daily_report"])
def options_callback(query):
    chat_id = query.message.chat.id
    current_options[chat_id] = query.data
    now = datetime.datetime.now()
    date = (now.year, now.month)
    current_shown_dates[chat_id] = date
    markup = create_calendar(now.year, now.month)
    bot.send_message(query.message.chat.id, "Пожалуйста, выберите дату", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: 'DAY' in call.data[0:13])
def handle_day_query(call):
    chat_id = call.message.chat.id
    saved_date = current_shown_dates.get(chat_id)
    last_sep = call.data.rfind(';') + 1

    if saved_date is not None:
        day = call.data[last_sep:]
        if len(day) == 1:
            day = f'0{day}'
        month = saved_date[1]
        if month < 10:
            month = f'0{month}'

        date = f'{saved_date[0]}-{month}-{day}'
        option = current_options[chat_id]
        if option == 'daily_report':
            send_reports(date, chat_id, no_report=False)
        elif option == 'rep_empty':
            send_reports(date, chat_id, no_report=True)
        elif option == 'rep_busy':
            send_reports(date, chat_id, no_report=False, busy=True)
        elif option == 'rep_lazy':
            send_reports(date, chat_id, no_report=False, busy=False)
        bot.answer_callback_query(call.id, text="")

@bot.callback_query_handler(func=lambda call: 'MONTH' in call.data)
def handle_month_query(call):
    info = call.data.split(';')
    month_opt = info[0].split('-')[0]
    year, month = int(info[1]), int(info[2])
    chat_id = call.message.chat.id

    if month_opt == 'PREV':
        month -= 1

    elif month_opt == 'NEXT':
        month += 1

    if month < 1:
        month = 12
        year -= 1

    if month > 12:
        month = 1
        year += 1

    date = (year, month)
    current_shown_dates[chat_id] = date
    markup = create_calendar(year, month)
    bot.edit_message_text("Please, choose a date", call.from_user.id, call.message.message_id, reply_markup=markup)

# context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
# context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

# start aiohttp server (our bot)
web.run_app(
    app,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    # ssl_context=context,
)

