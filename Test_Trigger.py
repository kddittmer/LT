import serial
import time
# Serielle Verbindung zum Arduino herstellen
ser = serial.Serial('COM3', 115200)  # Passe den COM-Port an

def get_sensor_data(command):
    ser.write((command + '\n').encode())
    time.sleep(1)  # Warte auf die Antwort des Arduino
    while ser.in_waiting > 0:
        line = ser.readline().decode('utf-8').strip()
        print(line)

try:
    while True:
        user_input = input("Gib den Befehl ein (GET_ID1, GET_ID2, GET_ID3, GET_ID4, GET_ALL): ")
        #if user_input in ["GET_R111", "GET_R221", "GET_R222","GET_R280","GET_ALL"]:
        get_sensor_data(user_input)
        #else:
        #    print("Ungültiger Befehl. Bitte versuche es erneut.")
except KeyboardInterrupt:
    print("Programm beendet.")
finally:
    ser.close()
