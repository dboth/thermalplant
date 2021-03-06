#!/usr/bin/env python

import os, re, sys, time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import utils
import ht301_hacklib

try:
    from ctypes import windll  # Only exists on Windows.
    myappid = 'de.uni-heidelberg.cos.thermalplant.100'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

class ThermalPlant(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.video_size = QSize(394,292)
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
        #self.image_label.setFixedSize(self.video_size)
        self.image_label.setStyleSheet("border: 1px solid #aaa; background-color: black")
        self.image_label.setSizePolicy(
            QSizePolicy.MinimumExpanding,
            QSizePolicy.MinimumExpanding
        )
        self.image_label.setAlignment(Qt.AlignCenter)

        self.folderWidget = QLineEdit();
        self.folderWidget.setReadOnly(True)
        self.folderWidget.setFixedHeight(30)
        self.folderWidget.setText(self.folder)


        self.nameWidget = QLineEdit();
        self.nameWidget.setFixedHeight(50)
        f = self.nameWidget.font()
        f.setPointSize(20)
        self.nameWidget.setFont(f)
        self.nameWidget.setPlaceholderText("Measurement name")
        self.nameWidget.returnPressed.connect(self.photo)

        self.main_layout = QGridLayout()

        self.main_layout.addWidget(self.folderWidget,0,0,1,4)
        self.main_layout.addWidget(self.createIconButton("Choose target folder","SP_DirIcon",self.selectFolder,30),0,4)
        self.main_layout.addWidget(self.createIconButton("Calibrate","SP_BrowserReload",self.calibrate,30),0,5)

        self.main_layout.addWidget(self.nameWidget,2,0,1,5)
        self.main_layout.addWidget(self.createIconButton("Save image","SP_DialogSaveButton",self.photo,50),2,5)

        #self.main_layout.addLayout(self.top_row)
        self.main_layout.addWidget(self.image_label,1,0,1,6)
        #self.main_layout.addLayout(self.bottom_row)

        self.setLayout(self.main_layout)

    def createIconButton(self,text,icon,action,height):
        button = QPushButton("")
        button.setToolTip(text)
        pixmapi = getattr(QStyle.StandardPixmap, icon)
        icon = self.style().standardIcon(pixmapi)
        button.setIcon(icon)
        button.setFixedHeight(height)
        button.clicked.connect(action)
        return button


    def calibrate(self):
        try:
            self.capture.calibrate()
        except:
            pass

    def selectFolder(self):
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setDirectory(self.folder)
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            self.folder = filenames[0]
            self.folderWidget.setText(self.folder)

    def photo(self):
        ret, frame = self.capture.read()
        try:
            info, lut = self.capture.info()
            A = lut[frame]
        except:
            #Emulated for test
            (A,G,R) = cv2.split(frame)
        im = Image.fromarray(A)
        measurement = "".join([c for c in self.nameWidget.text().replace(" ","_") if re.match(r'\w', c)])
        filename = time.strftime("%Y%m%d_%H%M%S") + ".tiff"
        if len(measurement) > 0:
            filename = measurement + "." + filename
        im.save(os.path.join(self.folder,filename))

    def setup_camera(self):
        """Initialize camera.
        """
        try:
            self.capture = ht301_hacklib.HT301()
        except:
            self.capture = cv2.VideoCapture(0)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.display_video_stream)
        self.timer.start(30)

    def display_video_stream(self):
        """Read frame from camera and repaint QLabel widget.
        """
        try:
            _, frame = self.capture.read()
            try:
                info, lut = self.capture.info()
                
            except:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = QImage(frame, frame.shape[1], frame.shape[0], 
                        frame.strides[0], QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            currentSize = self.image_label.size()
            self.image_label.setPixmap(pixmap.scaled(currentSize,Qt.KeepAspectRatio))
        except Exception as e:
            print(e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.ico')))
    win = ThermalPlant()
    win.show()
    sys.exit(app.exec())