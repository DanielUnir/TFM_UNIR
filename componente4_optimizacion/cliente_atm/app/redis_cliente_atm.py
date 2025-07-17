# Código del cliente ATM que contiene la clase RedisHandler para manejar las operaciones en Redis
#   Junto al archivo cliente_atm.py para la API Flask que proporciona la visualización de datos del espacio aéreo 
#   y el archivo config.py que contiene la configuración de las zonas geográficas.

# Importaciones necesarias
import  redis
import  logging
import  os
from    config  import centro_sectores

# Configuración de variables de entorno para Redis (.env)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")                               # Dirección del servidor de Redis (gracias a la red Docker se puede usar el nombre del servicio)
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))                             # Puerto del servidor de Redis definido en el archivo docker-compose
REDIS_TTL = int(os.getenv("REDIS_TTL", 60))                                 # Tiempo de vida (TTL) de las claves en Redis
ID_SERVICE = os.getenv("ID_SERVICE", "cliente_atm")                         # Identificador del servicio para trazas


# Clase RedisClienteATM para manejar las operaciones de Redis
class RedisClienteATM:
    """
    Clase para manejar las operaciones de Redis relacionadas con el tráfico aéreo.
    Proporciona métodos para obtener el conteo de aeronaves en un sector,
    obtener la lista de aeronaves en un sector y obtener información de una aeronave específica.
    """

    # Inicializa el cliente Redis con los parámetros que reciba la función o con las variables de entorno
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT):                       
        self.r = redis.Redis(host=host, port=port, decode_responses=True)                       # Conecta al servidor Redis especificado
        self.r.client_setname(ID_SERVICE)                                                       # Identificador del servicio en la conexión
        logging.getLogger(__name__).info(f"{ID_SERVICE}: Conectado a Redis en {host}:{port}")   # Logs

    # Función para contar aeronaves en un sector específico
    def conteo_aeronaves_sector(self):
        """
        Obtiene el conteo de aeronaves en un sector específico.
        """
        try:
            resultado={}                                                    # Inicializa una lista de resultados
            sectores = [s['nombre'] for s in centro_sectores]               # Obtiene los nombres de los sectores definidos en config.py
            time_utc = self.r.get("sector:time") or "No disponible"         # Obtiene la hora efectiva de sectorización
            for sector in sectores:                                         # Itera sobre los sectores
                key = f"sector:{sector}"                                    # Define la clave de Redis para el sector
                count = self.r.scard(key)                                   # Obtiene el conteo de aeronaves en el sector en Redis
                resultado[sector]=count                                     # Actualiza la lista de resultados
                logging.getLogger(__name__).info(f"Aeronaves en el sector {sector}: {count}")
            return resultado, time_utc
        except Exception as e:
            logging.getLogger(__name__).error(f"Error al obtener el conteo de aeronaves en el sector {sector}: {e}")
            return None
        
    # Función para obtener la lista de aeronaves en un sector específico
    def obtener_aeronaves_sector(self,sector):
        """
        Obtiene la lista de aeronaves en un sector específico.
        """
        try:
            aeronaves = self.r.smembers(f"sector:{sector}")                 # Obtiene el listado de aeronaves en el sector indicado en Redis
            logging.getLogger(__name__).info(f"Aeronaves en el sector {sector}: {aeronaves}")
            return list(aeronaves)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error al obtener las aeronaves en el sector {sector}: {e}")
            return None
        
    # Función para obtener la información de una aeronave específica
    def info_aeronave(self,icao24):
        """
        Obtiene la información de una aeronave específica.
        """
        try:
            info = self.r.hgetall(f"aeronave:{icao24}")                     # Obtiene la información de la aeronave en Redis
            return info
        except Exception as e:
            logging.getLogger(__name__).error(f"Error al obtener la información de la aeronave {icao24}: {e}")
            return None