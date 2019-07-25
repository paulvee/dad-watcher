#!/usr/bin/python3
#-------------------------------------------------------------------------------
# Name:        halt.py
# Purpose:     Use a pushbutton to halt the Pi.
#              This program is managed by a systemd script
#
# Author:      paulv
#
# Created:     20-03-2016
# Copyright:
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import RPi.GPIO as GPIO
import subprocess
import time

DEBUG = False

GPIO.setmode(GPIO.BCM) # use GPIO numbering
GPIO.setwarnings(False)

BUTTON = 27 # GPIO-27
# pulled-up to create an active low signal
GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def main():

    try:
        while True:
            # set an interrupt on a falling edge and wait for it to happen
            GPIO.wait_for_edge(BUTTON, GPIO.FALLING)

            if DEBUG:
                print ("Button press detected", GPIO.input(BUTTON))
            else:
                print ("Stop requested, Halting the RPi now!")
                subprocess.call(['systemctl stop dad_watch.service'], shell=True, \
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(5)
                subprocess.call(['poweroff'], shell=True, \
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(2)

    # the following will allow you to kill the program
    except KeyboardInterrupt:
        GPIO.cleanup(BUTTON)  # clean up GPIO on CTRL+C exit()


if __name__ == '__main__':
    main()