"""Handles sending notifications via the configured notifiers
"""

import json
import structlog
from jinja2 import Template
import sys 
import extractCoins
import requests,json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from openpyxl import Workbook
from tenacity import retry, stop_after_attempt

from notifiers.twilio_client import TwilioNotifier
from notifiers.slack_client import SlackNotifier
from notifiers.discord_client import DiscordNotifier
from notifiers.gmail_client import GmailNotifier
from notifiers.hotmail_client import HotmailNotifier
from notifiers.webhook_client import WebhookNotifier
from notifiers.stdout_client import StdoutNotifier

from pytz import utc
from pytz import timezone
from datetime import datetime

class Notifier():
    """Handles sending notifications via the configured notifiers
    """

    exchangeMap = {"ftx": "ftx交易所",
                   "binance": "币安",
                   "bitfinex": "bitfinex交易所",
                   "huobi": "火币全球",
                   "bittrex": "bittrex",
                   "gateio": "gateio",
                   "okex": "ok交易所",
                   "zb": "zb交易所",
                   "kucoin": "kucoin交易所",
                   "coinex":"coinex交易所",
                   "hitbtc":"hitbtc交易所",
                   "poloniex":"poloniex交易所",
                   "bitget":"bitget"
                  }

    periodMap = {"15min":"15分钟","30min":"30分钟","1h":"1小时", "1d":"日线", "d":"日线", "3d":"3日", "4h":"4小时", "6h":"6小时", "12h":"12小时", "w":"周线", "M":"月线"}
    cst_tz = timezone('Asia/Shanghai')
    utc_tz = timezone('UTC')
    webhook = 'https://oapi.dingtalk.com/robot/send?access_token=1c46cb23a6562a4325bea9cf4225b11209e4b2fc4edd7d07e2ef404e15a86f0b'

    def __init__(self, notifier_config):
        """Initializes Notifier class

        Args:
            notifier_config (dict): A dictionary containing configuration for the notifications.
        """
        self.logger = structlog.get_logger()
        self.notifier_config = notifier_config
        self.last_analysis = dict()

        # 全币种扫描模式(-a)下，收集到的信号会缓存在这里，最后统一写入excel并发送邮件，
        # 而不是逐条推送到钉钉。
        self.scan_all_signals = list()

        enabled_notifiers = list()
        self.logger = structlog.get_logger()
        self.twilio_configured = self._validate_required_config('twilio', notifier_config)
        if self.twilio_configured:
            self.twilio_client = TwilioNotifier(
                twilio_key=notifier_config['twilio']['required']['key'],
                twilio_secret=notifier_config['twilio']['required']['secret'],
                twilio_sender_number=notifier_config['twilio']['required']['sender_number'],
                twilio_receiver_number=notifier_config['twilio']['required']['receiver_number']
            )
            enabled_notifiers.append('twilio')

        self.discord_configured = self._validate_required_config('discord', notifier_config)
        if self.discord_configured:
            self.discord_client = DiscordNotifier(
                webhook=notifier_config['discord']['required']['webhook'],
                username=notifier_config['discord']['required']['username'],
                avatar=notifier_config['discord']['optional']['avatar']
            )
            enabled_notifiers.append('discord')

        self.slack_configured = self._validate_required_config('slack', notifier_config)
        if self.slack_configured:
            self.slack_client = SlackNotifier(
                slack_webhook=notifier_config['slack']['required']['webhook']
            )
            enabled_notifiers.append('slack')

        self.gmail_configured = self._validate_required_config('gmail', notifier_config)
        if self.gmail_configured:
            self.gmail_client = GmailNotifier(
                username=notifier_config['gmail']['required']['username'],
                password=notifier_config['gmail']['required']['password'],
                destination_addresses=notifier_config['gmail']['required']['destination_emails']
            )
            enabled_notifiers.append('gmail')

        self.telegram_configured = self._validate_required_config('telegram', notifier_config)
