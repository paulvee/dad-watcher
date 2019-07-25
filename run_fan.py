#!/usr/bin/python3
#-------------------------------------------------------------------------------
# Name:        run_fan.py
# Purpose:     Use PWM to run a fan to keep the core temperature in check
#              This program is managed by a systemd script
#
# Author:      Paul Versteeg
#
# Created:     01-12-2013, modified june 2019
# Copyright:   (c) Paul 2013, 2019
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import RPi.GPIO as GPIO
from time import sleep
import subprocess
import shlex
import string
import sys, os
import traceback

DEBUG = False

FAN_PIN = 17 # GPIO 17

GPIO.setwarnings(False) # when everything is working you could turn warnings off
GPIO.setmode(GPIO.BCM)  # choose BCM numbering scheme.
# set GPIO port as output driver for the Fan, pull it down
GPIO.setup(FAN_PIN, GPIO.OUT)


Fan = GPIO.PWM(FAN_PIN, 100) # create object Fan for PWM on port 22 at 100 Hertz
Fan.start(0)            # start Fan on 0 percent duty cycle (off)

delay = 30              # seconds of delay, testing the core every 30 seconds is OK
cool_baseline = 60      # start cooling from this temp in Celcius onwards
pwm_baseline = 40       # lowest PWM to keep the fan running
factor = 3              # multiplication factor
max_pwm = 100           # maximum PWM value
fan_running = False     # helps to kick-start the fan

def main():
    global fan_running
    '''
    This program controls a Fan by using PWM.
    The Fan will probably not work below 40% dutycycle, so that is the
    fan PWM baseline. The maximum PWM cannot be more than 100%.

    When the cpu temperature is above 50 'C, we will start to cool.
    When the cpu reaches 70 degrees, we would like to run the fan at max speed.

    To make the PWM related to the temperature, strip the actual temp from the
    cool baseline, multiply the delta with 3 and add that to the the baseline
    PWM to get 100% at 70 degrees.

    I have selected a PWM frequency of 100Hz to avoid high frequency noise, but
    you can change that.
    '''
    try:
        while True:
                # get the cpu temperature
                # need to use the full path otherwise root cannot find it
                cmd = "/opt/vc/bin/vcgencmd measure_temp"
                args = shlex.split(cmd)
                output, error = subprocess.Popen(args, stdout = subprocess.PIPE, \
                                stderr= subprocess.PIPE).communicate()

                # strip the temperature out of the returned string
                # the returned string is in the form : b"temp=43.9'C\n"
                # if your localization is set to US, you get the temp in Fahrenheit,
                # so you need to adapt the stripping somewhat
                #
                cpu_temp =float(output[5:9]) # for Celcius

                if DEBUG : print (cpu_temp)

                if cpu_temp < cool_baseline :
                    Fan.ChangeDutyCycle(0) # turn Fan off
                    fan_running = False

                if cpu_temp > cool_baseline :
                    if fan_running :
                        duty_cycle = ((cpu_temp-cool_baseline)*factor)+pwm_baseline
                        if duty_cycle > max_pwm : duty_cycle = max_pwm # max = 100%
                    else:
                        # kick-start the fan for one cycle
                        duty_cycle = 70
                        fan_running = True

                    Fan.ChangeDutyCycle(duty_cycle)   # output the pwm

                    if DEBUG : ("pwm {:.2f}".format(duty_cycle))

                sleep(delay)

    # the following will allow you to kill the program, you can delete these lines if you want
    except KeyboardInterrupt:
        Fan.stop()      # stop the PWM output
        GPIO.cleanup()  # clean up GPIO on CTRL+C exit()

    except Exception as e:
        sys.stderr.write("Got exception: %s" % e)
        if DEBUG :
            print(traceback.format_exc())
            print("GPIO.cleanup")
        GPIO.output(FAN_PIN, GPIO.LOW)
        GPIO.cleanup(FAN_PIN) # leave the other GPIO-pins alone!
        os._exit(1)


if __name__ == '__main__':
    main()