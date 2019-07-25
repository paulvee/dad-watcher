#!/usr/bin/python3
#-------------------------------------------------------------------------------
# Name:        send_mail.py
# Purpose:     send an email with a file attachment
#
# Author:      paulv
#
# Created:     25-04-2019
# Copyright:   (c) paulv 2019
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_mail():
    fromaddr = "raspberrypi725@gmail.com"
    toaddr = "pw.versteeg@gmail.com"
    msg = MIMEMultipart()
    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = "Dad_watch activity log file"
    body = "Today's log file"

    filename = "/home/pi/dad_watch.log"
    with open(filename, 'r') as f:
        attachment = MIMEText(f.read())
    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(attachment)

    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP('smtp.gmail.com:587')
    server.starttls()
    server.login(fromaddr, "Pensat55")
    text = msg.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()

def main():
    send_mail()

if __name__ == '__main__':
    main()
