import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import pigpio
from time import sleep
import math

PIN_STEP = 21
PIN_ENN = 4
PIN_DIR = 20
PIN_LAMP = 26
PIN_FAN = 13
PIN_PUMP = 19

ACCELERATION_MS2 = 1.5
MAX_VELOCITY_MS = 0.2
HEIGHT_M = 0.5
STEPS_PER_REV = 1600.0
PULLEY_DIAMETER_M = 0.012

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
        
        grid.attach(self.lamp_button, left=0, top=0, width=1, height=1)
        grid.attach(self.fan_button, left=0, top=1, width=1, height=1)
        grid.attach(self.pump_button, left=0, top=2, width=1, height=1)
        grid.attach(self.door_button, left=0, top=3, width=1, height=1)
        
        self.fullscreen()
                
        #initialize wave form sequences for door
        self.pi = pigpio.pi()
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
            sleep(0.1);

        self.door_position = 1 - self.door_position

        if self.door_position == DOOR_CLOSED:
            self.pi.write(PIN_ENN, 1)
            self.door_button.set_label(OPEN_DOOR_BUTTON_LABEL)
        else:
            self.door_button.set_label(CLOSE_DOOR_BUTTON_LABEL)
        
win = MyWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
