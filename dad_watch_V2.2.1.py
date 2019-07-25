#!/usr/bin/python3
#-------------------------------------------------------------------------------
# Name:        dad_watch.py
# Purpose:     Watching the activity of my dad, and send an SMS as warning when
#              no activity has been detected for a while.
#              This program is managed by a systemd script
#
# Author:      Paul Versteeg, based on idea and blog from Adrian Rosebrock
#              https://www.pyimagesearch.com/2018/08/13/opencv-people-counter/
# Modified:
#
# Created:     26-05-2019
# Copyright:   (c) Paul Versteeg
# Licence:     <your licence>
#-------------------------------------------------------------------------------

# import the necessary packages
from edgetpu.detection.engine import DetectionEngine
from imutils.video import VideoStream
from imutils.video import FPS
from PIL import Image
import argparse
import imutils    #pip3 install imutils @ sudo for running as root
import warnings
import datetime
# pip3 install json-minify and also sudo
from json_minify import json_minify
import json
import time
import cv2
import numpy as np
import os
import os.path
import sys
import shlex
import subprocess
import traceback
from threading import Thread
import logging
import logging.handlers
# https://www.twilio.com/
from twilio.rest import Client  # pip3 install twilio & sudo for running as root
import RPi.GPIO as GPIO
from multiprocessing import Process, Queue
import signal

VERSION = "2.2.1" # added fix for false positive at start-up
VERSION ="2.2"  # added json_minify to allow comments in the configuration file
                # added Twilio vars to the conf file, load all conf var at start
                # change all references to static vars in the code.
#VERSION ="2.1" # removed gpio.cleanup's to avoid exception in sound_alarm at shutdown
                # added ALARM check in timing deadline if statement

#filter warnings, load the configuration file
warnings.filterwarnings("ignore")
conf = json.loads(json_minify(open("/home/pi/conf.json").read()))

# load the configuration variables
DEBUG = conf["DEBUG"]
DAEMON = conf["DAEMON"]
SMS = conf["SMS"]
TEST = conf["TEST"]
alarm_time = conf["alarm_time"]
window = conf["window"]
confidence = conf["confidence"]
twilio_account_sid = conf["twilio_account_sid"] # for Twilio
twilio_auth_token = conf["twilio_auth_token"] # for Twilio
from_cell= conf["from_cell"] # Twilio cell number
to_cell = conf["to_cell"] # target cell number
whatsapp_from = conf["whatsapp_from"] # Twilio whatsapp cell number

if DEBUG :
    print ("DEBUG is {}".format(DEBUG))
    print ("DAEMON is {}".format(DAEMON))
    print("SMS is {}".format(SMS))
    print("TEST is {}".format(TEST))
    print("confidence {}".format(confidence))
    print("alarm_time is {}".format(alarm_time))
    print("window is {}".format(window))
    print("twilio_account_sid is {}".format(twilio_account_sid))
    print("twilio_auth_token is {}".format(twilio_auth_token))
    print("from_cell is {}".format(from_cell))
    print("to_cell is {}".format(to_cell))
    print("whatsapp_from is {}".format(whatsapp_from))


BEEPER = 4  # GPIO 4
ALARM = False      # alarm flag
ALARM_RUNNING = False
boot_up= True # to avoide a false positive at startup

#--logger definitions
# save daily logs for 7 days
# the logfile will be mailed daily
LOG_FILENAME = "/home/pi/dad_watch.log"
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
handler = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when="midnight", backupCount=7)
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class MyLogger():
    '''
    A class that can be used to capture stdout and sterr to put it in the log

    '''
    def __init__(self, level, logger):
            '''Needs a logger and a logger level.'''
            self.logger = logger
            self.level = level

    def write(self, message):
        # Only log if there is a message (not just a new line)
        if message.rstrip() != "":
                self.logger.log(self.level, message.rstrip())

    def flush(self):
        pass  # do nothing -- just to handle the attribute for now


# --Replace stdout and stderr with logging to file so we can run it as a daemon
# and still see what is going on
if DAEMON :
    sys.stdout = MyLogger(logging.INFO, logger)
    sys.stderr = MyLogger(logging.ERROR, logger)


def get_cpu_temp():
    # get the cpu temperature
    # need to use the full path, otherwise root cannot find it
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
    return(cpu_temp)


def init():
    global labels, model, vs, fps

    # set the GPIO mode
    GPIO.setmode(GPIO.BCM)
    if DEBUG:
        GPIO.setwarnings(True)
    else:
        GPIO.setwarnings(False)

    # set GPIO port as output driver for the beeper
    GPIO.setup(BEEPER, GPIO.OUT)

    # the core temp must be at the lowest at startup, so report it.
    logger.info("Core temp is {} degrees C".format(get_cpu_temp()))

    # initialize the labels dictionary
    print("parsing class labels...")
    labels = {}
    # loop over the class labels file
    for row in open("/home/pi/edgetpu_models/coco_labels.txt"):
        # unpack the row and update the labels dictionary
        (classID, label) = row.strip().split(maxsplit=1)
        labels[int(classID)] = label.strip()

    # load the Google Coral tpu object detection model
    print("loading Coral model...")
    model = DetectionEngine("/home/pi/edgetpu_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite")

    # initialize the video stream and allow the camera sensor to warmup
    print("starting video stream...")
    vs = VideoStream(src=0).start() # webcam
