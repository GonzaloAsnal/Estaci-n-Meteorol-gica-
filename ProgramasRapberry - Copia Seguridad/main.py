from machine import Pin, I2C, ADC, Timer,SPI, SoftSPI,RTC
from ssd1306 import SSD1306_I2C
from menuoled import MENU, MENU_ICONS, NAVIGATE_MENU
import ubuntu_15
from encoder import Rotary
import dht
import framebuf
import utime
import math
import sdcard
import usys
import uos
import network
import ntptime
import ustruct as struct
from micropython import const
from bmp280 import *
from collections import deque
import socket

#variables que contienen los valores instantáneos
presion = 0
conGases = 0
conParticulas = 0
temp = 0
hum = 0
velocidad_viento_actual = 0
valor_db = 0
valor_uv = 0
punto_cardinal = "-"
lluvia_acumulada = 0

'''
MENÚ INSTANTÁNEO INFORMATIVO OLED 
'''
WIDTH = 128
HEIGHT = 64

i2c = I2C(1, scl = Pin(15), sda = Pin(14), freq=400000)

oled = SSD1306_I2C(WIDTH, HEIGHT, i2c)

pantalla = 0

actuador = Pin(21,Pin.OUT)

#función para traer iconos de la memoria interna de la rb
def Abrir_Icono(ruta_icono):
    doc = open(ruta_icono, "rb")
    doc.readline()
    xy = doc.readline()
    x = int(xy.split()[0])
    y = int(xy.split()[1])
    icono = bytearray(doc.read())
    doc.close()
    return framebuf.FrameBuffer(icono, x, y, framebuf.MONO_HLSB)

oled.blit(Abrir_Icono("icons/utn.pbm"), 0, 20)
oled.blit(Abrir_Icono("icons/logo_utn.pbm"), 65, 22)

oled.show()
utime.sleep(2)

'''
WIFI-FECHA INICIAL
'''

rtc = RTC()
wifi_ssid = "w-labelectronica"
wifi_password = "electronicafrvm"

# Configura la conexión WiFi

def check_internet():
    try:
        addr = socket.getaddrinfo('www.google.com', 80)[0][-1]
        s = socket.socket()
        s.connect(addr)
        s.close()
        return True
    except OSError as e:
        print("No hay conexión a internet:", e)
        return False

def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # Configuración estática de IP
    ip = '192.168.104.180'  # Asegúrate de que esta IP no esté en uso
    subnet = '255.255.255.0'
    gateway = '192.168.104.1'
    dns = '8.8.8.8'
    
    oled.fill(0)
    oled.text("Config IP statica", 2, 2)
    oled.show()
    utime.sleep(2)
    
    try:
        wlan.ifconfig((ip, subnet, gateway, dns))
        oled.fill(0)
        oled.text("IP Configurada", 2, 2)
        oled.show()
        utime.sleep(2)
    except Exception as e:
        oled.fill(0)
        oled.text("Error IP Config", 2, 2)
        oled.text(str(e), 2, 12)
        oled.show()
        return
    
    oled.fill(0)
    oled.text("Conectando WiFi", 2, 2)
    oled.show()
    utime.sleep(2)
    
    if not wlan.isconnected():
        print("Conectando a la red WiFi...")
        wlan.connect(ssid, password)
        
        # Esperar a que se conecte
        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            utime.sleep(1)
            max_wait -= 1
            print("Intentando conectar...")

    oled.fill(0)
    if wlan.isconnected():
        oled.text("Conexion exitosa", 2, 2)
        oled.text(wlan.ifconfig()[0], 2, 12)
        print("Conexion exitosa")
        print(wlan.ifconfig())
    else:
        oled.text("Fallo al conectar", 2, 2)
        print("Fallo al conectar")
        oled.show()
        return
    
    oled.fill(0)
    oled.text("Verificando internet", 2, 2)
    oled.show()
    utime.sleep(2)
    
    if check_internet():
        try:
            ntptime.settime()
            oled.fill(0)
            oled.text("Fecha y hora obtenidas", 2, 2)
            oled.show()
            print("Fecha y hora obtenidas con éxito")
        except OSError as e:
            oled.fill(0)
            oled.text("Error NTP:", 2, 2)
            oled.text(str(e), 2, 12)
            oled.show()
            print("Error al obtener la fecha y hora:", e)
    else:
        oled.fill(0)
        oled.text("Sin internet", 2, 2)
        oled.show()
        print("No hay conexión a internet")
        
def check_internet_connection():
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()

# Obtener fecha y hora de un servidor de tiempo en red
def get_datetime():
    print("Obteniendo la fecha y hora...")
    try:
        ntptime.settime()
        print("Fecha y hora obtenidas con éxito")
    except OSError as e:
        print("Error al obtener la fecha y hora:", e)

# Ajuste de la zona horaria (GMT-5 en este caso)
timezone_offset = -3 * 60 * 60  # 5 horas en segundos

# Conectar a la red WiFi

connect_to_wifi(wifi_ssid, wifi_password)

# Obtener fecha y hora
get_datetime()

# Obtener la hora ajustada por el offset de la zona horaria
hora_actual = utime.localtime()
hora_unix = utime.mktime(hora_actual)  # Convertir la hora actual a segundos desde el epoch
hora_ajustada = utime.localtime(hora_unix + timezone_offset)

# Asegurarse de que la hora ajustada esté en el formato correcto para el RTC
hora_ajustada_para_rtc = (hora_ajustada[0], hora_ajustada[1], hora_ajustada[2],
                          hora_ajustada[6] % 7, hora_ajustada[3],  # Sin ajuste directo aquí
                          hora_ajustada[4], hora_ajustada[5], 0)

rtc.datetime(hora_ajustada_para_rtc)

# Mostrar la fecha y hora actual ajustada
print("Fecha y hora actual ajustada:", hora_ajustada_para_rtc)

year, month, day, weekday, hours, minutes, seconds, subseconds = rtc.datetime()
formatted_datetime = "{}/{}/{} {}:{}"
print(str(formatted_datetime.format(day, month, year, hours, minutes)))

#---------------------------web---------------------------------------------

import gc
#se usa socket que ya se lo importó en la conexión de red
import urequests

