#!/usr/bin/env python

from imutils.video import VideoStream
from flask import Response
from flask import Flask
from flask import render_template
import threading
import argparse
import datetime
import imutils
import time
import cv2

import os, re, sys, time, math, ctypes
from pathlib import Path


import cv2
import numpy as np
from PIL import Image


import utils
import ht301_hacklib

outputFrame = None
lock = threading.Lock()
# initialize a flask object
app = Flask(__name__)
# initialize the video stream and allow the camera sensor to
# warmup
#vs = VideoStream(usePiCamera=1).start()
try:
    capture = ht301_hacklib.HT301()
except:
    try:
        capture = cv2.VideoCapture(0)
    except:
        capture = cv2.VideoCapture(-1,cv2.CAP_V4L)
    capture.set(cv2.CAP_PROP_BUFFERSIZE,3)
time.sleep(2.0)


@app.route("/")
def index():
    # return the rendered template
    return render_template("index.html")

def stream():
    global capture, outputFrame, lock
    while True:
        try:
            _, frame = capture.read()
            try:
                info, lut = capture.info()
                temperatures = lut[frame]
            except:
                frame, g,b = cv2.split(frame)
                temperatures = frame
                #frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Sketchy auto-exposure
            frame = frame.astype(np.float32)
            frame -= frame.min()
            frame /= frame.max()
            frame = (np.clip(frame, 0, 1)*255).astype(np.uint8)
            frame = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
            try:
                utils.drawTemperature(frame, info['Tmin_point'], info['Tmin_C'], (55,0,0))
                utils.drawTemperature(frame, info['Tmax_point'], info['Tmax_C'], (0,0,85))
                utils.drawTemperature(frame, info['Tcenter_point'], info['Tcenter_C'], (0,255,255))
            except:
                pass
            #frame = cv2.resize(frame, (self.video_size.width(), self.video_size.height()))
            #frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with lock:
                outputFrame = frame.copy()
        except Exception as e:
            print(e)
            pass

def generate():
    # grab global references to the output frame and lock variables
    global outputFrame, lock
    # loop over frames from the output stream
    while True:
        # wait until the lock is acquired
        with lock:
            # check if the output frame is available, otherwise skip
            # the iteration of the loop
            if outputFrame is None:
                continue
            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)
            # ensure the frame was successfully encoded
            if not flag:
                continue
        # yield the output frame in the byte format
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
            bytearray(encodedImage) + b'\r\n')

@app.route("/video_feed")
def video_feed():
    # return the response generated along with the specific media
    # type (mime type)
    return Response(generate(),
        mimetype = "multipart/x-mixed-replace; boundary=frame")

if __name__ == '__main__':
    # construct the argument parser and parse command line arguments
    
    # start a thread that will perform motion detection
    t = threading.Thread(target=stream, args=(
        ))
    t.daemon = True
    t.start()
    # start the flask app
    app.run(host="127.0.0.1", port="8080", debug=True,
        threaded=True, use_reloader=False)
    capture.release()