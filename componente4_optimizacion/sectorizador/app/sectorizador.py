# Código del sectorizador para construir las estructuras de datos en Redis que representen las aeronaves activas en diferentes zonas geográficas
#   Junto al archivo redis_sectorizador.py que contiene la clase RedisHandler para manejar las operaciones en Redis y el archivo config.py que contiene la configuración de las zonas geográficas y los aeropuertos.

# En esta fase:
#   No se incluyen sectores reales de tráfico aéreo
#   Se crean sectores ficticios para representar zonas geográficas de cada continente
#   Se crean sectores ficticios de aeropuertos en la zona sur de España

# Importaciones necesarias
import  os
import  time
import  logging

# Librerías del archivo redis_sectorizador.py
from    redis_sectorizador  import RedisSectorizador

# Configuración del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/sectorizador.log'),
        logging.StreamHandler()
    ]
)

# Configuración de variables de entorno para Redis (.env)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")                           # Dirección del servidor de Redis (gracias a la red Docker se puede usar el id del servicio)
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))                         # Puerto del servidor de Redis definido en el archivo docker-compose
INTERVALO = int(os.getenv('SECTORIZADOR_INTERVALO', 10))                # Intervalo de actualización en segundos

# Kafka y Redis deben estar corriendo antes de ejecutar este script. 
# Se ajusta a traves de docker-compose.yml

# Inicializar el cliente de Redis
redis_client = RedisSectorizador(host=REDIS_HOST, port=REDIS_PORT)      # Crea una instancia de RedisSectorizador para manejar las operaciones de sectorización

# La función que se encarga de sectorizar las aeronaves activas en diferentes zonas y actualiza la información en Redis.
def estado_sectores():
    """
    Función para sectorizar las aeronaves activas en diferentes zonas geográficas en Redis.
    """
    while True:
        try:
            timestamp_inicio = time.time()                              # Obtiene el timestamp de escritura. se usará para calcular la latencia
            redis_client.sectorizar()                                                # Llama a la función para sectorizar las aeronaves
            latencia = (time.time() - timestamp_inicio)*1000            # Calcula la latencia (ms) 
            logging.info(f"***Latencia_Sectorizador***{latencia}***ms")        
            logging.info("Sectores actualizados en Redis.")
            time.sleep(INTERVALO)                                       # Espera el intervalo definido antes de la siguiente actualización
        except Exception as e:
            logging.error(f"Error al sectorizar: {e}")                  # Captura y registra cualquier error durante la sectorización
            time.sleep(INTERVALO)                                       # Espera el intervalo definido antes de intentar nuevamente
            continue                                                    # Continúa con la siguiente iteración del bucle

# El bucle principal del script ejecuta la función 
if __name__ == "__main__":
    """
    Punto de entrada del script.
    Ejecuta la función estado_sectores cada INTERVALO segundos.
    """
    estado_sectores()

    
