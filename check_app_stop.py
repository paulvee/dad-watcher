#!/usr/bin/python3
#-------------------------------------------------------------------------------
# Name:        check_app_stop.py
# Purpose:     Check if a pushbutton was pressed to prevent services from running.
#               If the button is pressed, a file in the home directory is
#               created that systemd will check before starting the application.
#
# Author:      paulv
#
# Created:     10-06-2019
# Copyright:
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import RPi.GPIO as GPIO
import subprocess
import time
import os

DEBUG = False

GPIO.setmode(GPIO.BCM) # use GPIO numbering
GPIO.setwarnings(False)

file_name= "/home/pi/do_not_run"

BUTTON = 24 # GPIO-24
# pulled-up to create an active low signal
GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
LED = 23    # GPIO 23
GPIO.setup(LED, GPIO.OUT, initial=GPIO.LOW) # active high


def main():

    # when the program starts (after a boot), remove the file flag
    # if the file is still there
    if os.path.isfile(file_name):
        if DEBUG : print("@boot: removing file flag")
        subprocess.call(["rm {}".format(file_name)], shell=True, \
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        if DEBUG : i = 0
        while True:
            # set an interrupt on a falling edge and wait for it to happen
            GPIO.wait_for_edge(BUTTON, GPIO.FALLING)

            # if the interrupt happends, we'll land here
            if DEBUG:
                i += 1
                print ("Button press detected {} {}".format(i, GPIO.input(BUTTON)))

            #filter out short presses and glitches
            time.sleep(0.5)
            if GPIO.input(BUTTON) == 0:
                if DEBUG : print("button is really pressed")
                if not os.path.isfile(file_name):
                    if DEBUG : print("Stop application is requested, creating file flag")
                    subprocess.call(["touch {}".format(file_name)], shell=True, \
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # turn the warning LED on
                    GPIO.output(LED, GPIO.HIGH)
                else:
                    if DEBUG : print("file is there, remove it")
                    subprocess.call(["rm {}".format(file_name)], shell=True, \
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # turn the warning LED off
                    GPIO.output(LED, GPIO.LOW)

    except KeyboardInterrupt:
        if DEBUG : print("\nCtrl-C - Terminating")
    finally:
        # remove the file if still there
        if os.path.isfile(file_name):
            if DEBUG : print("shutdown: removing file flag")
            subprocess.call(["rm {}".format(file_name)], shell=True, \
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        GPIO.cleanup()

if __name__ == '__main__':
    main()