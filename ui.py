import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import pigpio
import time
import math
from my_dht11 import DHT11

from matplotlib.backends.backend_gtk3agg import (
        FigureCanvasGTK3Agg as FigureCanvas)
from matplotlib.figure import Figure
import numpy as np

PIN_STEP = 21
PIN_ENN = 4
PIN_DIR = 20
PIN_LAMP = 26
PIN_FAN = 13
PIN_PUMP = 19
PIN_DHT11_INSIDE = 16
PIN_DHT11_OUTSIDE = 17
PIN_LIGHTGATE = 12

ACCELERATION_MS2 = 0.4
MAX_VELOCITY_MS = 0.2
HEIGHT_M = 0.335
STEPS_PER_REV = 1600.0
PULLEY_DIAMETER_M = 0.012 * (21.3 / 20.0)

PULLEY_CIRCUMF_M = PULLEY_DIAMETER_M * math.pi
STEPS_PER_M = STEPS_PER_REV / PULLEY_CIRCUMF_M
TOTAL_STEPS = HEIGHT_M * STEPS_PER_M
print("total steps: {}".format(TOTAL_STEPS))

DOOR_CLOSED = 0
DOOR_OPEN = 1
DOOR_UNKNOWN = 2

OPEN_DOOR_BUTTON_LABEL = "Open Door"
CLOSE_DOOR_BUTTON_LABEL = "Close Door"


class MyWindow(Gtk.Window):

    def __init__(self):
        #initialize user interface
        Gtk.Window.__init__(self, title="Hello World")
        grid = Gtk.Grid()
        self.add(grid)

        self.pi = pigpio.pi()
        
        #populate user interface

