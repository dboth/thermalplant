#!/usr/bin/env python

from ensurepip import version
import os, re, sys, time, qimage2ndarray
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
#from OpenGL.GL import *
#from OpenGL.GLU import *
#from OpenGL.GLUT import *

import utils
import ht301_hacklib

try:
    from ctypes import windll  # Only exists on Windows.
    myappid = 'de.uni-heidelberg.cos.thermalplant.100'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass      

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QPixmap)
    change_output_signal = pyqtSignal(np.ndarray)

    def __init__(self,video_size,mode):
        super().__init__()
        self.video_size = video_size
        self._run_flag = True
        self.mode = mode
        self.nextMode = mode
        self.outputRequested = False

    def requestOutput(self):
        self.outputRequested = True

    def setMode(self,mode):
        self.nextMode = mode

    def isPiCam(self, cap):
        if not cap.isOpened():
            return False
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print('width:', w, 'height:', h)
        if w == 640 and h == 480: return True
        return False

    def find_device(self):
        for i in range(10):
            print('testing device nr:',i)
            cap = cv2.VideoCapture(i,cv2.CAP_V4L)
            ok = self.isPiCam(cap)
            cap.release()
            if ok: return i
        raise Exception("HT301 device not found!")


    def run(self):
        
        self.thermal = ht301_hacklib.HT301()
        video_dev = self.find_device()
        self.capture = cv2.VideoCapture(video_dev,cv2.CAP_V4L)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE,3)
        while self._run_flag:
            if True or self.outputRequested or self.mode == "CAMERA" or self.mode == "BOTH":
                _, original_camera_frame = self.capture.read()
            if True or self.outputRequested or self.mode == "THERMAL" or self.mode == "BOTH":
                _, thermal_frame = self.thermal.read()
                info, lut = self.thermal.info()
                if self.outputRequested:
                    temperatures = lut[thermal_frame]
            
            if self.mode == "THERMAL" or self.mode == "BOTH":
                thermal_frame = thermal_frame.astype(np.float32)
                thermal_frame -= thermal_frame.min()
                thermal_frame /= thermal_frame.max()
                thermal_frame = (np.clip(thermal_frame, 0, 1)*255).astype(np.uint8)
                thermal_frame = cv2.applyColorMap(thermal_frame, cv2.COLORMAP_INFERNO)
                utils.drawTemperature(thermal_frame, info['Tmin_point'], info['Tmin_C'], (55,0,0))
                utils.drawTemperature(thermal_frame, info['Tmax_point'], info['Tmax_C'], (0,0,85))
                utils.drawTemperature(thermal_frame, info['Tcenter_point'], info['Tcenter_C'], (0,255,255))
                thermal_frame = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2RGB)  

            if self.mode == "CAMERA" or self.mode == "BOTH":
                camera_frame = original_camera_frame

            if self.mode == "THERMAL":
                frame = thermal_frame
            elif self.mode == "CAMERA":
                frame = camera_frame
            elif self.mode == "BOTH":
                #frame = cv2.resize(frame, (self.video_size.width(), self.video_size.height()))
                pass
            
            if self.outputRequested:
                self.change_output_signal(np.dstack((original_camera_frame,temperatures)))
                self.outputRequested = False
            image = qimage2ndarray.array2qimage(frame)
            pixmap = QPixmap.fromImage(image)
            self.change_pixmap_signal.emit(pixmap)
            self.mode = self.nextMode
            time.sleep(0.04)
        self.capture.release()

    def stop(self):
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()


class ThermalPlant(QWidget):
    mode = "THERMAL"

    def __init__(self):
        QWidget.__init__(self)
        self.video_size = QSize(394,292)
        self.icons = {
            "photo": QIcon("icons/photo.png"),
            "mode_CAMERA": QIcon("icons/mode_camera.png"),
            "mode_THERMAL": QIcon("icons/mode_thermal.png"),
            "mode_BOTH": QIcon("icons/mode_both.png") 
        }
        self.setup_ui()
        self.setup_camera()

    def setup_ui(self):
        """Initialize widgets.
        """
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.ico')))
        self.setWindowTitle("Thermal Plant v0.1")
        self.folder = str(Path.home())

        self.image_label = QLabel()
        self.image_label.setMinimumSize(self.video_size)
        self.image_label.setStyleSheet("border: 1px solid #aaa; background-color: black")
        self.image_label.setSizePolicy(
            QSizePolicy.MinimumExpanding,
            QSizePolicy.MinimumExpanding
        )
        self.image_label.setAlignment(Qt.AlignCenter)

        self.mode_button = self.createIconButton("Toggle mode","mode_"+self.mode,self.setMode,80)

        self.main_layout = QGridLayout()
        self.main_layout.addWidget(self.image_label,0,0,2,1)
        self.main_layout.addWidget(self.createIconButton("Save image","photo",self.requestPhoto,80),1,0,alignment=Qt.AlignRight | Qt.AlignBottom)
        self.main_layout.addWidget(self.mode_button,0,0,alignment=Qt.AlignRight | Qt.AlignTop)
        

        self.setLayout(self.main_layout)
        self.showFullScreen()

    def setMode(self):
        if self.mode == "CAMERA":
            self.mode = "THERMAL"
        elif self.mode == "THERMAL":
            self.mode = "CAMERA"
        self.thread.setMode(self.mode)
        self.mode_button.setIcon(self.icons["mode_"+self.mode])

    def createIconButton(self,text,icon,action,height):
        button = QPushButton("")
        button.setToolTip(text)
        button.setIcon(self.icons[icon])
        button.setFixedHeight(height)
        button.setFixedWidth(height)
        button.clicked.connect(action)
        button.setStyleSheet("margin: 20px")
        return button


    def selectFolder(self):
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setDirectory(self.folder)
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            self.folder = filenames[0]
            self.folderWidget.setText(self.folder)

    def requestPhoto(self):
        self.thread.requestOutput()

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

    def setup_camera(self):
        """Initialize camera.
        """
        self.thread = VideoThread(self.video_size, self.mode)
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.display_video_stream)
        self.thread.change_output_signal.connect(self.saveImage)
        # start the thread
        self.thread.start()

    @pyqtSlot(np.ndarray)
    def saveImage(self,stack):
        (r,g,b, temperatures) = cv2.split(stack)
        camera = np.dstack((r,g,b))
        temperatures_im = Image.fromarray(temperatures)
        camera_im = Image.fromarray(camera)
        filename = time.strftime("%Y%m%d_%H%M%S")
        temperatures_im.save(os.path.join(self.folder,filename+".temperatures.tiff"))
        camera_im.save(os.path.join(self.folder,filename+".camera.jpg"))

    @pyqtSlot(QPixmap)
    def display_video_stream(self,pixmap):
        currentSize = self.image_label.size()
        self.image_label.setPixmap(pixmap.scaled(currentSize,Qt.KeepAspectRatio))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.ico')))
    win = ThermalPlant()
    win.show()
    sys.exit(app.exec())
