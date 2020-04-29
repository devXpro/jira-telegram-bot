from jira import JIRA
from jira.resources import Group
from jira.resources import Resource
from jira.resources import Role

from aiohttp import web
import ssl
import sys

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

def get_report_issues(block_num,block_size,chosen_date):
    while True:
        jql = 'worklogDate = ' + chosen_date
        start_idx = block_num * block_size
        if block_num == 0:
            issues = jira.search_issues(jql, start_idx, block_size)
        else:
            more_issue = jira.search_issues(jql, start_idx, block_size)
            if len(more_issue)>0:
                for x in more_issue:
                    issues.append(x)
            else:
                break
        if len(issues) == 0:
            break
        block_num += 1
    return issues

def get_users(block_num,block_size):
    while True:
        start_idx = block_num * block_size
        if block_num == 0:
            users = jira.search_users("@",start_idx,block_size,True,False)
        else:
            more_users =  jira.search_users("@",start_idx,block_size,True,False)
            if len(more_users)>0:
                for x in more_users:
                    users.append(x)
            else:
                break
        if len(users) == 0:
            break
        block_num += 1
    return users

def print_users(users):
    print(len(users))
    i = 0
    for user in users:
        i += 1
        print(i, ' %s %s' % (user, users[str(user)]['fullname']))

def report(issues, report_date, report_users, message):
    msg = 'Daily reports for ' + report_date + ' :'
    bot.send_message(message.from_user.id, msg)

    failed_users = ['','']
    failed_users.clear()
    for r_user in report_users:
        log_time = ''
        for issue in issues:
            if issue.raw['fields']['reporter']['name'] == r_user:
                current_issue = jira.issue(issue.key)
                current_key = issue.key
                for w in current_issue.fields.worklog.worklogs:
                    if w.author.displayName == report_users[str(r_user)]['fullname']:
                        if log_time == '':
                            log_time = w.timeSpent
                        else:
                            log_time = log_time + ' + ' + w.timeSpent
        if log_time != '':
            msg = report_users[str(r_user)]['fullname'] + ' - ' + current_key + ' - time: ' + log_time
            bot.send_message(message.from_user.id, msg)
        else:
            failed_users.append(report_users[str(r_user)]['fullname'])

    bot.send_message(message.from_user.id,'----------------------------------------------------')
    if len(failed_users) > 0:
        bot.send_message(message.from_user.id,'Users without reports:')
        for f in failed_users:
            bot.send_message(message.from_user.id,f)

def report_details(issue_key, message):
    current_issue = jira.issue(issue_key)
    msg = [f'Report details for {issue_key} :']
    for w in current_issue.fields.worklog.worklogs:
        msg.extend((f'{w.author.name} : {w.timeSpent}', w.comment, '----------------------------'))
    bot.send_message(message.from_user.id, '\n'.join(msg))


@bot.message_handler(func=lambda message: True, content_types=['text'])
def start(message):
    if message.text == '/start':
        if message.from_user.username in trusted_users:
            bot.send_message(message.from_user.id, "Ок, поехали, тебе я доверяю")
            bot.send_message(message.from_user.id, "Чаво нада, хазяин?")
            bot.register_next_step_handler(message, get_command)
        else:
            bot.send_message(message.from_user.id, "Наш Гендальф тебя дальше не пустит" +
                             b'\xF0\x9F\x9A\xB7'.decode('utf-8'))
    else:
        bot.send_message(message.from_user.id, 'Напиши /start')      

def get_command(message):
    if 'daily_report' in message.text and message.text != 'daily_report':
        r_date = message.text.strip()[-10:]
        report_users = jira.group_members('daily_reports')
        issues = get_report_issues(0,100,r_date)
        report(issues, r_date, report_users, message)
        bot.register_next_step_handler(message, get_command)

    elif message.text == 'my_id':
        bot.send_message(message.from_user.id, message.from_user.id)
        bot.register_next_step_handler(message, get_command)
                
    elif message.text == 'daily_report':
        bot.send_message(message.from_user.id, "окей, допустим, а на какую дату?")
        bot.register_next_step_handler(message, get_date_for_report)

    elif 'report_details' in message.text:
        r_key = message.text.strip()
        r_key = r_key[14:]
        r_key = r_key.strip()
        if len(r_key) > 0:
            report_details(r_key, message)
        else:
            bot.send_message(message.from_user.id, "В запросе нет ключа таски. Давай попробуем ещё раз - что ты от меня хочешь?")
            bot.register_next_step_handler(message, get_command)
        
    elif message.text == '/help':
        msg = '''На данный момент я умею:
        daily_report
        daily_report YYYY-MM-DD
        report_details *ключ таски*'''
        bot.send_message(message.from_user.id, msg)
        bot.register_next_step_handler(message, get_command)
        
    else:
        bot.send_message(message.from_user.id, "хмммм, не знаю таких команд, попробуй ещё разок")
        bot.send_message(message.from_user.id, "или /help попробуй @_@")
        bot.register_next_step_handler(message, get_command)

def get_date_for_report(message):
    if len(message.text) == 10 and message.text.count('-') == 2 and message.text[0:4].isnumeric()and message.text[5:7].isnumeric()and message.text[8:10].isnumeric():
        r_date = message.text[0:10]
        report_users = jira.group_members('daily_reports')
        issues = get_report_issues(0,100,r_date)
        report(issues, r_date, message)
        bot.register_next_step_handler(message, get_command)
    else:
        bot.send_message(message.from_user.id, "либо это не дата, либо формат неправильный, нужно daily_report YYYY-MM-DD")
        bot.send_message(message.from_user.id, "или /help попробуй @_@")
        bot.register_next_step_handler(message, get_command)


# context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
# context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

# start aiohttp server (our bot)
web.run_app(
    app,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    # ssl_context=context,
)

