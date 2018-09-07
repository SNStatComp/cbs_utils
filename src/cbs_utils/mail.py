import smtplib
import base64
import sspi
import logging
from abc import ABC, abstractmethod
from email.mime.text import MIMEText

SMTP_EHLO_OKAY = 250
SMTP_AUTH_CHALLENGE = 334
SMTP_AUTH_OKAY = 235

def asbase64(msg):
    #return string.replace(base64.encodebytes(msg), '\n', '') Python 2.7 approach
    return base64.encodebytes(msg).decode('utf8').replace('\n','')


class EmailFormat(ABC):
    def __init__(self):
        self.body = ''
        self.subject = ''
        self.to_adress = []
        self.from_adress = ''

    def add_to_recipients(self, to):
        if isinstance(to, str):
            self.to_adress.append(to)
        else:
            # normally an addition of list with the iterable would suffice, but if a custom iterable is given this might
            # not be handled correctly. Therefore a loop is used.
            for recipient in to:
                if isinstance(recipient, str):
                    self.to_adress.append(recipient)
                else:
                    raise TypeError("Recipient type not supported. Expected str got {}.".format(type(recipient)))

    @abstractmethod
    def send(self):
        pass


class CBS_SMTP_Message(EmailFormat):
    """
    [NL]
    CBS SMTP gebaseerd email bericht.
    Dit bericht object maakt het eenvoudig om een email bericht naar een gebruiker te sturen.
    Je kan mails verstuurt vanuit elk e-mail account waarvoor je gerechtigd bent vanuit de centrale server.
    [EN]
    CBS SMTP based email message.
    This message object makes it easy to send messages to email recipients.
    By creating this object mails can be sent from any address the user is allowed to use according to the central server.
    """


    def _connect_to_exchange(self, smtp):
        code, response = smtp.ehlo()
        if code != SMTP_EHLO_OKAY:
            logging.error("Server did not respond as expected to EHLO command")
            raise smtplib.SMTPException("Server did not respond as expected to EHLO command")
        sspiclient = sspi.ClientAuth('NTLM')

        # Generate the NTLM Type 1 message
        sec_buffer = None
        err, sec_buffer = sspiclient.authorize(sec_buffer)
        ntlm_message = asbase64(sec_buffer[0].Buffer)

        # Send the NTLM Type 1 message -- Authentication Request
        code, response = smtp.docmd("AUTH", "NTLM " + ntlm_message)

        # Verify the NTLM Type 2 response -- Challenge Message
        if code != SMTP_AUTH_CHALLENGE:
            logging.error("Server did not respond as expected to NTLM negotiate message")
            raise smtplib.SMTPException("Server did not respond as expected to NTLM negotiate message")

        # Generate the NTLM Type 3 message
        err, sec_buffer = sspiclient.authorize(base64.decodebytes(response))
        ntlm_message = asbase64(sec_buffer[0].Buffer)

        # Send the NTLM Type 3 message -- Response Message
        code, response = smtp.docmd("", ntlm_message)
        if code != SMTP_AUTH_OKAY:
            logging.error("SMTPAuthenticationError")
            raise smtplib.SMTPAuthenticationError(code, response)
        # if this part is reached, the authentication was succesfull and emails can be sent.
        pass

    def __init__(self, sender:str, adressee:str, subject:str='', body:str='', mail_server:str='mail.cbsp.nl'):
        super().__init__()
        self.mail_server = mail_server
        self.from_adress = sender
        self.add_to_recipients(adressee)
        self.subject = subject
        self.body = body

    def send(self):
        """
        Send the prepared email message.
        :return: void
        """
        msg = MIMEText(self.body) # prepare body
        s = smtplib.SMTP(self.mail_server)
        self._connect_to_exchange(s)
        for receiver in iter(self.to_adress):
            if '@' not in receiver:
                receiver = '{rcv}@cbs.nl'.format(rcv=receiver)
            msg['Subject'] = self.subject
            msg['From'] = self.from_adress
            msg['To'] = receiver
            s.sendmail(self.from_adress, [receiver], msg.as_string())
        s.quit()