clima = "Soleado"

#Funcion que devuelve el HTML que se debe leer a partir del nombre que el index le asocia a la página
def get_page_content(page_name):
    if page_name == "Anemometro":
        return ("/sd/Anemometro.txt",1)
    elif page_name == "pluviometro":
        return ("/sd/pluviometro.txt",2)
    elif page_name == "Veleta":
        return ("/sd/veleta.txt",3)
    elif page_name == "Temperatura":
        return ("/sd/Temperatura.txt",4)
    elif page_name == "Humedad":
        return ("/sd/humedad.txt",5)
    elif page_name == "particulas":
        return ("/sd/particulas.txt",6)
    elif page_name == "gas":
        return ("/sd/gas.txt",7)
    elif page_name == "SensorDePresion":
        return ("/sd/presion.txt",8)
    elif page_name == "SensorUV":
        return ("/sd/uv.txt",9)
    elif page_name == "Decibelimetro":
        return ("/sd/decibelimetro.txt",10)
    elif page_name == "index":
        return ("/sd/index.txt", 5)
    else:
        return ("/sd/index.txt", 5)
        
#Calculo de frecuencias de las mediciones para mostrar en la veleta
def datosVeleta(contenido,valoresh,valoreshs,valores7d,valores31d,valores12m):
    global punto_cardinal,clima
    
    #['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO']
    contenido = contenido.replace("@@@", f"{clima}")
    contenido = contenido.replace("!!Veleta!!", f"{punto_cardinal}")
    
    if contenido.find("!!VALORESHORA"):
        frecuenciash=[0,0,0,0,0,0,0,0]
        
        for i in range (0,len(valoresh),1):
            if valoresh[i]=="N":
                frecuenciash[0]=frecuenciash[0]+1
            elif valoresh[i]=="NE":
                frecuenciash[1]=frecuenciash[1]+1
            elif valoresh[i]=="E":
                frecuenciash[2]=frecuenciash[2]+1
            elif valoresh[i]=="SE":
                frecuenciash[3]=frecuenciash[3]+1
            elif valoresh[i]=="S":
                frecuenciash[4]=frecuenciash[4]+1
            elif valoresh[i]=="SO":
                frecuenciash[5]=frecuenciash[5]+1
            elif valoresh[i]=="O":
                frecuenciash[6]=frecuenciash[6]+1
            elif valoresh[i]=="NO":
                frecuenciash[7]=frecuenciash[7]+1
            else:
                pass
    
        contenido = contenido.replace("!!VALORESHORA",f"{frecuenciash}")
    
    if contenido.find("!!VALORESHS"):
        
        frecuenciashs=[0,0,0,0,0,0,0,0]
        
        for i in range (0,len(valoreshs),1):
            if valoreshs[i]=="N":
                frecuenciashs[0]=frecuenciashs[0]+1
            elif valoreshs[i]=="NE":
                frecuenciashs[1]=frecuenciashs[1]+1
            elif valoreshs[i]=="E":
                frecuenciashs[2]=frecuenciashs[2]+1
            elif valoreshs[i]=="SE":
                frecuenciashs[3]=frecuenciashs[3]+1
            elif valoreshs[i]=="S":
                frecuenciashs[4]=frecuenciashs[4]+1
            elif valoreshs[i]=="SO":
                frecuenciashs[5]=frecuenciashs[5]+1
            elif valoreshs[i]=="O":
                frecuenciashs[6]=frecuenciashs[6]+1
            elif valoreshs[i]=="NO":
                frecuenciashs[7]=frecuenciashs[7]+1
            else:
                pass
        
        contenido = contenido.replace("!!VALORESHS",f"{frecuenciashs}")
       
    if contenido.find("!!VALORES7D"):
        
        frecuencias7d=[0,0,0,0,0,0,0,0]
        
        for i in valores7d:
            if i=="N":
                frecuencias7d[0]=frecuencias7d[0]+1
            elif i=="NE":
                frecuencias7d[1]=frecuencias7d[1]+1
            elif i=="E":
                frecuencias7d[2]=frecuencias7d[2]+1
            elif i=="SE":
                frecuencias7d[3]=frecuencias7d[3]+1
            elif i=="S":
                frecuencias7d[4]=frecuencias7d[4]+1
            elif i=="SO":
                frecuencias7d[5]=frecuencias7d[5]+1
            elif i=="O":
                frecuencias7d[6]=frecuencias7d[6]+1
            elif i=="NO":
                frecuencias7d[7]=frecuencias7d[7]+1
            else:
                pass
                
        contenido = contenido.replace("!!VALORES7D",f"{frecuencias7d}")
    
    if contenido.find("!!VALORES1M"):
        frecuencias31d=[0,0,0,0,0,0,0,0]
        
        for i in valores31d:
            if i=="N":
                frecuencias31d[0]=frecuencias31d[0]+1
            elif i=="NE":
                frecuencias31d[1]=frecuencias31d[1]+1
            elif i=="E":
                frecuencias31d[2]=frecuencias31d[2]+1
            elif i=="SE":
                frecuencias31d[3]=frecuencias31d[3]+1
            elif i=="S":
                frecuencias31d[4]=frecuencias31d[4]+1
            elif i=="SO":
                frecuencias31d[5]=frecuencias31d[5]+1
            elif i=="O":
                frecuencias31d[6]=frecuencias31d[6]+1
            elif i=="NO":
                frecuencias31d[7]=frecuencias31d[7]+1
            else:
                pass
                
        contenido = contenido.replace("!!VALORES1M",f"{frecuencias31d}")
    
    if contenido.find("!!VALORES12M"):
        frecuencias12m=[0,0,0,0,0,0,0,0]
        
        for i in valores12m:
            if i=="N":
                frecuencias12m[0]=frecuencias12m[0]+1
            elif i=="NE":
                frecuencias12m[1]=frecuencias12m[1]+1
            elif i=="E":
                frecuencias12m[2]=frecuencias12m[2]+1
            elif i=="SE":
                frecuencias12m[3]=frecuencias12m[3]+1
            elif i=="S":
                frecuencias12m[4]=frecuencias12m[4]+1
            elif i=="SO":
                frecuencias12m[5]=frecuencias12m[5]+1
            elif i=="O":
                frecuencias12m[6]=frecuencias12m[6]+1
            elif i=="NO":
                frecuencias12m[7]=frecuencias12m[7]+1
            else:
                pass
    
    
        contenido = contenido.replace("!!VALORES12M",f"{frecuencias12m}")
        
    return(contenido)
   
