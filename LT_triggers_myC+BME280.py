import serial
import mysql.connector
import threading
import keyboard
import time
from datetime import datetime

# Serielle Schnittstelle für PC konfigurieren
ser = serial.Serial('COM9', 115200, timeout=1)

# MySQL-Datenbankverbindung zu dit-srv1 (192.168.10.30) herstellen
db = mysql.connector.connect(
    host="192.168.10.30",
    user="klaus",
    password="dbdit",
    database="sensor_data"
)

cursor = db.cursor()


def read_from_port(ser):
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').rstrip()
            now = datetime.now()
            datum = now.date()
            zeit = now.time()
            formatted_date_time = now.strftime("%d. %b %y %H:%M")
            print(formatted_date_time, end=' ')
            print(line)
            # Daten aufteilen
            parts = line.split(';')
            raum_id = int(parts[0].split(':')[1].strip())

            if any(word in line.lower() for word in ["fehler", "error"]):
                # Fehlerhafte Werte in die Datenbank schreiben
                cursor.execute(
                    "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, luftdruck, fehler) VALUES (%s, %s, %s, %s, %s, %s)",
                    (datum, zeit, 9999.9, 9999.9, 9999.9, True))
                messwert_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO messwerte_raeume (id_mw, id_raum) VALUES (%s, %s)",
                    (messwert_id, raum_id))
            else:
                # Daten aufteilen und in die Datenbank schreiben
                temperatur = round(float(parts[1].split(':')[1].strip()), 2)
                feuchte = round(float(parts[2].split(':')[1].strip()), 2)

                if raum_id == 280:
                    luftdruck = round(float(parts[3].split(':')[1].strip()), 2)  # Luftdruck hinzufügen
                    cursor.execute(
                        "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, luftdruck, fehler) VALUES (%s, %s, %s, %s, %s, %s)",
                        (datum, zeit, temperatur, feuchte, luftdruck, False))
                else:
                    cursor.execute(
                        "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, fehler) VALUES (%s, %s, %s, %s, %s)",
                        (datum, zeit, temperatur, feuchte, False))

                messwert_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO messwerte_raeume (id_mw, id_raum) VALUES (%s, %s)",
                    (messwert_id, raum_id))

            db.commit()


def trigger_sensors():
    while True:
        # GET_DHT11
        # ser.write("GET_DHT11\n".encode())
        # time.sleep(20)  # X Sekunden warten

        # GET_DHT22
        # ser.write("GET_DHT22\n".encode())
        # time.sleep(20)  # X Sekunden warten

        # GET_ALL
        ser.write("GET_ALL\n".encode())
        time.sleep(600)  # X Sekunden warten


# Thread für das Lesen der seriellen Schnittstelle starten
thread = threading.Thread(target=read_from_port, args=(ser,))
thread.daemon = True
thread.start()

# Thread für das Triggern der Sensoren starten
trigger_thread = threading.Thread(target=trigger_sensors)
trigger_thread.daemon = True
trigger_thread.start()

# Hauptprogramm läuft weiter
try:
    while True:
        if keyboard.is_pressed('q'):
            print("Programm durch Taste q beendet")
            break
except KeyboardInterrupt:
    pass
finally:
    ser.close()
    db.close()