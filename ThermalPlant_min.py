#!/usr/bin/env python
import sys, time
import cv2
import numpy as np
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PIL import Image
from PyQt5.QtWidgets import *


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
        self.gl.glClearColor(0.0, 0.0, 0.0, 1.0) 
        self.setImage(np.zeros((self.width, self.height,3)))
        #self.setImage((np.random.rand(self.width,self.height,3)*255).astype(np.uint8))

    def _idle(self):
        #print("IDLE")
        
        self.update()

    def _display(self):
        #print("DISPLAY")
        self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | self.gl.GL_DEPTH_BUFFER_BIT)
        self.gl.glEnable(self.gl.GL_TEXTURE_2D)
        self.gl.glTexParameterf(self.gl.GL_TEXTURE_2D, self.gl.GL_TEXTURE_MIN_FILTER, self.gl.GL_NEAREST)
        
        self.gl.glMatrixMode(self.gl.GL_PROJECTION)
        self.gl.glLoadIdentity()
        self.gl.glOrtho(0, self.width, 0, self.height,-1,1)
        
        self.gl.glMatrixMode(self.gl.GL_MODELVIEW)
        self.gl.glLoadIdentity()    

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
        if h == 0:
            h = 1

        self.gl.glViewport(0, 0, w, h)
        self.gl.glMatrixMode(self.gl.GL_PROJECTION)

        self.gl.glLoadIdentity()
        
        if w <= h:
            self.gl.glOrtho(-1, 1, -1*h/w, h/w, -1, 1)
        else:
            self.gl.glOrtho(0, w, 0, h, -1, 1)

        self.gl.glMatrixMode(self.gl.GL_MODELVIEW)
        self.gl.glLoadIdentity()
        self.update()

    def paintGL(self):
        self._display()
      

class VideoThread(QThread):
    change_image_signal = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self._run_flag = True

    def run(self):
        capture = cv2.VideoCapture(0)
        capture.set(cv2.CAP_PROP_BUFFERSIZE,3)
        while self._run_flag:
            _, frame = capture.read()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (788, 584))
            self.change_image_signal.emit(frame)
            time.sleep(0.04)
        capture.release()

    def stop(self):
        self._run_flag = False
        self.wait()


class MainUI(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.video_size = QSize(788,584)
        self.setup_ui()
        self.setup_camera()

    def setup_ui(self):
        self.video_widget = GLWidget(self,self.video_size.width(),self.video_size.height())
        self.main_layout = QGridLayout()
        self.main_layout.addWidget(self.video_widget,0,0)
        self.setLayout(self.main_layout)

    def closeEvent(self, event):
        self.thread.stop()
        event.accept()

    def setup_camera(self):
        self.thread = VideoThread()
        self.thread.change_image_signal.connect(self.display_video_stream)
        self.thread.start()

    @pyqtSlot(np.ndarray)
    def display_video_stream(self,image):
        #print("CALL IT");
        self.video_widget.setImage(image)
        pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainUI()
    win.show()
    sys.exit(app.exec())
