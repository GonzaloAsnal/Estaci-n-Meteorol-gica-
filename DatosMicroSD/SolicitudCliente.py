import requests

IP_RASPBERRY = "192.168.1.138"  # Cambiar por IP real

# Obtener solo temperatura
response = requests.get(f"http://{IP_RASPBERRY}/temperatura")
print("Temperatura:", response.text)

# Obtener todos los datos en JSON
response = requests.get(f"http://{IP_RASPBERRY}/datos")
datos = response.json()
print("Datos completos:", datos)

# Obtener datos de sensor específico
response = requests.get(f"http://{IP_RASPBERRY}/sensor/temperatura")
print("Temperatura sensor:", response.text)