# Lee cada linea de los HTML para reemplazarlos por  
def PaginaWeb(contenido,posicion,pg):
    global velocidad_viento_actual,clima,punto_cardinal,temp,hum,conParticulas,conGases,presion,valor_uv,valor_db,horash,valoresh, horashs,valoreshs,horas7d,valores7d,horas31d,valores31d,horas12m,valores12m

    horas=[]
    valores=[]
    if pg == '/sd/Anemometro.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!Anemometro!!", f"{velocidad_viento_actual}")
        
    if pg == '/sd/pluviometro.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!Pluviometro!!", f"{clima}")
        
    if pg == '/sd/veleta.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!Veleta!!", f"{punto_cardinal}")
        
    if pg == '/sd/Temperatura.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!Temperatura!!", f"{temp}")
        
    if pg == '/sd/humedad.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!Humedad!!", f"{hum}")
    
    if pg == '/sd/particulas.txt' or pg =='/sd/index.txt':
        if conParticulas<=2:
            particulado = "Bajo contenido de particulas"
        elif conParticulas<20000:
            particulado = "Cantidad moderada de particulas"
        else:
            particulado = "Alto contenido de particulas"
        contenido = contenido.replace("!!Particulas!!", f"{particulado}")
          
    if pg == '/sd/gas.txt' or pg =='/sd/index.txt':
        if conGases<=2000:
            gasificado = "Ambiente libre de gases"
        elif conGases<10000:
            gasificado = "Cantidad de gases moderada en el ambiente"
        else:
            gasificado = "Alta cantidad de gases en el ambiente"
        contenido = contenido.replace("!!Gas!!", f"{gasificado}")
    
    if pg == '/sd/presion.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!Presion!!", f"{presion}")
        
    if pg == '/sd/uv.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!UV!!", f"{valor_uv}")
    
    if pg == '/sd/decibelimetro.txt' or pg =='/sd/index.txt':
        contenido = contenido.replace("!!DB!!", f"{valor_db}")
        
    contenido = contenido.replace("@@@", f"{clima}")
    
    if pg != '/sd/index.txt':
        contenido = contenido.replace("!!HORAS",f"{horashs}")
        contenido = contenido.replace("!!VALORESHS",f"{valoreshs}")
        
        contenido = contenido.replace("!!7DIAS",f"{horas7d}")
        contenido = contenido.replace("!!VALORES7D",f"{valores7d}")
        
        contenido = contenido.replace("!!1MES",f"{horas31d}")
        contenido = contenido.replace("!!VALORES1M",f"{valores31d}")
        
        contenido = contenido.replace("!!12MES",f"{horas12m}")
        contenido = contenido.replace("!!VALORES12M",f"{valores12m}")
        
        contenido = contenido.replace("!!HORA",f"{horash}")
        contenido = contenido.replace("!!VALORESH",f"{valoresh}")
                
    return contenido

#Crear objeto Socket
'''
establece un servidor TCP/IP que escucha en el puerto 80, que es el puerto estándar para HTTP
servidor utilizado para servir páginas web a través del protocolo HTTP hasta 5 conexiones
'''

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)

#Se leen cada archivo de datos almacenado para crear los vectores requeridos en los graficos

def leerDatosh(posicion, lectura):
    horas = []
    valores = []
    with open("/sd/datosH.csv", "r") as file:
        lines = file.readlines()[-30:]
        for line in lines:
            contenido = line.strip().split(";")
            horas.append(contenido[0])
            if lectura:
                valores.append(float(contenido[posicion]))
            else:
                valores.append(contenido[posicion])
    return (horas, valores)

def leerDatoshs(posicion, lectura):
    horas = []
    valores = []
    with open("/sd/datosHS.csv", "r") as file:
        lines = file.readlines()[-24:]
        for line in lines:
            contenido = line.strip().split(";")
            horas.append(contenido[0])
            if lectura:
                valores.append(float(contenido[posicion]))
            else:
                valores.append(contenido[posicion])
    return (horas, valores)

def leerDatos7d(posicion, lectura):
    horas = []
    valores = []
    with open("/sd/datosD.csv", "r") as file:
        lines = file.readlines()[-7:]
        for line in lines:
            contenido = line.strip().split(";")
            horas.append(contenido[0])
            if lectura:
                valores.append(float(contenido[posicion]))
            else:
                valores.append(contenido[posicion])
    return (horas, valores)

def leerDatos31d(posicion, lectura):
    horas = []
    valores = []
    with open("/sd/datosD.csv", "r") as file:
        lines = file.readlines()[-31:]
        for line in lines:
            contenido = line.strip().split(";")
            horas.append(contenido[0])
            if lectura:
                valores.append(float(contenido[posicion]))
            else:
                valores.append(contenido[posicion])
    return (horas, valores)

def leerDatos12m(posicion, lectura):
    horas = []
    valores = []
    with open("/sd/datosM.csv", "r") as file:
        lines = file.readlines()[-12:]
        for line in lines:
            contenido = line.strip().split(";")
            horas.append(contenido[0])
            if lectura:
                valores.append(float(contenido[posicion]))
            else:
                valores.append(contenido[posicion])
    return (horas, valores)


#---------------------------fin-web-----------------------------------------


oled.fill_rect(0, 0, 128, 64, 0)

def show_main_menu():
    global pantalla
    oled.text("UTN", 99, 0)
    oled.text("FRVM", 95, 9)
    if pantalla == 0: main_menu.draw()
    elif pantalla == 1: main_menu2.draw()
    elif pantalla == 2: main_menu3.draw()
    elif pantalla == 3: main_menu4.draw()
    
def show_temp():
    menu_extras.internal_var = "temp"
    show_main_menu()
    update_info()


def show_hum():
    menu_extras.internal_var = "hum"
    show_main_menu()
    update_info()


def show_press():
    menu_extras.internal_var = "press"
    show_main_menu()
    update_info()