#    vs = VideoStream(usePiCamera=True).start()  # Picam
    # let the camera sensor warm-up
    time.sleep(2.0)

    if not DAEMON :
        # start the frames per second throughput estimator
        fps = FPS().start()

    beep()


def send_sms(msg='no txt'):

    account_sid = twilio_account_sid
    auth_token = twilio_auth_token

    try:
        client = Client(account_sid, auth_token)

        message = client.messages.create(
                 body = msg,
                 from_= from_cell,
                 to = to_cell)

        logger.debug("sid = {}".format(message.sid))

    except Exception as e:
        logger.error("Unexpected Exception in send_sms() : \n{}".format(e))
        return


def send_whatsapp(msg='no txt'):

    account_sid = twilio_account_sid
    auth_token = twilio_auth_token

    try:
        client = Client(account_sid, auth_token)

        if DEBUG :
            logger.debug("whatsapp: "+msg)
            return
        else:
            message = client.messages.create(
                        body = msg,
                        from_= whatsapp_from,
                        to= to_cell)

        logger.debug("sid = {}".format(message.sid))

    except Exception as e:
        logger.error("Unexpected Exception in send_whatsapp() : \n{0}".format(e))
        return


def beep():
    GPIO.output(BEEPER, GPIO.HIGH)
    time.sleep(0.05)
    GPIO.output(BEEPER, GPIO.LOW)
    return


def sound_alarm():
    '''
    Function to create a seperate thread to start an alarm beep.
    The alarm will be stoppen when movement has been detected again or
    when the total alarm time has been exceeded.

    '''
    global alarm_thread, ALARM_RUNNING, ALARM, SMS

    try:
        class alarm_threadclass(Thread):

            def run(self):
                global alarm_thread, ALARM_RUNNING, ALARM, SMS
                try:
                    start_time = datetime.datetime.now()
                    i = 1
                    while ALARM :
                        ALARM_RUNNING = True
                        GPIO.output(BEEPER, GPIO.HIGH)
                        time.sleep(0.1*i)
                        GPIO.output(BEEPER, GPIO.LOW)
                        time.sleep(5)
                        i += 1
                        max_alarm = (datetime.datetime.now() - start_time).seconds

                        # add ALARM in the test to catch a change during the sleep period
                        if (max_alarm > alarm_time and ALARM) :
                            logger.info("*** no movement during alarm, sending SMS")
                            if SMS :
                                send_sms("no movement during alarm fase")
                                SMS = False # send only one SMS per session
                            break

                    ALARM_RUNNING = False
                    logger.info("alarm thread ended")
                    ALARM = False
                    return

                except Exception as e:
                    logger.error("Unexpected Exception in sound_alarm :\n{0} ".format(e))

        alarm_thread = alarm_threadclass()
        alarm_thread.setDaemon(True) # so a ctrl-C can terminate it
        if not ALARM_RUNNING :
            alarm_thread.start() # start the thread
            logger.info("sound_alarm thread started")

    except Exception as e:
        logger.error("Unexpected Exception in sound_alarm() : \n{0}".format(e))
        return


def sig_handler (signum=None, frame = None):
    '''
    This function will catch the most important system signals, but NOT not a shutdown!

    This handler catches the following signals from the OS:
        SIGHUB = (1) SSH Terminal logout
        SIGINT = (2) Ctrl-C
        SIGQUIT = (3) ctrl-\
        IOerror = (5) when terminating the SSH connection (input/output error)
        SIGTERM = (15) Deamon terminate (deamon --stop): is coming from systemd
    However, it cannot catch SIGKILL = (9), the kill -9 or the shutdown procedure

    '''

    try:
        logger.info("Sig_handler called with signal : {}".format(signum))
        if signum == 1 :
            return # ignore SSH logout termination

        # the core temp must be at the highest now, so report it.
        logger.info("Core temp is {} degrees C".format(get_cpu_temp()))
        logger.info("Terminating \n")

        beep()
        time.sleep(0.5)
        beep()

        if not DAEMON:
            # stop the fps timer and display the collected results
            fps.stop()
            print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
            print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

        # do a bit of cleanup
        GPIO.output(BEEPER, GPIO.LOW) # force the beeper to quit
#        GPIO.cleanup(BEEPER) # leave the other GPIO-pins alone!
        if not DAEMON :
            cv2.destroyAllWindows()
            vs.stop()
        time.sleep(1)
        os._exit(0) # force the exit to the OS

    except Exception as e: # IOerror 005 when terminating the SSH connection
        logger.error("Unexpected Exception in sig_handler() : \n{0}".format(e))
        return