#        f = Figure(figsize=(5, 4), dpi=100)
#        a = f.add_subplot(3, 1, 1)
#        b = f.add_subplot(3, 1, 2)
#        c = f.add_subplot(3, 1, 3)
#        t = np.arange(0.0, 3.0, 0.01)
#        s = np.sin(2*np.pi*t)
#        a.set_title("Automated Indoor Greenhouse")
#        a.plot(t, s)
#        a.plot(t, -s)
#        b.plot(t, s)
#        c.plot(t, s)

        
#        self.plot1 = FigureCanvas(f)
        
        self.lamp_button = Gtk.Button(label="Lamp On/Off")
        self.lamp_button.connect("clicked", self.on_lamp_button_clicked)
        self.lamp_button.set_hexpand(True)
        self.lamp_button.set_vexpand(True)
        
        self.fan_button = Gtk.Button(label="Fan On/Off")
        self.fan_button.connect("clicked", self.on_fan_button_clicked)
        self.fan_button.set_hexpand(True)
        self.fan_button.set_vexpand(True)
        
        self.pump_button = Gtk.Button(label="Pump On/Off")
        self.pump_button.connect("clicked", self.on_pump_button_clicked)
        self.pump_button.set_hexpand(True)
        self.pump_button.set_vexpand(True)
        
        self.door_button = Gtk.Button(label=OPEN_DOOR_BUTTON_LABEL)
        self.door_button.connect("clicked", self.on_door_button_clicked)
        self.door_button.set_hexpand(True)
        self.door_button.set_vexpand(True)

        self.moisture_levelbars = []
        self.moisture_levelbars_labels = []
        for i in range(8):
            self.moisture_levelbars.append(Gtk.LevelBar(min_value=0, max_value=1023, vexpand=True))
            if i % 2 == 1:
                position = "bottom"
            elif i % 2 == 0:
                position = "top"
            self.moisture_levelbars_labels.append(Gtk.Label("Plant {} ({})".format(int(i/2), position), vexpand=True))

        self.last_read_dht11 = 0.0
        self.inside_dht11 = DHT11(self.pi, PIN_DHT11_INSIDE)
        self.outside_dht11 = DHT11(self.pi, PIN_DHT11_OUTSIDE)
        self.inside_dht11_label = Gtk.Label("Inside Greenhouse:")
        self.inside_dht11_temp_label = Gtk.Label("")
        self.inside_dht11_humid_label = Gtk.Label("")
        self.outside_dht11_label = Gtk.Label("Outside Greenhouse:")
        self.outside_dht11_temp_label = Gtk.Label("")
        self.outside_dht11_humid_label = Gtk.Label("")

        self.lightgate_label = Gtk.Label("")
        self.pi.set_mode(PIN_LIGHTGATE, pigpio.INPUT)

        #self.plot1.set_size_request(480, 600)
        #grid.attach(self.plot1, left=0, top=0, width=2, height=1)

        total_num_cols = 3
        
        for i in range(8):
            grid.attach(self.moisture_levelbars_labels[i], left=0, top=2*i, width=total_num_cols, height=1)
            grid.attach(self.moisture_levelbars[i], left=0, top=2*i+1, width=total_num_cols, height=1)

        lightgate_row = 16
        grid.attach(self.lightgate_label, left=0, top=lightgate_row, width=total_num_cols, height=1)
            
        sensor_row = 17
        grid.attach(self.inside_dht11_label,       left=0, top=sensor_row, width=1, height=1)
        grid.attach(self.inside_dht11_temp_label,  left=1, top=sensor_row, width=1, height=1)
        grid.attach(self.inside_dht11_humid_label, left=2, top=sensor_row, width=1, height=1)
        grid.attach(self.outside_dht11_label,      left=0, top=sensor_row+1, width=1, height=1)
        grid.attach(self.outside_dht11_temp_label, left=1, top=sensor_row+1, width=1, height=1)
        grid.attach(self.outside_dht11_humid_label,left=2, top=sensor_row+1, width=1, height=1)

            
        button_row = 19
        grid.attach(self.lamp_button, left=0, top=button_row, width=1, height=1)
        grid.attach(self.fan_button, left=1, top=button_row, width=1, height=1)
        grid.attach(self.pump_button, left=2, top=button_row, width=1, height=1)
        grid.attach(self.door_button, left=0, top=button_row + 1, width=total_num_cols, height=1)
        
        self.fullscreen()
                
        #initialize wave form sequences for door
        accel_sequence = []
        decel_sequence = []
        const_sequence = []

        current_velocity_ms = 0.0
        current_steps = 0.0
        current_height_m = 0.0
        time_since_start_s = 0.001
        
        while current_velocity_ms < MAX_VELOCITY_MS and current_steps < TOTAL_STEPS/2:
            current_velocity_ms = ACCELERATION_MS2 * time_since_start_s
            delta_t_s = (1 / STEPS_PER_M) / current_velocity_ms
            #                              	 ON   	 OFF         DELAY
            accel_sequence.append(pigpio.pulse(1<<PIN_STEP, 0, int((1000000 * delta_t_s) / 2)))
            accel_sequence.append(pigpio.pulse(0, 1<<PIN_STEP, int((1000000 * delta_t_s) / 2)))
            
            decel_sequence.insert(0, pigpio.pulse(0, 1<<PIN_STEP, int((1000000 * delta_t_s) / 2)))
            decel_sequence.insert(0, pigpio.pulse(1<<PIN_STEP, 0, int((1000000 * delta_t_s) / 2)))
            
            current_steps += 1
            time_since_start_s += delta_t_s

        print("accel/decel steps: {}".format(current_steps))
        
        delta_t_s = (1 / STEPS_PER_M) / MAX_VELOCITY_MS
        const_sequence.append(pigpio.pulse(1<<PIN_STEP, 0, int((1000000 * delta_t_s) / 2)))
        const_sequence.append(pigpio.pulse(0, 1<<PIN_STEP, int((1000000 * delta_t_s) / 2)))
        self.num_steps_const_sequence = int(TOTAL_STEPS - (current_steps * 2))
        if self.num_steps_const_sequence >= 0xffff:
            print("burp")

        #initialize door control
        self.pi.set_mode(PIN_STEP, pigpio.OUTPUT)
        self.pi.set_mode(PIN_ENN, pigpio.OUTPUT)
        self.pi.set_mode(PIN_DIR, pigpio.OUTPUT)


        self.pi.wave_clear()

        self.pi.wave_add_generic(accel_sequence)
        self.wid_accel = self.pi.wave_create()

        self.pi.wave_add_generic(decel_sequence)
        self.wid_decel = self.pi.wave_create()

        self.pi.wave_add_generic(const_sequence)
        self.wid_const = self.pi.wave_create()

        self.door_position = DOOR_CLOSED

        #initialize lamp control
        self.pi.set_mode(PIN_LAMP, pigpio.OUTPUT)
        self.lamp_state = 0

        #initialize fan control
        self.pi.set_mode(PIN_FAN, pigpio.OUTPUT)
        self.fan_state = 0

        #initialize pump control
        self.pi.set_mode(PIN_PUMP, pigpio.OUTPUT)
        self.pump_state = 0

        #initialize moisture sensors

        # Open SPI bus
        self.spi = self.pi.spi_open(spi_channel=0, baud=1000000, spi_flags=0)

        # initialize timer to periodically read sensor data
        self.timeout_id = GLib.timeout_add(200, self.on_periodic_timer)

            
    # Function to read SPI data from MCP3008 chip
    # Channel must be an integer 0-7
    def read_mcp_3008(self, channel):
        count, adc = self.pi.spi_xfer(self.spi, [1,(8+channel)<<4,0])
        data = ((adc[1]&3) << 8) + adc[2]
        return data
        
    def on_lamp_button_clicked(self, widget):
        self.lamp_state = 1- self.lamp_state
        self.pi.write(PIN_LAMP, self.lamp_state)
        print("Lamp: {}".format(self.lamp_state))

    def on_fan_button_clicked(self, widget):
        self.fan_state = 1- self.fan_state
        self.pi.write(PIN_FAN, self.fan_state)
        print("Fan: {}".format(self.fan_state))

    def on_pump_button_clicked(self, widget):
        self.pump_state = 1- self.pump_state
        self.pi.write(PIN_PUMP, self.pump_state)
        print("Pump: {}".format(self.pump_state))
        
    def on_door_button_clicked(self, widget):
        print("Hello World")

        if self.door_position == DOOR_CLOSED:
            self.pi.write(PIN_DIR, 0)
        elif self.door_position == DOOR_OPEN:
            self.pi.write(PIN_DIR, 1)
        else:
            self.pi.write(PIN_ENN, 1)
            return
        
        self.pi.write(PIN_ENN, 0)

        
        self.pi.wave_chain([
            self.wid_accel,
            255, 0,
            self.wid_const,
            255, 1, self.num_steps_const_sequence & 0xff, self.num_steps_const_sequence >> 8,
            self.wid_decel,
        ])

        while self.pi.wave_tx_busy():
            time.sleep(0.1);

        self.door_position = 1 - self.door_position

        if self.door_position == DOOR_CLOSED:
            self.pi.write(PIN_ENN, 1)
            self.door_button.set_label(OPEN_DOOR_BUTTON_LABEL)
        else:
            self.door_button.set_label(CLOSE_DOOR_BUTTON_LABEL)

    def on_periodic_timer(self):
        self.moisture_data = np.zeros(8)
        for i in range(8):
            self.moisture_data[i] = self.read_mcp_3008(i)
            self.moisture_levelbars[i].set_value(self.moisture_data[i])
        print(self.moisture_data)

        if (time.time() - self.last_read_dht11 >= 1):
            self.inside_dht11.read()
            self.outside_dht11.read()
            self.inside_dht11_temp_label.set_text("{} °".format(self.inside_dht11.temperature))
            self.inside_dht11_humid_label.set_text("{} %".format(self.inside_dht11.humidity))
            self.outside_dht11_temp_label.set_text("{} °".format(self.outside_dht11.temperature))
            self.outside_dht11_humid_label.set_text("{} %".format(self.outside_dht11.humidity))
            self.last_read_dht11 = time.time()

        self.lightgate_label.set_text("Lightgate: {}".format(self.pi.read(PIN_LIGHTGATE)))
        
        return True
        
win = MyWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
