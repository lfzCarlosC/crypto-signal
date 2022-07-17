"""Notify a user via Gmail
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from notifiers.utils import NotifierUtils

class HotmailNotifier(NotifierUtils):
    """Class for handling gmail notifications
    """

    def __init__(self, username, password, destination_addresses):
        """Initialize GmailNotifier class

        Args:
            username (str): Username of the gmail account to use for sending message.
            password (str): Password of the gmail account to use for sending message.
            destination_addresses (list): A list of email addresses to notify.
        """

        self.logger = structlog.get_logger()
        self.smtp_server = 'smtp-mail.outlook.com:587'
        self.username = username
        self.password = password
        self.destination_addresses = ','.join(destination_addresses)


    @retry(stop=stop_after_attempt(3))
    def notify(self, message, title):
        """Sends the message.

        Args:
            message (str): The message to send.

        Returns:
            dict: A dictionary containing the result of the attempt to send the email.
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = title
        msg['From'] = 'From: %s\n' % self.username
        msg['To'] = 'To: %s\n' % self.destination_addresses

        part1 = MIMEText(message, 'html')
        msg.attach(part1)

        smtp_handler = smtplib.SMTP(self.smtp_server)
        smtp_handler.ehlo()
        smtp_handler.starttls()
        smtp_handler.login(self.username, self.password)
        addressList = self.destination_addresses.split(",")   
        result = smtp_handler.sendmail(self.username, addressList, msg.as_string().encode("utf-8"))
        smtp_handler.quit()
        return result
