#!/usr/bin/python3
import time
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import threading, queue
from pathlib import Path
import serial
import serial.tools.list_ports
from collections import deque
from random import uniform
import signal

### USER CONFIG START
device_id = "/dev/ttyUSB0"
logdir = "data/"
## REALTIME PLOT CONFIG
# How many seconds to show on the realtime plot
t_range = 10
# Y range in grams (can be negative)
g_min = -100
g_max = 5000
# Tick spacing
x_tick_spacing = 1
y_tick_spacing = 1000
# Enable or disable minor ticks and gridlines
minor_ticks = True
### USER CONFIG END

#matplotlib.use("Qt5Agg")

maxlen=5000
q = queue.Queue(maxsize=maxlen)

Path(logdir).mkdir(exist_ok=True)

animalname = str(input("Animal name: "))
logname = logdir+animalname+".pasta"

def read_ser(stop_event):
    # Load serial device
    devs = {x.device:x for x in serial.tools.list_ports.comports()}
    if device_id not in devs:
        raise IOError("Serial device not found!")
    else:
        dev = device_id
    baud = 115200
    ser = serial.Serial(dev,baud)
    # Open logfile
    logfile = open(logname, "w")
    # Flush the serial input buffer and start timer
    ser.reset_input_buffer()
    total_time = 0
    time1 = time.perf_counter()
    ser_line = None
    while not stop_event.is_set():
        while ser_line is None:
            try:
                ser_line = ser.readline()
            except ValueError:
                pass
            else:
                total_time += time.perf_counter()-time1
                time1 = time.perf_counter()
                datapoint = { "x": total_time,
                              "y": float(ser_line) }
        ser_line = None
        logfile.write(str(datapoint["x"])+","+str(datapoint["y"])+"\n")
        q.put(datapoint)
    ser.close()
    logfile.close()

def read_ser_dummy(stopper):
    total_time = 0
    time1 = time.perf_counter()
    ser_line = None
    while not stopper.is_set():
        while ser_line is None:
            try:
                #ser_line = ser.readline()
                ser_line = str(round(uniform(0,4000), 2))
                time.sleep(0.0125)
            except ValueError:
                pass
            else:
                total_time += time.perf_counter()-time1
                time1 = time.perf_counter()
                datapoint = { "x": total_time,
                              "y": float(ser_line) }
        ser_line = None
        q.put(datapoint)

def handle_closeplot(_event):
    global G_stopper
    G_stopper.set()

def handle_sigint(_sig, _frame):
    global G_stopper
    G_stopper.set()

class BlitManager:
    def __init__(self, canvas, animated_artists=()):
        """
        Parameters
        ----------
        canvas : FigureCanvasAgg
            The canvas to work with, this only works for sub-classes of the Agg
            canvas which have the `~FigureCanvasAgg.copy_from_bbox` and
            `~FigureCanvasAgg.restore_region` methods.

        animated_artists : Iterable[Artist]
            List of the artists to manage
        """
        self.canvas = canvas
        self._bg = None
        self._artists = []

        for a in animated_artists:
            self.add_artist(a)
        # grab the background on every draw
        self.cid = canvas.mpl_connect("draw_event", self.on_draw)

    def on_draw(self, event):
        """Callback to register with 'draw_event'."""
        cv = self.canvas
        if event is not None:
            if event.canvas != cv:
                raise RuntimeError
        self._bg = cv.copy_from_bbox(cv.figure.bbox)
        self._draw_animated()

    def add_artist(self, art):
        """
        Add an artist to be managed.

        Parameters
        ----------
        art : Artist

            The artist to be added.  Will be set to 'animated' (just
            to be safe).  *art* must be in the figure associated with
            the canvas this class is managing.

        """
        if art.figure != self.canvas.figure:
            raise RuntimeError
        art.set_animated(True)
        self._artists.append(art)

    def _draw_animated(self):
        """Draw all of the animated artists."""
        fig = self.canvas.figure
        for a in self._artists:
            fig.draw_artist(a)

    def update(self):
        """Update the screen with animated artists."""
        cv = self.canvas
        fig = cv.figure
        # paranoia in case we missed the draw event,
        if self._bg is None:
            self.on_draw(None)
        else:
            # restore the background
            cv.restore_region(self._bg)
            # draw all of the animated artists
            self._draw_animated()
            # update the GUI state
            cv.blit(fig.bbox)
        # let the GUI event loop process anything it has to do
        cv.flush_events()

x = deque(maxlen=maxlen)
y = deque(maxlen=maxlen)
plt.style.use("ggplot")
fig, ax = plt.subplots()
plt.grid(visible=True, which="minor", axis="y", alpha=0.5)
ax.set_title("PASTA real-time plot")
ax.set_xlabel("Time [s]")
ax.set_ylabel("Force [g]")
ax.xaxis.set_major_locator(ticker.MultipleLocator(x_tick_spacing))
ax.yaxis.set_major_locator(ticker.MultipleLocator(y_tick_spacing))
if minor_ticks:
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())

plot_stopper = threading.Event()
G_stopper = plot_stopper
fig.canvas.mpl_connect('close_event', handle_closeplot)

line, = ax.plot(0, 0, animated=True)
line.set_linewidth(0.7)
#line.set_color(next(ax._get_lines.prop_cycler)["color"])
# text = ax.text(0.8,0.5, "")

ax.set_xlim([-t_range, 0])
ax.set_ylim([g_min, g_max])

bm = BlitManager(fig.canvas, [line])
plt.show(block=False)
plt.pause(.1)

ser_stopper = threading.Event()
ser_thread = threading.Thread(target=read_ser, args=(ser_stopper,))
ser_thread.start()
signal.signal(signal.SIGINT, handle_sigint)

while not plot_stopper.is_set():
    x_value, y_value = q.get().values()
    if len(x) < maxlen:
        x.appendleft(-x_value)
    y.append(y_value)
    line.set_data(x, y)
    bm.update()

print("Stopping...")
#plt.close("all")
ser_stopper.set()
ser_thread.join()