def show_aire():
    menu_extras.internal_var = "aire"
    show_main_menu()
    update_info()


def show_db():
    menu_extras.internal_var = "db"
    show_main_menu()
    update_info()


def show_gas():
    menu_extras.internal_var = "gas"
    show_main_menu()
    update_info()

def show_brujula():
    menu_extras.internal_var = "brujula"
    show_main_menu()
    update_info()


def show_viento():
    menu_extras.internal_var = "viento"
    show_main_menu()
    update_info()


def show_lluvia():
    menu_extras.internal_var = "lluvia"
    show_main_menu()
    update_info()

def show_uv():
    menu_extras.internal_var = "uv"
    show_main_menu()
    update_info()


def show_tiempo():
    menu_extras.internal_var = "tiempo"
    show_main_menu()
    update_info()


def show_info():
    menu_extras.internal_var = "info"
    show_main_menu()
    update_info()
    
def show_flecha():
    menu_extras.setInternalVar("flecha")
    show_main_menu()
    update_info()


def update_info():
    global pantalla, temp, hum, valor_db, valor_uv, conParticulas, conGases, presion,velocidad_viento_max,velocidad_viento_actual,punto_cardinal,lluvia_acumulada,indice_PM1O
    
    oled.fill_rect(0, 19, 127, 55, 0)

    if menu_extras.internal_var == "temp":
        oled.text("Temperatura", 21, 19)
        oled.text(str(temp), 48, 32)
        oled.text("C", 84, 32)
        oled.text("S. Termica", 26, 43)
        oled.text(str(round(13.12+0.6215*temp-11.37*pow(velocidad_viento_actual,0.16)+0.3965*temp*pow(velocidad_viento_actual,0.16),1)), 48, 55)
        oled.text("C", 84, 55)
        # oled_option.centerText(t, 34)

    elif menu_extras.internal_var == "hum":
        menu_extras.text("Humedad", 32, 20)
        menu_extras.text(str(hum), 39, 38)
        menu_extras.text("%", 71, 38)
        # oled_option.centerText(h, 34)

    elif menu_extras.internal_var == "press":
        menu_extras.text("Presion", 40, 20)
        menu_extras.text(str(presion), 33, 38)
        menu_extras.text("hPa", 73, 38)
        # oled_option.centerText(p, 34)

    elif menu_extras.internal_var == "flecha":
        
        pantalla += 1
        if pantalla == 4: pantalla = 0
        
        menu_extras.internal_var = ""
        show_main_menu()
        
    elif menu_extras.internal_var == "db":
        menu_extras.text("Decibelios", 32, 20)
        menu_extras.text(str(valor_db), 40, 38)
        menu_extras.text("dB", 71, 38)
        # oled_option.centerText(h, 34)

    elif menu_extras.internal_var == "gas":
        menu_extras.text("Concentracion", 20, 18)
        menu_extras.text("de gases", 40, 32)
        menu_extras.text(str(conGases), 39, 50)
        oled.text("ppm", 81, 56)
        # oled_option.centerText(p, 34)

    elif menu_extras.internal_var == "brujula":
        menu_extras.text("Direccion", 36, 18)
        menu_extras.text("del viento", 35, 32)
        menu_extras.text(punto_cardinal, 58, 50)
        
    elif menu_extras.internal_var == "viento":
        menu_extras.text("Velocidad", 33, 18)
        menu_extras.text("del viento", 35, 32)
        menu_extras.text(str(velocidad_viento_actual), 39, 50)
        oled.text("km/h", 67, 56)
        
        # oled_option.centerText(h, 34)

    elif menu_extras.internal_var == "lluvia":
        menu_extras.text("Precipitaciones", 17, 20)
        menu_extras.text(str(round(lluvia_acumulada,1)), 35, 38)
        menu_extras.text("mm", 65, 38)
        # oled_option.centerText(p, 34)

    elif menu_extras.internal_var == "uv":
        menu_extras.text("Indice UV", 32, 20)
        menu_extras.text(str(valor_uv), 58, 38)
    
    elif menu_extras.internal_var == "info":
        oled.text("Estacion meteo_", 0, 20)
        oled.text("rologica by:", 0, 29)
        oled.text("Alaniz Andres", 0, 38)
        oled.text("Forneris Julian", 0, 47)
        oled.text("Manicardi Ramiro", 0, 56)

    elif menu_extras.internal_var == "tiempo":
        menu_extras.text("Fecha y hora", 26, 20)
        year, month, day, weekday, hours, minutes, seconds, subseconds = rtc.datetime()
        formatted_datetime = "{}/{}/{} {}:{}"
        menu_extras.text(str(formatted_datetime.format(day, month, year, hours, minutes)), 8, 38)
        # oled_option.centerText(p, 34)

    elif menu_extras.internal_var == "aire":
        menu_extras.text("Concen. de polvo", 10, 17)
        menu_extras.text(str(conParticulas), 39, 33)
        oled.text("ppm", 81, 38)
        oled.text(indice_PM1O, 1, 55)
    
    oled.show()


# bme = BME280(i2c=i2c)


#-------Menu Nº1------------

main_menu = MENU_ICONS(oled, n_icons_x=4, n_icons_y=1, separate=3)

main_menu.add_option("temperatura", show_temp, 0, 0)
main_menu.add_option("humedad", show_hum, 1, 0)
main_menu.add_option("presion", show_press, 2, 0)
main_menu.add_option("flechav2-final", show_flecha, 3, 0)

menu_list = [main_menu]

menu = NAVIGATE_MENU(menu_list)

#-------Menu Nº2------------

main_menu2 = MENU_ICONS(oled, n_icons_x=4, n_icons_y=1, separate=3)

main_menu2.add_option("aire_final", show_aire, 0, 0)
main_menu2.add_option("db_final", show_db, 1, 0)
main_menu2.add_option("gas_final", show_gas, 2, 0)
main_menu2.add_option("flechav2-final", show_flecha, 3, 0)

menu_list2 = [main_menu2]

menu2 = NAVIGATE_MENU(menu_list2)

#-------Menu Nº3------------

main_menu3 = MENU_ICONS(oled, n_icons_x=4, n_icons_y=1, separate=3)

