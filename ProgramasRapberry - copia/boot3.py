
try:
  import usocket as socket
except:
  import socket

import network

import gc
gc.collect()

ssid = 'MANICARDI 2.4'
password = '00422648275'

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())
