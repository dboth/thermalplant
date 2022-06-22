#!/usr/bin/env python

import os, re, sys, time, threading
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.image import Image as Kimage
from kivy.uix.boxlayout import BoxLayout
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Rectangle, Color
from kivy.graphics.texture import Texture

from functools import partial

import utils
import ht301_hacklib

'''
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    change_temperatures_signal = pyqtSignal(np.ndarray)

    def __init__(self,video_size):
        super().__init__()
        self.video_size = video_size
        self._run_flag = True

    def run(self):
        # capture from web cam
        try:
            self.capture = ht301_hacklib.HT301()
        except:
            try:
                self.capture = cv2.VideoCapture(0)
            except:
                self.capture = cv2.VideoCapture(-1,cv2.CAP_V4L)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE,3)
        while self._run_flag:
            try:
                _, frame = self.capture.read()
                try:
                    info, lut = self.capture.info()
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
                frame = cv2.resize(frame, (self.video_size.width(), self.video_size.height()))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                #image = qimage2ndarray.array2qimage(frame)
                self.change_pixmap_signal.emit(frame)
                self.change_temperatures_signal.emit(temperatures)
            except Exception as e:
                print(e)
                pass
            time.sleep(0.12)
        # shut down capture system
        self.capture.release()

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()
'''

class KivyCamera(Widget):
    source = 0
    fps = 30

    def __init__(self):
        super(KivyCamera, self).__init__()
        with self.canvas:
            #Color(1, 0, 0, 1)
            self.bg = Rectangle(pos=self.pos, size=self.size)

        self.bind(pos=self.update_bg)
        self.bind(size=self.update_bg)
        threading.Thread(target=self.doit, daemon=True).start()

    def doit(self):
        self.do_vid = True
        frame=None
        cam=cv2.VideoCapture(0)#-1, cv2.CAP_V4L)

        while (self.do_vid):
            ret, frame = cam.read()
            Clock.schedule_once(partial(self.update, frame))
            time.sleep(0.04)
        cam.release()
    
    def update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def update(self, frame, dt):
        buf1 = cv2.flip(frame, 0)
        buf = buf1.tostring()
        image_texture = Texture.create(
            size=(frame.shape[1], frame.shape[0]), colorfmt="bgr"
        )
        image_texture.blit_buffer(buf, colorfmt="bgr", bufferfmt="ubyte")
        self.bg.texture = image_texture

class MyBackground(Widget):
    def __init__(self, **kwargs):
        super(MyBackground, self).__init__(**kwargs)
        with self.canvas:
            #Color(1, 0, 0, 1)
            self.bg = Rectangle(source='water.png', pos=self.pos, size=self.size)

        self.bind(pos=self.update_bg)
        self.bind(size=self.update_bg)


class ThermalPlant(App):


    def photo(self):
        im = Image.fromarray(self.temperatures)
        measurement = "".join([c for c in self.nameWidget.text().replace(" ","_") if re.match(r'\w', c)])
        filename = time.strftime("%Y%m%d_%H%M%S") + ".tiff"
        if len(measurement) > 0:
            filename = measurement + "." + filename
        im.save(os.path.join(self.folder,filename))


    def setup_camera(self):
        """Initialize camera.
        
        self.thread = VideoThread(self.video_size)
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.display_video_stream)
        self.thread.change_temperatures_signal.connect(self.setTemperatures)
        # start the thread
        self.thread.start()"""

    def setTemperatures(self,temps):
        self.temperatures = temps

    def display_video_stream(self,image):
        """Read frame from camera and repaint QLabel widget.
        """
        #(r,g,b, temperatures) = cv2.split(frames)
        #frame = np.dstack((r,g,b))
        #self.temperatures = temperatures
        #self.image_label.setImage(image)

    def reset_rects(self,x):
        pass

    def addRectangle(self):
        with self.wid.canvas:
            Color(1, 0, 0, 1)
            Rectangle(pos=(self.wid.x,self.wid.y), size=(self.wid.width, self.wid.height))

    def build(self):
        self.wid = KivyCamera()

        #self.addRectangle()

        btn_reset = Button(text='Reset',on_press=partial(self.reset_rects, 1))

        layout = BoxLayout(size_hint=(1, None), height=50)
        layout.add_widget(btn_reset)
        #layout.add_widget(label)

        root = BoxLayout(orientation='vertical')
        root.add_widget(self.wid)
        root.add_widget(layout)

        return root


if __name__ == '__main__':
    ThermalPlant().run()
