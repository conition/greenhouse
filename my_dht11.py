#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals
import time
import pigpio

class DHT11(object):
    def __init__(self, pi, gpio):
        """
        pi (pigpio): an instance of pigpio
        gpio (int): gpio pin number
        """
        self.pi = pi
        self.gpio = gpio
        self.temperature = 0
        self.humidity = 0
        self.either_edge_cb = None
        self.data = []
        
        # Clears the internal gpio pull-up/down resistor
        self.pi.set_pull_up_down(self.gpio, pigpio.PUD_OFF)

        # Monitors EDGE changes using callback.
        self.either_edge_cb = self.pi.callback(
            self.gpio,
            pigpio.EITHER_EDGE,
            self.either_edge_callback
        )

    def either_edge_callback(self, gpio, level, tick):
        """
        Either Edge callbacks, called each time the gpio edge changes.
        Accumulate the 40 data bits from the dht11 sensor.
        """
        self.data.append((tick, level))

    def read(self):
        """
        Start reading over DHT11 sensor.
        """
        self.data = []
        data_bits = []
        
        integ_rh_data = ''
        dec_rh_data = ''
        integ_t_data = ''
        dec_t_data = ''
        checksum_data = ''
        
        self.pi.write(self.gpio, pigpio.LOW)
        time.sleep(0.017) # 17 ms
        self.pi.set_mode(self.gpio, pigpio.INPUT)
        #self.pi.set_watchdog(self.gpio, 200)
        time.sleep(0.2)

        if len(self.data) < 10:
            print("ERROR: NO DATA REVEIVED")
            return False
        
        for idx in range(len(self.data) - 1):
            tick = self.data[idx][0]-self.data[0][0]
            level = self.data[idx][1]
            duration = self.data[idx+1][0]-self.data[idx][0]
            if level == 0:
                type = "sync"
            elif duration < 50:
                type = "Bit 0"
                data_bits.append('0')
            elif duration >= 50:
                type = "Bit 1"
                data_bits.append('1')

            # print("Tick: {}, Level: {}, Duration: {}, Type: {}".format(tick, level, duration, type))


        for idx in range(len(data_bits)-8, len(data_bits)):
            checksum_data += data_bits[idx]

        for idx in range(len(data_bits)-16, len(data_bits)-8):
            dec_t_data += data_bits[idx]

        for idx in range(len(data_bits)-24, len(data_bits)-16):
            integ_t_data += data_bits[idx]

        for idx in range(len(data_bits)-32, len(data_bits)-24):
            dec_rh_data += data_bits[idx]

        for idx in range(len(data_bits)-40, len(data_bits)-32):
            integ_rh_data += data_bits[idx]

        checksum = int(checksum_data, 2)
        dec_temp = int(dec_t_data, 2)
        integ_temp = int(integ_t_data, 2)
        dec_humid = int(dec_rh_data, 2)
        integ_humid = int (integ_rh_data, 2)

        if checksum != (dec_temp + integ_temp + dec_humid + integ_humid) & 0xff:
            print("ERROR: WRONG CHECKSUM")
            return False
        
        # print(data_bits)
        # print("Integral Humidity: {} ({})".format(integ_rh_data, int(integ_rh_data, 2)))
        # print("Decimal Humidity: {} ({})".format(dec_rh_data, int(dec_rh_data, 2)))
        # print("Integral Temperature: {} ({})".format(integ_t_data, int(integ_t_data, 2)))
        # print("Decimal Temperature: {} ({})".format(dec_t_data, int(dec_t_data, 2)))
        # print("Checksum: {} ({})".format(checksum, int(checksum, 2)))

        self.temperature = integ_temp
        self.humidity = integ_humid

        return True
            
    def close(self):
        """
        Stop reading sensor, remove callbacks.
        """
        self.pi.set_watchdog(self.gpio, 0)
        if self.either_edge_cb:
            self.either_edge_cb.cancel()
            self.either_edge_cb = None

if __name__ == '__main__':
    pi = pigpio.pi()
    sensor1 = DHT11(pi, 16)
    sensor2 = DHT11(pi, 17)

    for i in range(200):
        sensor1.read()
        sensor2.read()
        print("Sensor 1: Temperature: {}, Humidity: {}".format(sensor1.temperature, sensor1.humidity))
        print("Sensor 2: Temperature: {}, Humidity: {}".format(sensor2.temperature, sensor2.humidity))
        time.sleep(1)

    sensor1.close()
    sensor2.close()
