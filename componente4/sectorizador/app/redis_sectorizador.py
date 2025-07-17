# Código del sectorizador que contiene la clase RedisHandler para manejar las operaciones en Redis
#   Junto al archivo sectorizador.py  para construir las estructuras de datos en Redis que representen 
#   las aeronaves activas en diferentes zonas geográficas y el archivo config.py que contiene la configuración de las zonas geográficas y los aeropuertos.

# En esta fase:
#   No se incluyen sectores reales de tráfico aéreo
#   Se crean sectores ficticios para representar zonas geográficas de cada continente
#   Se crean sectores ficticios de aeropuertos en la zona sur de España

# Importaciones necesarias
import redis
import logging
import os
import numpy    as np
from   datetime import datetime

# Librerías del archivo config.py
from   config.config import centro_sectores

# Configuración de variables de entorno para Redis (.env)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")                                               # Dirección del servidor de Redis (gracias a la red Docker se puede usar el nombre del servicio)
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))                                             # Puerto del servidor de Redis definido en el archivo docker-compose
REDIS_TTL = int(os.getenv("REDIS_TTL", 60))                                                 # Tiempo de vida (TTL) de las claves en Redis
ID_SERVICE = os.getenv("ID_SERVICE", "sectorizador")                                        # Identificador del servicio para trazas


# Clase RedisSectorizador para manejar la conexión y operaciones con Redis, se utiliza para gestionar el estado de los sectores
class RedisSectorizador:
    """
    Cliente Redis para sectorización de aeronaves.
    """
    # Inicializa el cliente Redis con los parámetros que reciba la función o con las variables de entorno
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT):                       
        self.r = redis.Redis(host=host, port=port, decode_responses=True)                       # Conecta al servidor Redis especificado
        self.r.client_setname(ID_SERVICE)                                                       # Identificador del servicio en la conexión
        logging.getLogger(__name__).info(f"{ID_SERVICE}: Conectado a Redis en {host}:{port}")   # Logs


    def distancia_a_sector(self,lat,lon):                                                       # Funcion para calcular la distancia de la aeronave a un sector
        pos=np.array([lat,lon])                                                                 # Estable lat y lon de la aeronave
        distancias=[np.linalg.norm(pos-np.array([s["lat"],s["lon"]])) for s in centro_sectores] # Calcula la distancia hasta el centro de cada sector
        id=int(np.argmin(distancias))                                                           # Escoge la distancia mínima y el nombre del sector correspondiente
        return centro_sectores[id]["nombre"]


    # Función para agrupar las aeronaves en sectores según los datos de latitud, longitud y radio del sector.
    def sectorizar(self):
        """
        Sectoriza las aeronaves activas entorno a un área geográfica en Redis, por cercanía al centro del sector.
        Para evitar inconsistencias en las consultas mientras se recalculan los sectores, se crean estructuras 
        temporales para después renombrarlos por los operativos.
        """
        try:
            clave_sectores_tmp = [f"sector_tmp:{s['nombre']}" for s in centro_sectores]         # Establece el nombre de las claves temporales para el cálculo de sectores
            for clave in clave_sectores_tmp:
                self.r.delete(clave)                                                            # Elimina las claves temporales si ya existían de una sectorización previa
                        
            aeronaves_activas=self.r.zrange("aeronaves:activas",0,-1)                           # Lista los identificativos de todas las aeronaves activas
            aeronaves_geo=self.r.geopos("aeronaves:geo",*aeronaves_activas)                     # Lista la ubicación disponible de las aeronaves activas almacenadas

            for aeronaves, geo in zip(aeronaves_activas,aeronaves_geo):                         # Itera sobre los identificativos y ubicaciones
                if geo is None:                                                                 # Si no se dispone de valores pasa a la siguiente
                    continue
                lon,lat=map(float,geo)                                                          # Guarda lat y lon en una variable
                sector_id=self.distancia_a_sector(lat,lon)                                      # Llama a la función de cálculo de distancias, para establecer el sector cercano
                self.r.sadd(f"sector_tmp:{sector_id}",aeronaves)                                # Añade la aeronave a la clave temporal correspondiente del sector cercano
            
            for sector in centro_sectores:                                                      # Itera sobre los sectores una vez se ha terminado de sectorizar sobre claves temporales
                nombre=sector["nombre"]
                self.r.rename(f"sector_tmp:{nombre}",f"sector:{nombre}")                        # Renombra la clave temporal a definitiva, sobreescribiendo la anterior
            
            self.r.set("sector:time", datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))          # Establece una clave para la hora de sectorización. Servirá para presentación del cliente_atm
            logging.getLogger(__name__).info(f"{len(aeronaves_activas)} aeronaves sectorizadas correctamente.")  

        except Exception as e:
            logging.getLogger(__name__).error(f"Error al sectorizar: {e}")