main_menu3.add_option("brujula-final", show_brujula, 0, 0)
main_menu3.add_option("viento-final", show_viento, 1, 0)
main_menu3.add_option("lluvia-final", show_lluvia, 2, 0)
main_menu3.add_option("flechav2-final", show_flecha, 3, 0)

menu_list3 = [main_menu3]

menu3 = NAVIGATE_MENU(menu_list3)

#-------Menu Nº4------------

main_menu4 = MENU_ICONS(oled, n_icons_x=4, n_icons_y=1, separate=3)

main_menu4.add_option("uv-final", show_uv, 0, 0)
main_menu4.add_option("tiempo_final", show_tiempo, 1, 0)
main_menu4.add_option("info-final", show_info, 2, 0)
main_menu4.add_option("flechav2-final", show_flecha, 3, 0)

menu_list4 = [main_menu4]

menu4 = NAVIGATE_MENU(menu_list4)

#--------------------------

menu_extras = MENU(oled)
menu_extras.setFont(ubuntu_15)

rotary = Rotary(3,2,4)


def rotary_changed(change):
    if change == Rotary.ROT_CCW:
        
        if pantalla == 0 : menu.navigate("left")
        elif pantalla == 1 : menu2.navigate("left")
        elif pantalla == 2 : menu3.navigate("left")
        elif pantalla == 3 : menu4.navigate("left")

    elif change == Rotary.ROT_CW:
        
        if pantalla == 0 : menu.navigate("right")
        elif pantalla == 1 : menu2.navigate("right")
        elif pantalla == 2 : menu3.navigate("right")
        elif pantalla == 3 : menu4.navigate("right")
    update_info()
    
def button_changed(change):
    if change == Rotary.SW_PRESS:
        
        if pantalla == 0 : menu.select()
        elif pantalla == 1 : menu2.select()
        elif pantalla == 2 : menu3.select()
        elif pantalla == 3 : menu4.select()

    elif change == Rotary.SW_RELEASE:
        pass
    update_info()
    
    
rotary.add_handler(rotary_changed)
rotary.add_handler(button_changed)


show_temp()

'''
TARJETA SD
'''
def iniciar_registro():
    CS_PIN = Pin(17, Pin.OUT)
    spi = SPI(0, baudrate=1000000, polarity=0, phase=0, bits=8, firstbit=SPI.MSB, sck=Pin(18), mosi=Pin(19), miso=Pin(16))#miso 16 azul, cs 17 blanco, sck 18 gris y tx 19 lila. Negro 3.3V, Amarillo gnd y Verde 5V

    sd = sdcard.SDCard(spi, CS_PIN)

    vfs = uos.VfsFat(sd)
    uos.mount(vfs, "/sd")

    return "/sd/curva.txt"

def almacenar_lista(archivo, lista):
    with open(archivo, "a") as file:
        # Convertir todos los elementos de la lista a cadenas y unirlos con comas
        linea = ",".join(map(str, lista))
        file.write(linea + '\n')
        file.flush()  # Forzar la escritura de datos en el archivo

# Uso de la función
archivo = iniciar_registro()
'''
FIN SD-WIFI
'''

dht_pin = Pin(0)
d = dht.DHT22(dht_pin)

t1 = utime.ticks_ms()

tiempo_inicial = utime.ticks_ms()
radio = 0.102
pi = math.radians(180)

brujula = "-"
punto_cardinal = "-"

lectura = 0

nivel_voltaje = ADC(27)

# display.invert(1)
#display.contrast(100)

salida_comparador = Pin(22, machine.Pin.IN, machine.Pin.PULL_DOWN)

def conversion(boton):
      global t1, brujula, salida_comparador, punto_cardinal,lectura
      t2 = utime.ticks_ms()
      if (t2 - t1) > 500:
            actuador.value(1)
            print("\n -------------------------------")
            print("\n Leyendo")
            print("\n -------------------------------")
            lectura = nivel_voltaje.read_u16()
            print("lec: ",lectura)
            lectura_str = zfill_manual(lectura, 4)
            brujula = lectura_str
            
            if lectura >  5000 and lectura < 11000: punto_cardinal = "NO"
            if lectura > 11000 and lectura < 16000: punto_cardinal = "O"
            if lectura > 16000 and lectura < 22000: punto_cardinal = "SO"
            if lectura > 22000 and lectura < 27000: punto_cardinal = "S"
            if lectura > 27000 and lectura < 33000: punto_cardinal = "SE"
            if lectura > 33000 and lectura < 39000: punto_cardinal = "E"
            if lectura > 39000 and lectura < 45000: punto_cardinal = "NE"
            if lectura > 45000: punto_cardinal = "N"
            
            print("lec: ",punto_cardinal)
            actuador.value(0)         
            t1=t2

salida_comparador.irq(trigger=Pin.IRQ_RISING, handler=conversion)

def zfill_manual(valor, a):
      return '{:0>{w}}'.format(valor, w=a)

sensor_hall = Pin(10, machine.Pin.IN, machine.Pin.PULL_DOWN)
duracion_medicion_ms = 6000

# Función para medir las RPM durante un período específico
def medir_rpm(duracion_ms):
    cambios_estado = 0
    tiempo_inicio = utime.ticks_ms()
    estado_anterior = sensor_hall.value()
    print("aca1")
    while utime.ticks_diff(utime.ticks_ms(), tiempo_inicio) < duracion_ms:
        utime.sleep_ms(30)
        estado_actual = sensor_hall.value()
        
        if estado_actual == 1 and estado_anterior == 0:
            cambios_estado += 1
            print(cambios_estado)

        estado_anterior = estado_actual
    print("aca3")
    return cambios_estado

# Función para calcular las RPM
def calcular_rpm(cambios_estado, duracion_ms):
    global velocidad_viento
    rpm = (cambios_estado / 2) / (duracion_ms / 60000)
    velocidad_viento = round(((rpm * 2 * pi * 8.235 * 60) / 100000),1)
    return velocidad_viento

pin_pluviometro = Pin(20, machine.Pin.IN, machine.Pin.PULL_DOWN)

