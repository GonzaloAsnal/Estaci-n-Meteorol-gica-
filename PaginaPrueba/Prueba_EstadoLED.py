import network
import socket
import time

from machine import Pin,ADC

led=Pin("LED", Pin.OUT)
sensor_temp = ADC(4)

ssid = 'Flia Valinotti'
password = 'yacanto1977'

wlan= network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

def cargar_html():
    try:
        with open("index.html", "r") as archivo:
            return archivo.read()
    except:
        # Fallback: HTML embebido por si el archivo no existe
        return """<!DOCTYPE html><html><body><h1>Error: Archivo HTML no encontrado</h1></body></html>"""

html_template = cargar_html()

max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print('waiting for connection...')
    time.sleep(1)

if wlan.status() != 3:
    raise RuntimeError('network connection failed')
else:
    print('connected')
    status = wlan.ifconfig()
    print( 'ip = ' + status[0] )

addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]

s = socket.socket()
s.bind(addr)
s.listen(1)

print('listening on', addr)
conversion_factor = 3.3 / (65535)

while True:
    try:
        cl, addr = s.accept()
        print('client connected from', addr)
        request = cl.recv(1024)
        print(request)

        request = str(request)
        led_on = request.find('/light/on')
        led_off = request.find('/light/off')
        print('led on = ' + str(led_on))
        print('led off = ' + str(led_off))

        # INICIALIZA stateis con un valor por defecto
        stateis = "Bienvenido - Usa /light/on o /light/off"  # ← Valor por defecto

        if led_on == 6:
            print("led on")
            led.value(1)
            stateis = "LED is ON"

        elif led_off == 6:  # ← Usa elif para evitar conflictos
            print("led off")
            led.value(0)
            stateis = "LED is OFF"

        # También puedes manejar la ruta raíz explícitamente
        root_request = request.find('GET / ')
        if root_request == 6:
            stateis = "Bienvenido - Controla el LED con /light/on o /light/off"
        
        lectura = sensor_temp.read_u16() * conversion_factor
        # Fórmula aproximada según datasheet del RP2040
        temperatura = 27 - (lectura - 0.706)/0.001721
        print("Temperatura interna:", temperatura, "°C")
    
        response = html_template % (stateis,temperatura)
        
        cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        cl.send(response)
        cl.close()

    except OSError as e:
        cl.close()
        print('connection closed')