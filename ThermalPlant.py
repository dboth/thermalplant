#!/usr/bin/env python

from ensurepip import version
import os, re, sys, time, qimage2ndarray
from cv2 import ROTATE_90_CLOCKWISE
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from subprocess import call
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from gpiozero import CPUTemperature

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
    change_output_signal = pyqtSignal(np.ndarray,np.ndarray)

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
        outputRequested = False
        white = 0
        while self._run_flag:
            if True or outputRequested or self.mode == "CAMERA" or self.mode == "BOTH":
                _, original_camera_frame = self.capture.read()
                original_camera_frame = cv2.rotate(original_camera_frame, cv2.ROTATE_180)
            if True or outputRequested or self.mode == "THERMAL" or self.mode == "BOTH":
                _, thermal_frame = self.thermal.read()
                info, lut = self.thermal.info()
                if outputRequested:
                    temperatures = (lut[thermal_frame])[::-1,::-1]
            
            if self.mode == "THERMAL" or self.mode == "BOTH":
                thermal_frame = thermal_frame.astype(np.float32)
                thermal_frame -= thermal_frame.min()
                thermal_frame /= thermal_frame.max()
                thermal_frame = (np.clip(thermal_frame, 0, 1)*255).astype(np.uint8)
                thermal_frame = cv2.applyColorMap(thermal_frame, cv2.COLORMAP_INFERNO)
                thermal_frame = cv2.rotate(thermal_frame, cv2.ROTATE_180)
                utils.drawTemperature(thermal_frame, (thermal_frame.shape[1]-info['Tmin_point'][0],thermal_frame.shape[0]-info['Tmin_point'][1]), info['Tmin_C'], (55,0,0))
                utils.drawTemperature(thermal_frame, (thermal_frame.shape[1]-info['Tmax_point'][0],thermal_frame.shape[0]-info['Tmax_point'][1]), info['Tmax_C'], (0,0,85))
                utils.drawTemperature(thermal_frame, (thermal_frame.shape[1]-info['Tcenter_point'][0],thermal_frame.shape[0]-info['Tcenter_point'][1]), info['Tcenter_C'], (0,255,255))  

            if self.mode == "CAMERA" or self.mode == "BOTH":
                camera_frame = original_camera_frame

            if self.mode == "THERMAL":
                frame = thermal_frame
            elif self.mode == "CAMERA":
                frame = camera_frame
            elif self.mode == "BOTH":
                #frame = cv2.resize(frame, (self.video_size.width(), self.video_size.height()))
                pass

            
            if outputRequested:
                self.change_output_signal.emit(cv2.cvtColor(original_camera_frame,cv2.COLOR_BGR2RGB),temperatures)
                outputRequested = False
                white = 5
            else:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            if white > 0:
                frame = (np.ones((292,394,3))*255).astype(np.uint)
                white -= 1
            image = qimage2ndarray.array2qimage(frame)
            pixmap = QPixmap.fromImage(image)
            self.change_pixmap_signal.emit(pixmap)
            self.mode = self.nextMode
            outputRequested = self.outputRequested
            self.outputRequested = False
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
            "photo": QIcon("/home/pi/thermalplant/icons/camera.png"),
            "mode_CAMERA": QIcon("/home/pi/thermalplant/icons/mode_camera.png"),
            "mode_THERMAL": QIcon("/home/pi/thermalplant/icons/mode_thermal.png"),
            "close": QIcon("/home/pi/thermalplant/icons/shutdown.png"),
            "mode_BOTH": QIcon("/home/pi/thermalplant/icons/mode_both.png") 
        }
        self.setup_ui()
        self.setup_camera()

    def setup_ui(self):
        """Initialize widgets.
        """
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.ico')))
        self.setWindowTitle("Thermal Plant v0.1")

        self.image_label = QLabel()
        self.image_label.setMinimumSize(self.video_size)
        self.image_label.setStyleSheet("border: 1px solid #aaa; background-color: black")
        self.image_label.setSizePolicy(
            QSizePolicy.MinimumExpanding,
            QSizePolicy.MinimumExpanding
        )
        self.image_label.setAlignment(Qt.AlignRight)

        self.temperature_label = QLabel()
        self.temperature_label.setAlignment(Qt.AlignRight|Qt.AlignBottom)

        self.mode_button = self.createIconButton("Toggle mode","mode_"+self.mode,self.setMode,150)

        self.main_layout = QGridLayout()
        self.main_layout.addWidget(self.image_label,0,0,3,2)

        self.main_layout.addWidget(self.createIconButton("Close","close",self.close,150),0,0,alignment=Qt.AlignLeft | Qt.AlignTop)
        self.main_layout.addWidget(self.mode_button,1,0,alignment=Qt.AlignLeft | Qt.AlignCenter)
        self.main_layout.addWidget(self.createIconButton("Save image","photo",self.requestPhoto,150),2,0,alignment=Qt.AlignLeft | Qt.AlignBottom)
        self.main_layout.addWidget(self.temperature_label,2,1,alignment=Qt.AlignRight | Qt.AlignBottom)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.timer=QTimer()
        self.timer.timeout.connect(self.checkTemperature)
        self.timer.start(5000)

        self.setLayout(self.main_layout)
        self.setCursor(Qt.BlankCursor)
        self.showFullScreen()

    def checkTemperature(self):
        temp = CPUTemperature().temperature
        warn_threshold = 55
        alert_threshold = 65
        if temp >= alert_threshold:
            self.temperature_label.setText("!! Device temp: %.2f °C !!" % temp)
            self.temperature_label.setStyleSheet("margin: 10px; font-size: 20px; color: red; background-color: rgba(0,0,0, 0.7); font-weight: bold;")
        elif temp >= warn_threshold:
            self.temperature_label.setText("Device temp: %.2f °C" % temp)
            self.temperature_label.setStyleSheet("margin: 10px; font-size: 15px;  color: orange; background-color: rgba(0,0,0, 0.7);")
        else:
            self.temperature_label.setText("")


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
        button.setIconSize(QSize(int(height*0.5),int(height*0.5)))
        size = QSize(height,height)
        button.setMinimumSize(size)
        button.setFixedSize(size)
        button.clicked.connect(action)
        button.setStyleSheet("margin: 20px; border-radius: 20px; background-color: rgba(255, 255, 255, 0.5); border: 0px;")
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
        ret = QMessageBox.question(self,'', "Do you really want to shutdown the camera?", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.thread.stop()
            call("sudo nohup shutdown -h now", shell=True)
            event.accept()
        else:
            event.ignore()

    def setup_camera(self):
        """Initialize camera.
        """
        self.thread = VideoThread(self.video_size, self.mode)
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.display_video_stream)
        self.thread.change_output_signal.connect(self.saveImage)
        # start the thread
        self.thread.start()

    def findFolder(self):
        directory = os.fsencode("/media/pi")
        for folder in os.listdir(directory):
            xxx = os.path.join(directory,folder)
            if os.path.isdir(xxx):
                return xxx.decode("utf-8") 
        return str(Path.home())

    @pyqtSlot(np.ndarray,np.ndarray)
    def saveImage(self,camera,temperatures):
        temperatures_im = Image.fromarray(temperatures)
        camera_im = Image.fromarray(camera)
        filename = time.strftime("%Y%m%d_%H%M%S")
        folder = self.findFolder()
        print(folder)
        temperatures_im.save(os.path.join(folder,filename+".temperatures.tiff"))
        camera_im.save(os.path.join(folder,filename+".camera.jpg"))

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