pulso = 0
area_pluviometro = 0.009852
# lluvia_acumulada = 0
lluvias_guardadas = []
ultima_lluvia = hora_actual[5]
primera_lluvia = True

def pluviometro(boton):
      global t1,pulso,lluvia_acumulada, ultima_lluvia,primera_lluvia,velocidad_viento_actual 
      t2 = utime.ticks_ms()
      if (t2 - t1) > 800:
            pulso = pulso + 1
            #cada pulso cae 4mm
            #lluvia acumulada(mm) = agua retenida (l) / área del embudo (m^2)
            lluvia_acumulada = pulso*(0.004/0.009852)
            
            hora_actual = rtc.datetime()
            
            ultima_lluvia = hora_actual[5]
            primera_lluvia = False
            if velocidad_viento_actual > 30:
                clima = "Tormentoso"
            else:
                clima = "Lluvioso"
            print("Pluviometro: ",lluvia_acumulada)
            t1=t2

pin_pluviometro.irq(trigger=Pin.IRQ_RISING, handler=pluviometro)

def revisar_lluvia():
    global ultima_lluvia,primera_lluvia,lluvias_guardadas,lluvia_acumulada,pulso
    hora_actual = rtc.datetime()
    if hora_actual[5]>(ultima_lluvia+1) and primera_lluvia == False:
        lluvias_guardadas.append(f"{hora_actual[2]}/{hora_actual[1]}/{hora_actual[0]}   {round(lluvia_acumulada, 1)}mm")
        print(lluvias_guardadas)
        clima = "Soleado"
        lluvia_acumulada=0
        pulso=0
        primera_lluvia = True

'''
MULTIPLEXOR DE ENTRADAS ANALÓGICAS
'''

# Define los pines del multiplexor y de control
mux_channel_pins = [6, 7]  # Pines A y B del multiplexor
adc_pin = machine.ADC(26)  # Pin ADC de la Raspberry Pi Pico

# Configura los pines del multiplexor
for pin in mux_channel_pins:
    Pin(pin, machine.Pin.OUT)

# Función para leer el valor analógico de un canal específico
def read_analog(channel):
    # Configura los pines del multiplexor para seleccionar el canal deseado
  
    for j in range(2):
        Pin(mux_channel_pins[j], Pin.OUT).value((channel >> j) & 1)
        
    utime.sleep_us(100)  # Espera para estabilizar la señal
    # Lee el valor analógico del pin ADC
    value = adc_pin.read_u16()
  
    return value

'''
MQ135-DSM501A-BMP280
'''
#-------------------------VARIABLES SENSOR DE GAS MQ135-------------------------#

analog_pin = machine.ADC(26) # Va de 0 a 1023

valor_sensor = 0
b = -0.36542
a = 5.59730
RL = 10000
RsData = 0
RsSuma = 0
RsCa = 0
RS = 0
Ro = 0

#-------------------------VARIABLES SENSOR DE PARTICULAS DSM501A---------------------------#

pinSensor = machine.Pin(11, machine.Pin.IN)

tiempoMuestra_ms = 1000
duracionPulso = 0
concentracion = 0
tiempoInicio = 0
pulsosBajos = 0
radio = 0

#-------------------------VARIABLES SENSOR DE PRESION BMP280-------------------------#

bus = I2C(0, sda = Pin(12), scl = Pin(13))

bmp = BMP280(bus)

#-------------------------SENSOR DE GAS MQ135-----------------------------#

sensor_value = read_analog(2) # 12-bits ADC

for i in range(1, 11):
    sensor_value = read_analog(2) # 12-bits ADC
    valor_sensor = valor_sensor + sensor_value
    RsData = 65536 * (RL / sensor_value) - RL
    RsSuma = RsSuma + RsData
    print("Calibrando...")
    utime.sleep(1)
    
RsCa = RsSuma / 10
Ro = RsCa / (a * 414 ** b)

tiempoInicio = utime.ticks_ms()



def MQ135():
    global RL,Ro,a,b,indice_PM1O
    sensor_value = read_analog(2) # 16-bits ADC
    RS = 65536 * (RL / sensor_value) - RL
    ppmCo2 = ((RS/Ro)/a) ** (1/b)
    return ppmCo2

indice_PM1O = "AMBIENTE LIMPIO"

def DSM501A():
    global pulsosBajos, duracionPulso, pinSensor, tiempoInicio, tiempoMuestra_ms, indice_PM1O
    duracionPulso = machine.time_pulse_us(pinSensor, 0) # Esta linea mide la duracion de un pulso en microsegundos en un determinado pin cunado el pulso esta en estado bajo
    pulsosBajos += duracionPulso # Acumulamos la duracion de los pulsos en estado bajo

    if (utime.ticks_ms() - tiempoInicio) > tiempoMuestra_ms: #Entra a calcular la concentracion cuando llegamos al timepo de muestra que establecimos de 1000 ms
        radio = pulsosBajos / (tiempoMuestra_ms * 10.0)
        concentracion = 1.1 * math.pow(radio, 3) - 3.8 * math.pow(radio, 2) + 520 * radio + 0.62
        pulsosBajos = 0
        
        if concentracion < 1000:
            indice_PM1O = "MEDIO LIMPIO"
        elif concentracion < 10000:
            indice_PM1O = "MEDIO APROPIADO"
        elif concentracion < 20000:
            indice_PM1O = "MEDIO ACEPTABLE"
        elif concentracion < 50000:
            indice_PM1O = "MEDIO PESADO"
        else:
            indice_PM1O = "MEDIO PELIGROSO"
        
        return concentracion
    
'''
UV-DB
'''

############ VARIABLES ############

amplitud_micro = 0
lectura_micro = 0
lecturas_micro = 0
valor_db = 0

lec_uv = 0
indice_uv = 0
valor_uv = 0

