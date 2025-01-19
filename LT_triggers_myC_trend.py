import serial
import mysql.connector
import threading
from sklearn.linear_model import LinearRegression
import numpy as np
import signal
import sys
import time
from datetime import datetime

# Serielle Schnittstelle konfigurieren
ser = serial.Serial('COM5', 115200, timeout=3)


# MySQL-Datenbankverbindung zu ditsrv1 (192.168.10.30) initialisieren
db = mysql.connector.connect(
    host="192.168.10.30",
    user="klaus",
    password="dbdit",
    database="lf7_klima"
)

# Objekt fuer DB-Zugriff erzeugen
cursor = db.cursor()

# Bei Eingang eines Interrupts (Thread: "read_fom_port") von der seriellen Verbindung Zeile lesen und Aufteilen
def read_from_port(ser):
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').rstrip()
            now = datetime.now()
            datum = now.date()
            zeit = now.time()
            formatted_date_time = now.strftime("%d. %b %y %H:%M")
            # Variable definieren
            temperatur = None
            feuchte = None
            luftdruck = None
            sensor_id = None

            print(f"\n{formatted_date_time}\n{line}")
            if "info" in line.lower():
                continue  # Für weitere Bearbeitung Zeilen ignorieren, die das Wort "Info" enthalten
            # Daten aufteilen
            parts = line.split(';')
            if len(parts) < 3:
                print("Zeichenkette korrupt. Warte auf neuen Input.")
                continue
            try:
                sensor_id = int(parts[0].split(':')[1].strip())
            except (IndexError, ValueError):
                print("Fehler beim Extrahieren der Sensor-ID. Warte auf neuen Input.")
                continue

            if any(word in line.lower() for word in ["fehler", "error"]):
                # Fehlerhafte Werte in die Datenbank schreiben
                #sensor_id = int(parts[0].split(':')[1].strip())
                cursor.execute(
                    "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, luftdruck, fehler, id_sensor) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (datum, zeit, None, None, None, True, sensor_id))
            else:
                # Weitere Fehlerprüfung:
                if not all(word in line.lower() for word in ["sensor", "temperatur", "feuchte"]):
                    print("Zeichenkette korrupt. Warte auf neuen Input.")
                else:
                    #print("Zeichenkette ok")
                    # Daten aufteilen und in die Datenbank schreiben
                    temperatur = round(float(parts[1].split(':')[1].strip()), 2)
                    feuchte = round(float(parts[2].split(':')[1].strip()), 2)
                    luftdruck = round(float(parts[3].split(':')[1].strip()), 2) if len(parts) > 3 else None
                if luftdruck is not None:
                    cursor.execute(
                        "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, luftdruck, id_sensor) VALUES (%s, %s, %s, %s, %s, %s)",
                        (datum, zeit, temperatur, feuchte, luftdruck, sensor_id))
                else:
                    cursor.execute(
                        "INSERT INTO messwerte (datum, zeit, temperatur, feuchte, id_sensor) VALUES (%s, %s, %s, %s, %s)",
                        (datum, zeit, temperatur, feuchte, sensor_id))

            db.commit()
            #print(f"calculate_trend wird aufgerufen für sensor_id: {sensor_id}")  # Debugging-Ausgabe
            # Trendberechnung nach dem Speichern der Sensordaten
            calculate_trend(sensor_id)
            #except mysql.connector.Error as err:
                #print(f"Fehler bei der Datenbankoperation: {err}")
            #except Exception as e:
                #print(f"Fehler beim Lesen der seriellen Schnittstelle: {e}")

def calculate_trend(sensor_id):
    trends = {}
    threshold = 0.008  # Niedrigere Schwelle fuer "gleichbleibend"

    # Bestimmung der zu messenden Metriken basierend auf dem Sensor
    if sensor_id == 4:
        metrics = ["temperatur", "feuchte", "luftdruck"]
    else:
        metrics = ["temperatur", "feuchte"]

    # Berechnung des Trends fuer die angegebenen Metriken
    for metric in metrics:
        values = fetch_latest_values(sensor_id, metric)
        print(f"Fetched values for sensor {sensor_id} and metric {metric}: {values}")  # Debugging-Ausgabe
        # Ueberpruefung, ob korrekte bzw. genuegend Werte vorhanden sind.
        if not values or any(value is None for value in values):
            trends[f"Sensor {sensor_id} - {metric}"] = "kein Trend"
            print(f"Keine geeigneten Daten fuer die Trendberechnung fuer Sensor {sensor_id} und {metric}.")
            store_trend(sensor_id, metric, "kein Trend")
            continue
        if len(values) < 9:
            trends[f"Sensor {sensor_id} - {metric}"] = "kein Trend"
            print(f"Nicht genuegend Daten fuer die Trendberechnung fuer Sensor {sensor_id} und {metric}.")
            store_trend(sensor_id, metric, "kein Trend")
            continue

        from sklearn.preprocessing import StandardScaler

        x = np.array(range(1, len(values) + 1)).reshape(-1, 1)
        y = np.array(values).reshape(-1, 1)

        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x)
        y_scaled = scaler.fit_transform(y)

        model = LinearRegression().fit(x_scaled, y_scaled)
        slope = model.coef_[0]
        print(f"Slope for sensor {sensor_id} and metric {metric}: {slope}")  # Debugging-Ausgabe
        if abs(slope) < threshold:
            trends[f"Sensor {sensor_id} - {metric}"] = "gleichbleibend"
        elif slope < 0:
            trends[f"Sensor {sensor_id} - {metric}"] = "fallend"
        else:
            trends[f"Sensor {sensor_id} - {metric}"] = "steigend"

        store_trend(sensor_id, metric, trends[f"Sensor {sensor_id} - {metric}"])

    # Ausgabe des Trends
    print(f"Trend der letzten 9 Werte fuer Sensor {sensor_id}:")
    for metric, trend in trends.items():
        print(f"{metric}: {trend}")

    return trends

