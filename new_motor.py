import pigpio
from time import sleep
import math

pi = pigpio.pi()
PIN_STEP = 20
PIN_ENN = 4
PIN_DIR = 21

ACCELERATION_MS2 = 1.5
MAX_VELOCITY_MS = 0.3
HEIGHT_M = 0.5
STEPS_PER_REV = 1200.0
PULLEY_DIAMETER_M = 0.012

PULLEY_CIRCUMF_M = PULLEY_DIAMETER_M * math.pi
STEPS_PER_M = STEPS_PER_REV / PULLEY_CIRCUMF_M
TOTAL_STEPS = HEIGHT_M * STEPS_PER_M

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

delta_t_s = (1 / STEPS_PER_M) / MAX_VELOCITY_MS
const_sequence.append(pigpio.pulse(1<<PIN_STEP, 0, int((1000000 * delta_t_s) / 2)))
const_sequence.append(pigpio.pulse(0, 1<<PIN_STEP, int((1000000 * delta_t_s) / 2)))
num_steps_const_sequence = int(TOTAL_STEPS - (current_steps * 2))
if num_steps_const_sequence >= 0xffff:
    print("burp")

pi.set_mode(PIN_STEP, pigpio.OUTPUT)
pi.set_mode(PIN_ENN, pigpio.OUTPUT)
pi.set_mode(PIN_DIR, pigpio.OUTPUT)

pi.write(PIN_DIR, 0)
pi.write(PIN_ENN, 0)

#for i in range(1600):
#	pi.write(20, 1)
#	sleep(0.0001)
#	pi.write(20, 0)
#	sleep(0.0001)

pi.wave_clear()

pi.wave_add_generic(accel_sequence)
wid_accel = pi.wave_create()

pi.wave_add_generic(decel_sequence)
wid_decel = pi.wave_create()

pi.wave_add_generic(const_sequence)
wid_const = pi.wave_create()

pi.wave_chain([
    wid_accel,
    255, 0,
    wid_const,
    255, 1, num_steps_const_sequence & 0xff, num_steps_const_sequence >> 8,
    wid_decel,
])

while pi.wave_tx_busy():
    sleep(0.1);

pi.wave_clear()

pi.write(PIN_ENN, 1)