def main():
    global ALARM, boot_up

    logger.info('\n\n dad_watch version %s' % VERSION)

    # initialize the frame dimensions (we'll set them as soon as we read
    # the first frame from the video)
    W = None
    H = None
    startX = 0
    startY = 0
    endX = 0
    endY = 0

    dir = None  # direction

    side = None
    old_side = None
    movement = 0

    init()

    # setup a catch for the following signals: signal.SIGINT = ctrl-c
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, sig_handler)

    # setup the movement timers
    lastSeen = datetime.datetime.now()
    lastSeen_ts = datetime.datetime.now()

    try:
        # loop over the frames from the video stream
        while True:
            # setup the presence timers
            timestamp = datetime.datetime.now()
            lastSeen_ts = datetime.datetime.now()
            interval = (lastSeen_ts - lastSeen).seconds

            # grab the frame from the threaded video stream and resize it
            # to have a maximum width of 500 or 800 pixels during testing
            frame = vs.read()

            if DAEMON :
                frame = imutils.resize(frame, width=500)
            else:
                frame = imutils.resize(frame, width=800)

            orig = frame.copy()

            # if the frame dimensions are empty, set them
            if W is None or H is None:
                (H, W) = frame.shape[:2]
                logger.debug("[INFO] H= {} W= {}".format(H,W))
                # Create a dividing line in the center of the frame
                # It is used to determine movement of the objects
                centerline = W // 2

            # make sure the alarm does not run indefinetely
            if (interval > (window + 100) and ALARM == True) :
                logger.info("reset the timer interval")
                lastSeen = datetime.datetime.now()
                ALARM = False

            # check if we went past the movement timing deadline...
            if ((interval > window) and (ALARM == False)):
                ts =  timestamp.strftime("%A %d %B %Y %H:%M:%S")
                logger.info("*** no movement alarm")
                ALARM = True
                sound_alarm()

            # prepare the frame for object detection by converting it
            # from BGR to RGB channel ordering and then from a NumPy
            # array to PIL image format
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(frame)

            # do the heavy lifting on the Coral USB tpu
            results = model.DetectWithImage(frame, threshold=confidence,
                keep_aspect_ratio=True, relative_coord=False)


            # loop over the results
            for r in results:
                # use the index to get at the properlabel
                label = labels[r.label_id]
                # we're only interested in persons
                if label != "person" :
                    continue

                # extract the bounding box and predicted class label
                box = r.bounding_box.flatten().astype("int")
                (startX, startY, endX, endY) = box

                # calculate the middle of the object
                position = (startX + endX) // 2
                # The centerline line is in the middle of the frame (W // 2)
                # Determine if the object movement is accross the centerline
                # If the middle of the object AND the right-hand side (endX) has
                # crossed, there was a complete move to the left.
                # If the middle of the object AND the left-hand side (startX) has
                # crossed, there was a complete move to the right.

                if position < centerline and endX < centerline :
                    side = "left"
                    # print("moving left")
                if position > centerline and startX > centerline :
                    side = "right"
                    # print("moving right")

                # if there is a change in the side, record it as a movement
                # avoid a false positive at startup
                if boot_up :
                    old_side = side
                    boot_up = False
                if side is not old_side:
                    movement += 1
                    if TEST : beep()
                    logger.info("movement {}".format(movement))

                    # reset the counter & alarm flag
                    lastSeen = datetime.datetime.now()
                    if (ALARM == True) :
                        ALARM = False

                old_side = side

                if not DAEMON :
                    # draw the bounding box and label on the image
                    cv2.rectangle(orig, (startX, startY), (endX, endY),
                        (0, 255, 0), 2)
                    y = startY - 15 if startY - 15 > 15 else startY + 15
                    text = "{}: {:.2f}%".format(label, r.score * 100)
                    cv2.putText(orig, text, (startX, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            if not DAEMON :
                # show the output frame and wait for a key press
                cv2.imshow("Frame", orig)
                key = cv2.waitKey(1) & 0xFF

                # if the `q` key was pressed, break from the loop
                if key == ord("q"):
                    break
                # update the FPS counter
                fps.update()

    except KeyboardInterrupt:
        if (DEBUG) and (not DAEMON): print ("\nCtrl-C Terminating")

    except Exception as e:
        sys.stderr.write("Got exception: %s" % e)
        if (DEBUG) and (not DAEMON): print(traceback.format_exc())
        logger.error("exception in main() \n {}".format(traceback.format_exc()))

    finally:
        if not DAEMON :
            # stop the timer and display FPS information
            fps.stop()
            print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
            print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))
        # do a bit of cleanup
        print("GPIO.cleanup")
        GPIO.output(BEEPER, GPIO.LOW)  # force beeper to quit
        GPIO.cleanup()     # cleanup does not really force the output to zero
        cv2.destroyAllWindows()
        vs.stop()



if __name__ == '__main__':
    main()