############ MAPEO ############
def mapeo(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

############ DECIBELIMETRO ############
def decibelimetro():
    global amplitud_micro,lecturas_micro
    
    while lecturas_micro < 21:
        minimo_micro = 65535
        maximo_micro = 0   
        for i in range (1000):
            lectura_micro = read_analog(0)
            minimo_micro = lectura_micro if minimo_micro > lectura_micro else minimo_micro
            maximo_micro = lectura_micro if maximo_micro < lectura_micro else maximo_micro
            
        amplitud_micro = amplitud_micro + (maximo_micro - minimo_micro)/20

        lecturas_micro += 1

    lecturas_micro = 0
    db = mapeo(amplitud_micro, 20000, 50000, 46, 90)
    amplitud_micro = 0 
    return db

############ SENSOR UV ############
def lectura_uv():
    
    lec_uv = read_analog(3)
      
    if lec_uv < 992:
        indice_uv = 0
    elif lec_uv < 4058:
        indice_uv = 1
    elif lec_uv < 6315:
        indice_uv = 2
    elif lec_uv < 8102:
        indice_uv = 3
    elif lec_uv < 9989:
        indice_uv = 4
    elif lec_uv < 12034:
        indice_uv = 5
    elif lec_uv < 13821:
        indice_uv = 6
    elif lec_uv < 15787:
        indice_uv = 7
    elif lec_uv < 17495:
        indice_uv = 8
    elif lec_uv < 19382:
        indice_uv = 9
    elif lec_uv < 21427:
        indice_uv = 10
    else:
        indice_uv = 11
        
    return indice_uv
    #print("Lectura del sensor =", lec_uv, "indice_uv UV =", indice_uv)

def encontrar_letra_mas_comun(lista):
    conteo = {}
    for letra in lista:
        if letra in conteo:
            conteo[letra] += 1
        else:
            conteo[letra] = 1
    
    letra_mas_comun = None
    maximo_conteo = 0
    for letra, cantidad in conteo.items():
        if cantidad > maximo_conteo:
            letra_mas_comun = letra
            maximo_conteo = cantidad
    
    return letra_mas_comun

def calcular_promedios_acumulaciones(archivo_lectura,archivo_escritura,lineas):
    #lineas (30) cargo datos con datosH a datosHS 
    #lineas (24) cargo datos con datosHS a datosD 
    #lineas (31) cargo datos con datosD a datosM 
    
    try:
        # Inicializar listas
        velocidades_viento = []
        lluvias_acumuladas = []
        puntos_cardinales = []
        temperaturas = []
        humedades = []
        listaParticulas = []
        listaGases = []
        presiones = []
        valores_uv = []
        valores_db = []

        # Leer las últimas 30 líneas del archivo
        with open(archivo_lectura, "r") as file:
            
            lines = file.readlines()[-(lineas):]
        
            for line in lines:
                entry = line.strip()
                hora, velocidad_viento_actual, lluvia_acumulada, punto_cardinal,temp,hum,conParticulas,conGases,presion,valor_uv,valor_db = entry.split(';')
                velocidades_viento.append(float(velocidad_viento_actual))
                lluvias_acumuladas.append(float(lluvia_acumulada))
                puntos_cardinales.append(punto_cardinal)
                temperaturas.append(float(temp))
                humedades.append(float(hum))
                listaParticulas.append(float(conParticulas))
                listaGases.append(float(conGases))
                presiones.append(float(presion))
                valores_uv.append(float(valor_uv))
                valores_db.append(float(valor_db))

            # Calcular promedios
            print(temperaturas)
            promedio_velocidades_viento = sum(velocidades_viento) / (len(velocidades_viento)-1)
            suma_lluvias_acumuladas = sum(lluvias_acumuladas)
            punto_comun = encontrar_letra_mas_comun(puntos_cardinales)
            promedio_temperaturas = sum(temperaturas) / (len(temperaturas)-1)
            promedio_humedades = sum(humedades) / (len(humedades)-1)
            promedio_listaParticulas = sum(listaParticulas) / (len(listaParticulas)-1)
            promedio_listaGases = sum(listaGases) / (len(listaGases)-1)
            promedio_presiones = sum(presiones) / (len(presiones)-1)
            promedio_valores_uv = sum(valores_uv) / (len(valores_uv)-1)
            promedio_valores_db = sum(valores_db) / (len(valores_db)-1)
            
            print("promedios calculados")
            
            tiempo_actual = rtc.datetime()
            minuto = tiempo_actual[5]
            minuto_str = zfill_manual(minuto,2)
            hora = tiempo_actual[4]
            hora_str = zfill_manual(hora,2)
            dia = tiempo_actual[2]
            dia_str = zfill_manual(dia,2)
            print("dia: ",dia_str)
            mes = tiempo_actual[1]
            mes_str = zfill_manual(mes,2)
            año = tiempo_actual[0]
            

            with open(archivo_escritura, "a") as file:
                print(f"{hora_str}:{minuto_str} {dia_str}/{mes}/{año};{round(promedio_velocidades_viento,1)};{round(suma_lluvias_acumuladas,1)};{punto_comun};{round(promedio_temperaturas,1)};{round(promedio_humedades,1)};{round(promedio_listaParticulas,1)};{round(promedio_listaGases,1)};{round(promedio_presiones,1)};{round(promedio_valores_uv,1)};{round(promedio_valores_db,1)}\n")
                if lineas == 30:
                    file.write(f"{hora_str}:{minuto_str};{round(promedio_velocidades_viento,1)};{round(suma_lluvias_acumuladas,1)};{punto_comun};{round(promedio_temperaturas,1)};{round(promedio_humedades,1)};{round(promedio_listaParticulas,1)};{round(promedio_listaGases,1)};{round(promedio_presiones,1)};{round(promedio_valores_uv,1)};{round(promedio_valores_db,1)}\n")
                if lineas == 24:
                    file.write(f"{dia_str}/{mes_str}/{año};{round(promedio_velocidades_viento,1)};{round(suma_lluvias_acumuladas,1)};{punto_comun};{round(promedio_temperaturas,1)};{round(promedio_humedades,1)};{round(promedio_listaParticulas,1)};{round(promedio_listaGases,1)};{round(promedio_presiones,1)};{round(promedio_valores_uv,1)};{round(promedio_valores_db,1)}\n")
                if lineas == 31:
                    file.write(f"{mes_str}/{año};{round(promedio_velocidades_viento,1)};{round(suma_lluvias_acumuladas,1)};{punto_comun};{round(promedio_temperaturas,1)};{round(promedio_humedades,1)};{round(promedio_listaParticulas,1)};{round(promedio_listaGases,1)};{round(promedio_presiones,1)};{round(promedio_valores_uv,1)};{round(promedio_valores_db,1)}\n")
            
            print("Promedios y acumulaciones calculados y escritos en datosHS.csv con éxito.")
            gc.collect()
    except Exception as e:
            print(e)

def limpiar_datos(archivo):   #funcion para limpiar DatosH
    try:  #Hacer cuando estamos seguros que haya valores para borrar
        with open(archivo, 'r') as archivo:
            nuevos_valores=[]
            linea = file.read()  
        
            contenido = linea.split("\n")
            
            for i in range(len(contenido)-120,len(contenido),1):
                nuevos_valores.append(contenido[i])
            
        with open(archivo,"w") as file:
            file.write("hora;anemometro;pluviometro;veleta;temperatura;humedad;particulas;gases;presion;uv;db\n")
            for i in range(0,len(nuevos_valores),1):
                file.write(nuevos_valores[i])
                file.write("\n")
                
        print("Archivo leído con éxito")
    except Exception as e:
        print(e)   
    


led_pin = Pin("LED",Pin.OUT)

dos_minutos = 0
#dos_minutos = (30*24*31)-1

def sensado(timer):
    global temp, hum, valor_db, valor_uv, conParticulas, conGases, presion, velocidad_viento_max, velocidad_viento_actual, lluvia_acumulada,dos_minutos,clima
    oled.fill_rect(0, 0, 128, 64, 0)
    oled.blit(Abrir_Icono("icons/hourglass.pbm"), 30, 2)
    oled.show()
    print("Sensando")
    
    if check_internet_connection():
        print("¡Hay conexión a Internet!")
    else:
        print("No hay conexión a Internet.")
        connect_to_wifi(wifi_ssid, wifi_password)
    
    led_pin.value(1)
    
    d.measure()
    temp = d.temperature()
    hum = d.humidity()
    valor_db = round(decibelimetro(), 1)
    valor_uv = lectura_uv()
    conParticulas = round(DSM501A(), 1)
    conGases = round(MQ135(), 1)
    presion = round((bmp.pressure / 100), 1)
    cambios_estado = medir_rpm(duracion_medicion_ms)
    velocidad_viento_actual = calcular_rpm(cambios_estado, duracion_medicion_ms)
    actuador.value(0)

    if conGases > 2000:
        actuador.value(1)
        print("Gases peligrosos")
    
    tiempo_actual = rtc.datetime()
    minuto = tiempo_actual[5]
    hora = tiempo_actual[4]
    
    #Cada 2 minutos se guarda un datos
    try:
        with open("/sd/DatosH.csv","a") as file:
            file.write(f"{hora}:{minuto};{velocidad_viento_actual};{lluvia_acumulada};{punto_cardinal};{temp};{hum};{conParticulas};{conGases};{presion};{valor_uv};{valor_db}\n")
            print("Archivo escrito con éxito")
            dos_minutos += 1
            print("dos_minutos: ",dos_minutos)
    except Exception as e:
        print(e)
        
    #Cada 30 datos se guarda un dato referido a 1 hora
    if dos_minutos % 30 == 0:   
        calcular_promedios_acumulaciones("/sd/DatosH.csv","/sd/DatosHS.csv",30)
    if dos_minutos % (30*24) == 0:   
        calcular_promedios_acumulaciones("/sd/DatosHS.csv","/sd/DatosD.csv",24)
    if dos_minutos % (30*24*31) == 0:   
        calcular_promedios_acumulaciones("/sd/DatosD.csv","/sd/DatosM.csv",31)   
  
    revisar_lluvia()
    
    #lluvioso, tormentoso, despejado(noche), nublado, ventoso, soleado
    
    if velocidad_viento_actual > 30:
        clima = "Ventoso"
    elif hora < 7 and hora >20:
        clima = "Despejado"
    elif hora >= 7 and hora <= 20 and valor_uv < 4:
        clima = "Nublado"
    else:
        clima = "Soleado"
        
    print("clima: ",clima)
    
    gc.collect()
    conParticulasEnvio = 0
    oled.fill_rect(0, 0, 128, 64, 0)
    update_info()
    show_main_menu()
    oled.show()
    
    led_pin.value(0)

tim2 = Timer()
tim2.init(period=120000, callback=sensado)
print("Timer iniciado")


while True:
    
    try:
        gc.collect()
        conn, addr = s.accept()
        print('Got a connection from %s' % str(addr))
        gc.collect()
        request = conn.recv(1024)
        request = str(request)
        
        if request.find("/"):
            pagina = request.find("/")
            if pagina != -1:
                pagina = request[request.find("/") + 1 : request.find(".html")]
                gc.collect()
        # Obtener el nombre de la página a partir de la solicitud del cliente
        else:
            pagina = "index"
        pg, num = get_page_content(pagina)
        if num:
            if pg != "/sd/index.txt":
                if pg != "/sd/veleta.txt":
                    horash,valoresh = leerDatosh(num,True)
                    print("leyó hora")
                    horashs,valoreshs = leerDatoshs(num,True)
                    print("leyó horas")
                    horas7d,valores7d = leerDatos7d(num,True)
                    print("leyó 7d")
                    horas31d,valores31d = leerDatos31d(num,True)
                    print("leyó 31d")
                    horas12m,valores12m = leerDatos12m(num,True)
                    print("leyó 12m")
                else:
                    horash,valoresh = leerDatosh(num,False)
                    horashs,valoreshs = leerDatoshs(num,False)
                    horas7d,valores7d = leerDatos7d(num,False)
                    horas31d,valores31d = leerDatos31d(num,False)
                    horas12m,valores12m = leerDatos12m(num,False)
            
        print(pg, num)
        # Obtener el contenido de la página
        file = open(pg)
        for line in file:
            if num:
                if pg != "/sd/veleta.txt":
                    line = PaginaWeb(line, num, pg)
                else:
                    line = datosVeleta(line,valoresh,valoreshs,valores7d,valores31d,valores12m)
            if not line:
                break
            conn.send(line)
       
        conn.close()
        gc.collect()
    except Exception as e:
        conn.close()
        gc.collect()
        print(e)
    finally:
        conn.close()
        gc.collect()