# Aufforderung einen Befehl zum Trigern des Arduino ueber serielle Schnittstelle zu senden (Thread: send_command)
def send_command(ser):
    while True:
        time.sleep(5) # Wartezeit in Sekunden
        ser.write(b'GET_ID5\n')
        #time.sleep(5)  # Wartezeit in Sekunden
        #ser.write(b'GET_ID2\n')
        #time.sleep(5)  # Wartezeit in Sekunden
        #ser.write(b'GET_ID3\n')
        #time.sleep(5)  # Wartezeit in Sekunden
        #ser.write(b'GET_ID4\n')
        time.sleep(715)  # Wartezeit in Sekunden

def fetch_latest_values(sensor_id, metric, limit=9):
    # Abfrage der letzten Werte für den angegebenen Sensor und das angegebene Messwert
    query = f"""
    SELECT {metric}
    FROM messwerte
    WHERE id_sensor = {sensor_id} AND fehler = false AND TIMESTAMP(datum, zeit) >= NOW() - INTERVAL 180 MINUTE
    ORDER BY datum DESC, zeit DESC
    LIMIT {limit}; """
    cursor.execute(query)
    results = cursor.fetchall()

    # Umkehren der Reihenfolge der Ergebnisse, um die ältesten Werte zuerst zu haben
    results.reverse()

    #print(f"Fetched values for sensor {sensor_id} and metric {metric}: {results}")
    return [row[0] for row in results]

def store_trend(sensor_id, metric, trend):
    # Löschen alter Trends für den angegebenen Sensor und das angegebene Messwert
    delete_query = f"""
    DELETE FROM Trends
    WHERE sensor_id = {sensor_id} AND metric = '{metric}';
    """
    cursor.execute(delete_query)

    # Einfügen des neuen Trends in die Tabelle Trends
    insert_query = f"""
    INSERT INTO Trends (sensor_id, metric, trend)
    VALUES ({sensor_id}, '{metric}', '{trend}');
    """
    cursor.execute(insert_query)
    db.commit()

def delete_old_trends():
    # Löschen alter Trends, die älter als 1 Stunde sind
    query = """
    DELETE FROM Trends
    WHERE timestamp < NOW() - INTERVAL 2 HOUR;
    """
    cursor.execute(query)
    db.commit()

def calculate_trend(sensor_id):
    trends = {}
    threshold = 0.008  # Niedrigere Schwelle fuer "gleichbleibend"

    # Bestimmung der zu messenden Metriken basierend auf dem Sensor
    if sensor_id == 4:
        metrics = ["temperatur", "feuchte", "luftdruck"]
    else:
        metrics = ["temperatur", "feuchte"]

    # Berechnung des Trends fuer die angegebenen Metriken
    for metric in metrics:
        values = fetch_latest_values(sensor_id, metric)
        # Ueberpruefung, ob korrekte bzw. genuegend Werte vorhanden sind.
        if not values or any(value is None for value in values):
            trends[f"Sensor {sensor_id} - {metric}"] = "kein Trend"
            print(f"Keine geeigneten Daten fuer die Trendberechnung fuer Sensor {sensor_id} und {metric}.")
            store_trend(sensor_id, metric, "kein Trend")
            continue
        if len(values) < 9:
            trends[f"Sensor {sensor_id} - {metric}"] = "kein Trend"
            print(f"Nicht genuegend Daten fuer die Trendberechnung fuer Sensor {sensor_id} und {metric}.")
            store_trend(sensor_id, metric, "kein Trend")
            
            continue

        from sklearn.preprocessing import StandardScaler

        x = np.array(range(1, len(values) + 1)).reshape(-1, 1)
        y = np.array(values).reshape(-1, 1)

        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x)
        y_scaled = scaler.fit_transform(y)

        model = LinearRegression().fit(x_scaled, y_scaled)
        slope = model.coef_[0]
        if abs(slope) < threshold:
            trends[f"Sensor {sensor_id} - {metric}"] = "gleichbleibend"
        elif slope < 0:
            trends[f"Sensor {sensor_id} - {metric}"] = "fallend"
        else:
            trends[f"Sensor {sensor_id} - {metric}"] = "steigend"

        store_trend(sensor_id, metric, trends[f"Sensor {sensor_id} - {metric}"])

    # Ausgabe des Trends
    #print(f"Trend der letzten 9 Werte fuer Sensor {sensor_id}:")
    for metric, trend in trends.items():
        print(f"{metric}: {trend}")

    return trends

# Thread fuer das Lesen der seriellen Schnittstelle (Interrupt) starten
#threading.Thread(target=read_from_port, args=(ser,)).start()
thread_read = threading.Thread(target=read_from_port, args=(ser,))
thread_read.daemon = True
thread_read.start()

# Thread fuer das Senden von Befehlen starten
#threading.Thread(target=send_command, args=(ser,)).start()
thread_command = threading.Thread(target=send_command, args=(ser,))
thread_command.daemon = True
thread_command.start()

# Signal-Handler fuer das Beenden des Programms definieren
def signal_handler(sig, frame):
    print("Programm beendet")
    ser.close()
    db.close()
    sys.exit(0)
    
signal.signal(signal.SIGINT, signal_handler)

# Hauptprogramm laeuft weiter
try:
    while True:
        time.sleep(1) # Kurze Pause, um CPU-Auslastung zu reduzieren
except KeyboardInterrupt:
    pass
finally:
    ser.close()
    db.close()
