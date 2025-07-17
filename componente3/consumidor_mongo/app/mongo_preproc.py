# Código del consumidor_mongo para preprocesar y almacenar datos de aeronaves
#   Este script define las funciones para sectorizar, calcular nivel de vuelo y almacenar en MongoDB
#   junto al archivo consumer_mongo.py que contiene el código del consumidor de Kafka que llama a estas funciones

# Importación de librerías
from datetime import datetime
import os
import logging

# Librerías del archivo requeriments.txt y config.py
import numpy as np
from config.config import centro_sectores
from pymongo import ASCENDING, GEOSPHERE

# Configuración de variables de entorno para Kafka y MongoDB (.env)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB = os.getenv("MONGO_DB", "adsb_database")
COLECCION_INTERVALO = int(os.getenv('MONGO_COLECCION_INTERVALO', 15))
ID_SERVICE = os.getenv("ID_SERVICE", "consumidor_mongo")


# Función para obtener el nombre de la colección donde se debe insertar la aeronave, en función de su atributo 'time'
#   las colecciones almacenan datos de aeronaves cada tiempo correspondiente a un intervalo definido COLECCION_INTERVALO
def nombre_coleccion_bloque_tiempo(timestamp):
    tiempo_edit = datetime.utcfromtimestamp(timestamp)                              # Tiempo en formato UTC
    bloque_tiempo = tiempo_edit.replace(                                            # Formateo a YYYYMMDDHHMM
        minute=tiempo_edit.minute // COLECCION_INTERVALO * COLECCION_INTERVALO,
        second=0,
        microsecond=0
    )
    return bloque_tiempo.strftime("%Y%m%d%H%M")

# ----------------------------------------------# ----------------------------------------------# ----------------------------------------------

# Función para tomar un valor de altitud según los datos disponibles, si solo hay uno toma el disponible
# si están los dos se le da prioridad a la información de baroaltitude.
def definir_altitud(mensaje):
    for k in ['baroaltitude', 'geoaltitude']:
        valor = mensaje.get(k)
        if isinstance(valor, (int, float)):
            return valor
    return None
# ----------------------------------------------# ----------------------------------------------# ----------------------------------------------

# Cálculo del nivel de vuelo en cientos de pies
def definir_FL(altitud):
    return int(round(altitud * 3.28084 / 100))
# ----------------------------------------------# ----------------------------------------------# ----------------------------------------------

# Cálculo de distancia al centro de sector más cercano de los definidos, devuelve el nombre del sector correspondiente para asociar a él la aeronave
def sectorizar_aeronave(mensaje):
    try:
        posicion = np.array([float(mensaje.get('lat')), float(mensaje.get('lon'))])     # almacena la ubicación en un array
    except Exception:
        return "desconocido"

    distancia_min = float("inf")                                                        # Inicializa una variable
    sector_asignado = "desconocido"                                                     # Inicializa un sector en caso de no encontrar solución
    for sector in centro_sectores:                                                      # Itera sobre la lista de sectores definidos
        centro = np.array([sector["lat"], sector["lon"]])                               # ubicación del centro del sector
        distancia = np.linalg.norm(posicion - centro)                                   # Cálculo de distancia de separación
        if distancia < distancia_min:                                                   # Comparación con la distancia anterior
            distancia_min = distancia
            sector_asignado = sector["nombre"]                                          # Si la distancia es menor, le asigna el sector
    return sector_asignado
# ----------------------------------------------# ----------------------------------------------# ----------------------------------------------

# Función para insertar aeronaves de una en una en MongoDB, según su atributo 'time' en una colección
def insertar_aeronave(db, mensaje):
    bloque_tiempo = nombre_coleccion_bloque_tiempo(mensaje['time'])             # Se obtiene el nombre de la colección correspondiente al atributo 'time'
    coleccion = db[bloque_tiempo]                                               # Selecciona la colección, si no existe este comando la crea.

    inicializa_indices_coleccion(coleccion)                                     # Crea índices de búsqueda, si ya existen se ignora la creación

    if not coleccion.find_one({"icao24": mensaje['icao24'], "time": mensaje['time']}):
        coleccion.insert_one(mensaje)                                           # Inserta la aeronave si este registro de aeronave-tiempo no está en la colección  
# ----------------------------------------------# ----------------------------------------------# ----------------------------------------------

# Función para insertar conjuntos de aeronaves recibidos en un mensaje, donde todas las aeronaves presentan el mismo valor de 
#   atributo 'time'
def insertar_aeronaves(db, mensaje, mensaje_time):
    
    if mensaje_time is None or not mensaje:                                     # Chequeo de mensaje
        return

    bloque_tiempo = nombre_coleccion_bloque_tiempo(mensaje_time)                # Se obtiene el nombre de la colección correspondiente al atributo 'time'
    coleccion = db[bloque_tiempo]                                               # Selecciona la colección, si no existe este comando la crea.

    inicializa_indices_coleccion(coleccion)                                     # Crea índices de búsqueda, si ya existen se ignora la creación

    nuevos = []                                                                 # Inicio de grupo de aeronaves
    for aeronave in mensaje:                                                    # Itera en las aeronaves del mensaje recibido
        
        # Debido a que el consumidor Mongo va a recibir el mensaje más antiguo disponible en Kafka para evitar perder información en caso de desconexión
        # Es necesario comprobar si el registro ya está incluido y evitar cálculos lo antes posible para pasar al siguiente
 
        if not coleccion.find_one({"icao24": aeronave['icao24'], "time": aeronave['time']}):    # Si este registro de aeronave-tiempo no está en la colección  
            altitud = definir_altitud(aeronave)                                     # Define la altitud según los datos disponibles
            if altitud is None or altitud < 0:                                      # Al ser un valor clave, si no es posible se considera registro corrupto
                continue
            aeronave['altitude'] = altitud                                          # Se añade altitud al registro  
            aeronave['FL'] = definir_FL(altitud)                                    # Se calcula y añade Nivel de Vuelo (FL) al registro
            aeronave['sector'] = sectorizar_aeronave(aeronave)                      # Se calcula y añade el sector correspondiente por ubicación
            nuevos.append(aeronave)                                                 # Añade el registro al grupo a insertar en la base de datos

    if nuevos:                                                                      # Si existen aeronaves a añadir
        try:
            coleccion.insert_many(nuevos)                                               # Inserción masiva en una orden
            logging.getLogger(__name__).info(f"{ID_SERVICE}:{len(nuevos)} aeronaves insertadas en la colección {coleccion.name}.")
        except Exception as e:
            logging.getLogger(__name__).info(f"{ID_SERVICE}:Error al insertar {len(nuevos)} aeronaves en la colección {coleccion.name}.")

# ----------------------------------------------# ----------------------------------------------# ----------------------------------------------
# Función para crear los índices en cada nueva colección que permite realizar operaciones de análisis de espacio aéreo retrospectivo
#   Si los índices ya existen no se aplica.
def inicializa_indices_coleccion(colecccion_mongo):
    try:
        colecccion_mongo.create_index([("location", GEOSPHERE)])
        colecccion_mongo.create_index([("icao24", ASCENDING), ("time", ASCENDING)])
        colecccion_mongo.create_index([("time", ASCENDING), ("sector", ASCENDING)])
        colecccion_mongo.create_index([("FL", ASCENDING)])
        colecccion_mongo.create_index([("time", ASCENDING)])
    except Exception as e:
        logging.getLogger(__name__).warning(f"{ID_SERVICE}: Error al crear índices en la colección {colecccion_mongo}.")