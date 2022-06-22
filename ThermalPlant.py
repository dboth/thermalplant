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

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None, width=1280, height=720):
        self.parent = parent
        self.width = width
        self.height = height
        QOpenGLWidget.__init__(self, parent)

    def sizeHint(self):
        return QSize(self.width,self.height)

    def setImage(self,image):
        self.image = np.flipud(image).flatten().tobytes()
        #print(self.image)

        self._idle()

    def initializeGL(self):
        version_profile = QOpenGLVersionProfile()
        version_profile.setVersion(2,0)
        self.gl = self.context().versionFunctions(version_profile)
        print(self.gl)
        self.gl.glClearColor(0.0, 0.0, 0.0, 1.0) 
        self.setImage(np.zeros((self.width, self.height,3)))
        print(self.gl.glGetString(self.gl.GL_VERSION))
        #self.setImage((np.random.rand(self.width,self.height,3)*255).astype(np.uint8))

    def _idle(self):
        #print("IDLE")
        
        self.update()

    def _display(self):
        #print("DISPLAY")
        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | self.gl.GL_DEPTH_BUFFER_BIT)
        self.gl.glEnable(self.gl.GL_TEXTURE_2D)
        self.gl.glTexParameterf(self.gl.GL_TEXTURE_2D, self.gl.GL_TEXTURE_MIN_FILTER, self.gl.GL_NEAREST)
        
        #self.gl.glMatrixMode(self.gl.GL_PROJECTION)
        #self.gl.glLoadIdentity()
        #self.gl.glOrtho(0, self.width, 0, self.height,-1,1)
        
        #self.gl.glMatrixMode(self.gl.GL_MODELVIEW)
        #self.gl.glLoadIdentity()    

        self.gl.glBegin(self.gl.GL_QUADS)
        self.gl.glTexCoord2f(0.0, 0.0)
        self.gl.glVertex2f(0.0, 0.0)
        self.gl.glTexCoord2f(1.0, 0.0)
        self.gl.glVertex2f(self.width, 0.0)
        self.gl.glTexCoord2f(1.0, 1.0)
        self.gl.glVertex2f(self.width, self.height)
        self.gl.glTexCoord2f(0.0, 1.0)
        self.gl.glVertex2f(0.0, self.height)
        self.gl.glEnd()
        self.gl.glPixelStorei(self.gl.GL_UNPACK_ALIGNMENT, 1)
        self.gl.glTexImage2D(self.gl.GL_TEXTURE_2D, 
            0, 
            self.gl.GL_RGB, 
            self.width,self.height,
            0,
            self.gl.GL_RGB, 
            self.gl.GL_UNSIGNED_BYTE, 
            self.image)
        self.gl.glFlush()

    def resizeGL(self, w, h):
        self.update()

    def paintGL(self):
        self._display()
        
        

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


class ThermalPlant(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.video_size = QSize(788,584)
        self.temperatures = np.array([])
        self.setup_ui()
        self.setup_camera()

    def setup_ui(self):
        """Initialize widgets.
        """
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.ico')))
        self.setWindowTitle("Thermal Plant v0.1")
        self.folder = str(Path.home())

        self.image_label = GLWidget(self,self.video_size.width(),self.video_size.height())
        self.image_label.setMinimumSize(self.video_size)
        #self.image_label.setFixedSize(self.video_size)
        self.image_label.setStyleSheet("border: 1px solid #aaa; background-color: black")
        self.image_label.setSizePolicy(
            QSizePolicy.MinimumExpanding,
            QSizePolicy.MinimumExpanding
        )
        #self.image_label.setAlignment(Qt.AlignCenter)

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
        #self.main_layout.addWidget(self.createIconButton("Calibrate","SP_BrowserReload",self.calibrate,30),0,5)

        self.main_layout.addWidget(self.nameWidget,2,0,1,4)
        self.main_layout.addWidget(self.createIconButton("Save image","SP_DialogSaveButton",self.photo,50),2,4)

        #self.main_layout.addLayout(self.top_row)
        self.main_layout.addWidget(self.image_label,1,0,1,5)
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


    def selectFolder(self):
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setDirectory(self.folder)
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            self.folder = filenames[0]
            self.folderWidget.setText(self.folder)

    def photo(self):
        im = Image.fromarray(self.temperatures)
        measurement = "".join([c for c in self.nameWidget.text().replace(" ","_") if re.match(r'\w', c)])
        filename = time.strftime("%Y%m%d_%H%M%S") + ".tiff"
        if len(measurement) > 0:
            filename = measurement + "." + filename
        im.save(os.path.join(self.folder,filename))

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

    def setup_camera(self):
        """Initialize camera.
        """
        self.thread = VideoThread(self.video_size)
        # connect its signal to the update_image slot
        self.thread.change_pixmap_signal.connect(self.display_video_stream)
        self.thread.change_temperatures_signal.connect(self.setTemperatures)
        # start the thread
        self.thread.start()

    @pyqtSlot(np.ndarray)
    def setTemperatures(self,temps):
        self.temperatures = temps

    @pyqtSlot(np.ndarray)
    def display_video_stream(self,image):
        """Read frame from camera and repaint QLabel widget.
        """
        #(r,g,b, temperatures) = cv2.split(frames)
        #frame = np.dstack((r,g,b))
        #self.temperatures = temperatures
        self.image_label.setImage(image)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.ico')))
    win = ThermalPlant()
    win.show()
    sys.exit(app.exec())
