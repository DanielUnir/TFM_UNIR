# Código auxiliar para `consumidor_redis.py`
#   Define las funciones para realizar las operaciones en Redis de almacenamiento de aeronaves


# Librerías necesarias
import logging
import os
import redis
from   datetime    import datetime, timezone


# Configuración de variables de entorno para Redis (.env)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")                                   # Dirección del servidor de Redis (gracias a la red Docker se puede usar el nombre del servicio)
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))                                 # Puerto del servidor de Redis definido en el archivo docker-compose
REDIS_TTL = int(os.getenv("REDIS_TTL", 60))                                     # Tiempo de vida (TTL) de las claves en Redis
ID_SERVICE = os.getenv("ID_SERVICE", "consumidor_redis")                        # Identificador del servicio para trazas


# Establece la clase para definir las operaciones en Redis que utilizará `consumidor_redis.py`
class RedisHandler:
    """
    Cliente para las operaciones que almacenan los datos de aeronaves en Redis.
    """

#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # Inicializa el cliente Redis con los parámetros que reciba la función o con las variables de entorno
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT):                       
        self.r = redis.Redis(host=host, port=port, decode_responses=True)                       # Conecta al servidor Redis especificado
        self.r.client_setname(ID_SERVICE)                                                       # Identificador del servicio en la conexión
        logging.getLogger(__name__).info(f"{ID_SERVICE}: Conectado a Redis en {host}:{port}")   # Logs

#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Define la función para almacenar el mensaje completo de aeronaves en las claves Redis correspondientes
    def actualizar_aeronaves(self, aeronaves_correctas, ttl=REDIS_TTL):                                  
        """ Función para almacenar el mensaje completo de aeronaves en las claves Redis correspondientes.
                Utiliza operaciones en pipeline para mejorar eficiencia de proceso.
                Una clave única para cada aeronave, 
                una clave común para aeronaves activas, servirá para el cliente de visualización
                una clave común para geoposicionamiento, servirá para el servicio de sectorización.
        """

        with self.r.pipeline() as pipe:                                                         # Preparación del pipeline, serie de operaciones en Redis
            for aeronave in aeronaves_correctas:                                                # Itera en cada aeronave del mensaje
                try:
                    icao24 = aeronave.get("icao24")                                             # Obtiene el identificador
                    t_mensaje = aeronave.get("time")                                            # Obtiene 'time'
                    key = f"aeronave:{icao24}"                                                  # Define la clave Redis para almacenar los datos de la aeronave
                    
                    if self.mensaje_obsoleto(key,t_mensaje):                                    # Verifica si ya existen datos más reciente con la función mensaje_obsoleto
                        continue

                    booleanos = ["onground", "alert", "spi"]                                    # Lista de campos booleanos del mensaje de la aeronave
                    aeronave_edit  = {k: (int(v) if k in booleanos else v)                      # Convierte booleanos a enteros (0 o 1) y elimina los campos None
                        for k, v in aeronave.items() if v is not None}                    

                    pipe.geoadd("aeronaves:geo", (aeronave_edit.get("lon"), 
                                                  aeronave_edit.get("lat"), icao24))            # Actualiza la posición geoespacial
                    pipe.hset(key, mapping=aeronave_edit)                                       # Actualiza el estado de la aeronave en Redis tipo hash
                    pipe.zadd("aeronaves:activas", {icao24: t_mensaje})                         # Actualiza el conjunto ordenado de aeronaves activas tipo sorted set
                    pipe.expire(key, ttl)                                                       # Establece expiración (TTL) a la clave en Redis
                except Exception as e:                                                          # Sale de la iteración en caso de error
                    continue
            pipe.execute()                                                                      # Ejecuta el pipeline en Redis                               
        logging.getLogger(__name__).info(
            f"{ID_SERVICE}: {len(aeronaves_correctas)} insertadas en Redis.")                   # Log  

#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Define la función para limpiar las claves Redis
    def aeronaves_inactivas(self, ttl=REDIS_TTL):
        """ Define la función para limpiar las claves Redis aeronaves:activas y aeronaves:geo para evitar crecimiento descontrolado
            Utiliza el tiempo marcado por la expiración de las claves de aeronaves.
            """
        
        try:
            maximo= int(datetime.now(timezone.utc).timestamp()- float(ttl))                     # Obtiene el tiempo UTC a partir del cual se deben eliminar aeronaves
            inactivas=self.r.zrangebyscore("aeronaves:activas",0,maximo)                        # Comprueba si existen claves cuya puntuación, marcada por el atributo
                                                                                                #   'time' de la aeronave en UTC es inferior al máximo permitido
            
            if inactivas:                                                                       # Elimina aquellas claves encontradas de los sorted set 
                self.r.zrem("aeronaves:activas",*inactivas)                                     # aeronaves:activas
                self.r.zrem("aeronaves:geo",*inactivas)                                         # aeronaves:geo
        except Exception as e:                                                                  # Sale de la iteración en caso de error
            logging.getLogger(__name__).error(                                                  # Log
                f"{ID_SERVICE}: Error al eliminar aeronaves inactivas: {e}")                    

#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    # Define la función para verificar si el mensaje es obsoleto
    def mensaje_obsoleto(self, icao24, t_mensaje):                                 
        """
        Verifica si el mensaje, ya validado en atributos esenciales, es obsoleto.
        Compara el valor de tiempo del mensaje con el del último mensaje almacenado en Redis.
        Si el mensaje es más antiguo que el almacenado, se considera obsoleto y se descarta.
        """


        try:    
            t_almacenado = self.r.zscore("aeronaves:activas", icao24)       # Obtener en Redis el tiempo más reciente de la aeronave si está activa
            if t_almacenado is None:
                return False                                                # La aeronave no está activa, no es obsoleto
            elif float(t_mensaje) <= float(t_almacenado):                   # La aeronave está activa. Compara el tiempo actual con el almacenado
                return True                                                 # Si el mensaje es más antiguo o igual al almacenado, se considera obsoleto
            else:
                return False                                                # Si el mensaje es más reciente, no es obsoleto
        except Exception as e:                                              # Sale de la iteración en caso de error
            return True

#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------