#!/usr/bin/python3
#-------------------------------------------------------------------------------
# Name:        clear_stop_flag.py
# Purpose:     Clear the manually set file flag that stops the application from
#              running.
#              This will be executed by cron at 23:30 hrs.
#
# Author:      paulv
#
# Created:     10-06-2019
# Copyright:
# Licence:     <your licence>
#-------------------------------------------------------------------------------


import subprocess
import os

DEBUG = False

file_name= "/home/pi/do_not_run"


def main():

    # remove the file flag if the file is still there
    if os.path.isfile(file_name):
        if DEBUG : print("removing file flag")
        subprocess.call(["rm {}".format(file_name)], shell=True, \
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

if __name__ == '__main__':
    main()