#        if self.telegram_configured:
#            self.telegram_client = TelegramNotifier(
#                token=notifier_config['telegram']['required']['token'],
#                chat_id=notifier_config['telegram']['required']['chat_id'],
#                parse_mode=notifier_config['telegram']['optional']['parse_mode']
#            )
#           enabled_notifiers.append('telegram')
#
        self.webhook_configured = self._validate_required_config('webhook', notifier_config)
        if self.webhook_configured:
            self.webhook_client = WebhookNotifier(
                url=notifier_config['webhook']['required']['url'],
                username=notifier_config['webhook']['optional']['username'],
                password=notifier_config['webhook']['optional']['password']
            )
            enabled_notifiers.append('webhook')

        self.stdout_configured = self._validate_required_config('stdout', notifier_config)
        if self.stdout_configured:
            self.stdout_client = StdoutNotifier()
            enabled_notifiers.append('stdout')

        self.logger.info('enabled notifiers: %s', enabled_notifiers)


    def notify_all(self, new_analysis):
        """Trigger a notification for all notification options.

        Args:
            new_analysis (dict): The new_analysis to send.
        """

        self.notify_slack(new_analysis)
        self.notify_discord(new_analysis)
        self.notify_twilio(new_analysis)
        self.notify_gmail(new_analysis)
        self.notify_telegram(new_analysis)
        self.notify_webhook(new_analysis)
        self.notify_stdout(new_analysis)

    def notify_discord(self, new_analysis):
        """Send a notification via the discord notifier

        Args:
            new_analysis (dict): The new_analysis to send.
        """

        if self.discord_configured:
            message = self._indicator_message_templater(
                new_analysis,
                self.notifier_config['discord']['optional']['template']
            )
            if message.strip():
                self.discord_client.notify(message)


    def notify_slack(self, new_analysis):
        """Send a notification via the slack notifier

        Args:
            new_analysis (dict): The new_analysis to send.
        """

        if self.slack_configured:
            message = self._indicator_message_templater(
                new_analysis,
                self.notifier_config['slack']['optional']['template']
            )
            if message.strip():
                self.slack_client.notify(message)


    def notify_twilio(self, new_analysis):
        """Send a notification via the twilio notifier

        Args:
            new_analysis (dict): The new_analysis to send.
        """

        if self.twilio_configured:
            message = self._indicator_message_templater(
                new_analysis,
                self.notifier_config['twilio']['optional']['template']
            )
            if message.strip():
                self.twilio_client.notify(message)


    def notify_gmail(self, new_analysis, text):
        """Send a notification via the gmail notifier

        Args:
            new_analysis (dict): The new_analysis to send.
        """
        if self.gmail_configured:
            (message, title) = self._indicator_message_templater(
                new_analysis,
                text,
                self.notifier_config['gmail']['optional']['template']
            )
            message = message.strip()

            indicatorModes = sys.argv[3]
            if message != "":
                if(indicatorModes == 'easy'):
                    self.dingtalk(message, self.webhook)
                self.gmail_client.notify(message, title)

    def _is_scan_all_mode(self):
        """判断本次运行是否为全币种扫描模式(命令行参数中第4个参数为 -a)。

        Returns:
            bool: 是否为全币种扫描模式。
        """
        return bool(sys.argv[4:] and (sys.argv[4] == '-a'))

    def notify_dingtalk(self, new_analysis, text, market_pair):
        (message, title, period) = self._indicator_message_templater(
                new_analysis,
                text,
                self.notifier_config['gmail']['optional']['template']
            )

        if self._is_scan_all_mode():
            (exchange, period_cn, type_) = self.convertTitle()
            self._record_scan_all_signal(
                exchange=exchange,
                market_pair=market_pair,
                signal_type=text,
                period=period_cn,
                message=message,
                title=title,
                remark=""
            )
            return

        self.dingtalk(message + " - " + market_pair + " - " + title, self.webhook)

    def notify_harmonic_dingtalk(self, message, market_pair=None, signal_type=None):
        if not (message and message.strip()):
            return

        if self._is_scan_all_mode():
            (exchange, period_cn, type_) = self.convertTitle()
            self._record_scan_all_signal(
                exchange=exchange,
                market_pair=market_pair or "",
                signal_type=signal_type or "谐波形态",
                period=period_cn,
                message=message.strip(),
                title="",
                remark=message.strip()
            )
            return

        self.dingtalk(message.strip(), self.webhook)

    def _record_scan_all_signal(self, exchange, market_pair, signal_type, period, message, title, remark):
        """全币种扫描模式下，记录一条信号，等待统一写入excel。

        Args:
            exchange (str): 交易所中文名。
            market_pair (str): 交易对。
            signal_type (str): 信号类型/名称。
            period (str): 周期(中文，如 4小时/日线)。
            message (str): 信号正文消息。
            title (str): 信号标题(如有)。
            remark (str): 备注，谐波形态等额外细节信息放在这里。
        """
        self.scan_all_signals.append({
            'exchange': exchange,
            'market_pair': market_pair,
            'signal_type': signal_type,
            'period': period,
            'message': message,
            'title': title,
            'remark': remark,
            'time': self.getLocalizeTime()
        })

    def export_scan_all_to_excel_and_email(self, recipient='lfz.carlos@gmail.com', exchange=None, candle_period=None):
        """将本次全币种扫描模式下收集到的所有信号写入excel文档，并通过邮件发送给指定收件人。

        只有命令行参数中包含 -a (全币种扫描) 时才会被调用；若没有收集到任何信号，则不生成文件、不发邮件。

        Args:
            recipient (str): 收件人邮箱地址。
            exchange (str): 交易所(原始key，如 'binance')，用于邮件标题。
            candle_period (str): 本次扫描的candle_period(如 '1d'/'1w'/'1M'/'3d'/'12h')，用于邮件标题。
        """
        if not self.scan_all_signals:
            self.logger.info("Scan all mode: no signals collected, skipping excel export & email.")
            return

        try:
            filepath = self._write_scan_all_excel(self.scan_all_signals)
        except Exception as e:
            self.logger.warn("Failed to write scan-all excel file: %s", str(e))
            return

        exchange_cn = self.exchangeMap.get(exchange, exchange) if exchange else "未知交易所"
        period_label = candle_period if candle_period else "未知周期"
        subject = "全币种扫描信号汇总 - " + str(exchange_cn) + " - " + str(period_label)

        try:
            self._send_email_with_attachment(
                recipient=recipient,
                subject=subject,
                body="本次全币种扫描共发现 " + str(len(self.scan_all_signals)) + " 条信号，详见附件。",
                attachment_path=filepath
            )
        except Exception as e:
            self.logger.warn("Failed to send scan-all excel email: %s", str(e))

    def _write_scan_all_excel(self, signals):
        """将信号列表写入一个xlsx文件，每条信号一行，字段分列展示。

        Args:
            signals (list): _record_scan_all_signal 收集到的信号字典列表。

        Returns:
            str: 生成的excel文件路径。
        """
        wb = Workbook()
        sheet = wb.active
        sheet.title = "信号汇总"

        headers = ["交易所", "交易对", "信号类型", "周期", "标题", "信号内容", "备注", "记录时间"]
        sheet.append(headers)

        for signal in signals:
            sheet.append([
                signal.get('exchange', ''),
                signal.get('market_pair', ''),
                signal.get('signal_type', ''),
                signal.get('period', ''),
                signal.get('title', ''),
                signal.get('message', ''),
                signal.get('remark', ''),
                signal.get('time', '')
            ])

        widths = [14, 18, 28, 10, 30, 40, 60, 26]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[chr(64 + index)].width = width

        os.makedirs('/tmp/scan_all_exports', exist_ok=True)
        filename = "scan_all_signals_" + datetime.now(self.cst_tz).strftime('%Y%m%d_%H%M%S') + ".xlsx"
        filepath = os.path.join('/tmp/scan_all_exports', filename)
        wb.save(filepath)
        return filepath

    @retry(stop=stop_after_attempt(3))
    def _send_email_with_attachment(self, recipient, subject, body, attachment_path):
        """独立于 GmailNotifier 的邮件发送函数，使用 smtplib 通过 gmail 配置中的账号密码
        发送带附件的邮件。复用 notifier_config['gmail']['required'] 下的 username/password，
        SMTP 连接方式与 notifiers/gmail_client.py 保持一致(587端口 + starttls)。

        Args:
            recipient (str): 收件人邮箱地址。
            subject (str): 邮件标题。
            body (str): 邮件正文。
            attachment_path (str): 附件文件路径。
        """
        gmail_required = self.notifier_config.get('gmail', {}).get('required', {})
        username = gmail_required.get('username')
        password = gmail_required.get('password')

        if not username or not password:
            self.logger.warn("Gmail username/password not configured, cannot send scan-all excel email.")
            return

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = 'From: %s\n' % username
        msg['To'] = 'To: %s\n' % recipient
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        with open(attachment_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            'attachment; filename="%s"' % os.path.basename(attachment_path)
        )
        msg.attach(part)

        smtp_handler = smtplib.SMTP('smtp.gmail.com:587')
        smtp_handler.ehlo()
        smtp_handler.starttls()
        smtp_handler.login(username, password)
        result = smtp_handler.sendmail(username, [recipient], msg.as_string().encode("utf-8"))
        smtp_handler.quit()
        return result

    def dingtalk(self, msg, webhook):
        headers = {'Content-Type': 'application/json; charset=utf-8'}
        prefix = "ding "
        msg += prefix
        data = {'msgtype': 'text', 'text': {'content': msg}, 'at': {'atMobiles': [], 'isAtAll': False}}
        post_data = json.dumps(data)
        response = requests.post(webhook, headers=headers, data=post_data)
        return response.text

    def notify_telegram(self, new_analysis):
        """Send a notification via the telegram notifier

        Args:
            new_analysis (dict): The new_analysis to send.
        """

        if self.telegram_configured:
            message = self._indicator_message_templater(
                new_analysis,
                self.notifier_config['telegram']['optional']['template']
            )
            if message.strip():
                self.telegram_client.notify(message)


    def notify_webhook(self, new_analysis):
        """Send a notification via the webhook notifier

        Args:
            new_analysis (dict): The new_analysis to send.
        """

        if self.webhook_configured:
            for exchange in new_analysis:
                for market in new_analysis[exchange]:
                    for indicator_type in new_analysis[exchange][market]:
                        for indicator in new_analysis[exchange][market][indicator_type]:
                            for index, analysis in enumerate(new_analysis[exchange][market][indicator_type][indicator]):
                                analysis_dict = analysis['result'].to_dict(orient='records')
                                if analysis_dict:
                                    new_analysis[exchange][market][indicator_type][indicator][index] = analysis_dict[-1]
                                else:
                                    new_analysis[exchange][market][indicator_type][indicator][index] = ''

            self.webhook_client.notify(new_analysis)

    def notify_stdout(self, new_analysis):
        """Send a notification via the stdout notifier

        Args:
            new_analysis (dict): The new_analysis to send.
        """

        if self.stdout_configured:
            message = self._indicator_message_templater(
                new_analysis,
                self.notifier_config['stdout']['optional']['template']
            )
            if message.strip():
                self.stdout_client.notify(message)

    def _validate_required_config(self, notifier, notifier_config):
        """Validate the required configuration items are present for a notifier.

        Args:
            notifier (str): The name of the notifier key in default-config.json
            notifier_config (dict): A dictionary containing configuration for the notifications.

        Returns:
            bool: Is the notifier configured?
        """

        notifier_configured = True
        for _, val in notifier_config[notifier]['required'].items():
            if not val:
                notifier_configured = False
        return notifier_configured


    def convertTitle(self):
        temp = sys.argv[2].split("_")
        items = temp[0].split("/")
        exchange = items[len(items)-1];
        period = temp[1].split(".")[0];
        type = ""
        if temp[len(temp)-1].split(".")[0] == "contract" :
            type = "合约"

        return self.exchangeMap[exchange], self.periodMap[period], type

    def getLocalizeTime(self):
        utcnow = datetime.utcnow()
        utcnow = utcnow.replace(tzinfo=self.utc_tz)
        china = utcnow.astimezone(self.cst_tz)
        return "   发送时间: 时区: 亚洲/上海(GMT+08:00)  %s"%china.strftime('%Y-%m-%d %H:%M:%S')

    def _indicator_message_templater(self, new_analysis, text, template):
        """Creates a message from a user defined template

        Args:
            new_analysis (dict): A dictionary of data related to the analysis to send a message about.
            template (str): A Jinja formatted message template.

        Returns:
            str: The templated messages for the notifier.
        """
        if not self.last_analysis:
            self.last_analysis = new_analysis

        message_template = Template(template)
        new_message = str()

        # file = open(sys.argv[2], mode='r')

        if text == "":
            return "", ""

        (exchange, period, type) = self.convertTitle();
        title = '信号： '+ exchange + "  " + period + "    " + type + '\n\n'
        if len(sys.argv) > 5 and (sys.argv[5] == '-prefix'):
            prefix = self.notifier_config['gmail']['prefix']
            title = prefix + title
        new_message = new_message + text

        # Merge changes from new analysis into last analysis
        self.last_analysis = {**self.last_analysis, **new_analysis}
        return new_message, title, period