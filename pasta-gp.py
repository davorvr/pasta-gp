#!/usr/bin/python3

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
import serial
import serial.tools.list_ports
import time
import threading
from collections import deque
import signal
import subprocess
signal.signal(signal.SIGINT, signal.SIG_DFL)
font=QtGui.QFont()
font.setPixelSize(20)
from datetime import datetime

port = list(serial.tools.list_ports.grep("10c4:ea60"))
if not port:
#    print("hi")
    raise IOError("Serial device not found!")
else:
    dev = port[0][0]
baud = 115200

pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', (50, 50, 50))
pg.setConfigOption('foreground', (240, 240, 240))

def handler(msg_type, msg_log_context, msg_string):
    pass

#QtCore.qInstallMessageHandler(handler)
app = QtGui.QApplication([])
view = pg.GraphicsView()
view.show()
l = pg.GraphicsLayout()
view.setCentralItem(l)
view.setWindowTitle('Load cell real-time plot')
view.resize(800,400)
view.move(0,680)

p = l.addPlot()
#p.setDownsampling(mode='peak')
p.setClipToView(True)
p.showAxis('right', show=True)

p.setLabel('bottom', 'Time (s)')
p.getAxis('bottom').setScale(10**(-3))

p.setLabel('left', 'Weight offset')

p.getAxis('bottom').setTickSpacing(1, 0.1)
#p.getAxis('bottom').tickFont = font
p.getAxis('left').setTickSpacing(50, 5)
p.getAxis('right').setTickSpacing(50, 5)

p.getAxis('bottom').setTickSpacing(0.5, 0.1)

p.showGrid(y=True, x=True, alpha=0.2)

p.setXRange(-10000, 0)
p.setYRange(-50, 500)
p.setLimits(xMax=0)
curve = p.plot()
curve.setPen(pg.mkPen(color=(240, 240, 240), width=2))

data = deque([], 5000)
ptr = 0

logname = str(input("Reset the MCU, input the filename, and press Return:\n> "))+".csv"
ser = serial.Serial(dev,baud)

def update_ser():
    global data, ser, logname, timer
    t = threading.currentThread()
    
    # discard the first few values
    temp_timer = datetime.now()
    while (datetime.now()-temp_timer).seconds<2:
        ser.readline()
    
    logfile = open(logname, "w")
    timer.start()
    while getattr(t, "running", True):
        ser_in = None
        while ser_in is None:
            try:
                ser_in = float(ser.readline())
            except ValueError:
                pass
        time = timer.elapsed()
        logfile.write(str(time)+","+str(ser_in)+"\n")
        data.append({'x': time, 'y': ser_in})
    logfile.close()

def update_plot():
    global x, y, p, data, curve
    data_temp = list(data)
    x = [item['x'] for item in data_temp]
    y = [item['y'] for item in data_temp]
    curve.setData(x=x, y=y)
    curve.setPos(-(timer.elapsed()), 0)
    # ~ curve.setPos(-(abc), 0)

# ~ timer_ser = pg.QtCore.QTimer()
# ~ timer_ser.timeout.connect(update_ser)
# ~ timer_ser.start(0)

timer_plot = pg.QtCore.QTimer()
timer_plot.timeout.connect(update_plot)
timer_plot.start(10)

#if __name__ == '__main__':
#    import sys
#    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
#        QtGui.QApplication.instance().exec_()

logthread = threading.Thread(target=update_ser)
logthread.running = True
timer = QtCore.QTime()
logthread.start()
app.exec_()
print("Stopping...")
logthread.running = False
logthread.join()
timer_plot.stop()
ser.close()
print("Test finished.")

