# pip install pyserial mysql-connector-python keyboard
import serial
import mysql.connector
import threading
from datetime import datetime
import keyboard

# Serielle Schnittstelle für LT konfigurieren
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
            from datetime import datetime
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
                    "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, fehler) VALUES (%s, %s, %s, %s, %s)",
                    (datum, zeit, 999.9, 999.9, True))
                messwert_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO messwerte_raeume (id_mw, id_raum) VALUES (%s, %s)",
                    (messwert_id, raum_id))
            else:
                # Daten aufteilen und in die Datenbank schreiben
                temperatur = round(float(parts[1].split(':')[1].strip()), 2)
                feuchte = round(float(parts[2].split(':')[1].strip()), 2)
                cursor.execute(
                    "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, fehler) VALUES (%s, %s, %s, %s, %s)",
                    (datum, zeit, temperatur, feuchte, False))
                messwert_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO messwerte_raeume (id_mw, id_raum) VALUES (%s, %s)",
                    (messwert_id, raum_id))

            db.commit()


# Thread für das Lesen der seriellen Schnittstelle starten
thread = threading.Thread(target=read_from_port, args=(ser,))
thread.daemon = True
thread.start()

# Hauptprogramm laeuft weiter
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
