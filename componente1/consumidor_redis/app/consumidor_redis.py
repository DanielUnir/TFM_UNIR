# Código fuente del microservicio consumidor_redis
#   Este script consume mensajes de un topic de Kafka y actualiza los datos de aeronaves en Redis
#   Junto al archivo cliente_redis.py que contiene la clase RedisHandler para manejar las operaciones de almacenamiento en Redis
#   Kafka y Redis deben estar corriendo antes de ejecutar este script. Se ajusta a traves de docker-compose.yml

#   El mensaje de Kafka contiene
#       {"timestamp_envio", aeronaves:[{aeronave1},{aeronave2}, ...]} 
#   El primer campo permite calcular latencias del sistema. 
#   La lista de aeronaves recibidas comparten el mismo valor del atributo 'time'.
#   La conexión con Kafka se parametriza para que lea los mensajes nuevos del topic tras la conexión, a través de `auto_offset_reset="latest"``


# Librerías necesarias
import  json
import  os
import  time
import  logging
from    kafka           import KafkaConsumer
from    kafka.errors    import NoBrokersAvailable
from    cliente_redis    import RedisHandler


# Configuración de variables de entorno para Kafka y Redis (.env)
TOPIC = os.getenv("KAFKA_TOPIC", "adsb.aeronaves")                              # Nombre del topic de Kafka del que se consumirán los datos
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")               # Dirección del servidor de Kafka (gracias a la red Docker se puede usar el nombre del servicio)
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_REDIS", "adsb_redis_group")             # ID del grupo de consumidores de Kafka
REDIS_HOST = os.getenv("REDIS_HOST", "redis")                                   # Dirección del servidor de Redis (gracias a la red Docker se puede usar el nombre del servicio)
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))                                 # Puerto del servidor de Redis definido en el archivo docker-compose
REDIS_TTL = int(os.getenv("REDIS_TTL", 60))                                     # Tiempo de vida (TTL) de las claves en Redis
ID_SERVICE = os.getenv("ID_SERVICE", "consumidor_redis")                        # Identificador del servicio para trazas


# Configuración del logging
log_file=f"/logs/{ID_SERVICE}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)


# Función auxiliar para definir la altitud de la aeronave
def definir_altitud(mensaje):
    """
    Crea un campo de altitud basado en el mensaje recibido.
    Si el mensaje contiene 'baroaltitude', se usa ese valor; de lo contrario, se usa 'geoaltitude'.
    """
    for k in ['baroaltitude','geoaltitude']:
        valor=mensaje.get(k)
        if isinstance(valor, (int,float)):
            return valor
    return None


# Conexión con Redis a través de la clase definida en `cliente_redis.py``
rdb = RedisHandler(host=REDIS_HOST, port=REDIS_PORT)                            


# Conexión con Kafka
max_retries = 3                                                                 # Número máximo de intentos de conexión a Kafka

for attempt in range(max_retries):                                              # Bucle para intentar conectar a Kafka
    try:
        consumer = KafkaConsumer(                                               # Crea un consumidor de Kafka
            TOPIC,                                                              # Especifica el topic del que se consumirán los mensajes
            bootstrap_servers=[KAFKA_SERVER],                                   # Conecta al servidor de Kafka
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),         # Deserializa los mensajes de JSON a objetos Python
            group_id=KAFKA_GROUP_ID,                                            # Define un grupo de consumidores para manejar la carga de mensajes
            auto_offset_reset="latest",                                         # Configura el consumidor para leer los mensjaes nuevos del topic
            enable_auto_commit=True,                                            # Habilita el auto commit de offsets para que el consumidor registre automáticamente los mensajes leídos
            session_timeout_ms=30000,                                           # Tiempo para considerar fallo del consumidor
            heartbeat_interval_ms=10000,                                        # Envío de señal de actividad del consumidor a Kafka
            max_poll_interval_ms=300000,                                        # Tiempo máximo entre tandas de mensajes cuando el proceso el largo  
            client_id=ID_SERVICE                                                # Identificador del servicio para trazas
        )
        logging.info(f"{ID_SERVICE}:Conectado a Kafka en {KAFKA_SERVER}.")
        break                                                                   # Sale del bucle si se conecta exitosamente
    except NoBrokersAvailable:                                      
        logging.info(f"{ID_SERVICE}:Esperando Kafka, intento {attempt+1}/{max_retries}")
        time.sleep(5)
else:
    raise RuntimeError("{ID_SERVICE}:No se pudo conectar a Kafka.")


# Bucle principal de consumo de mensajes en Kafka
for message in consumer:                                                                # Itera sobre los mensajes del topic especificado
    timestamp_recepcion = time.time()                                                   # Obtiene la hora actual para cálculos de latencia
    grupo = message.value                                                               # Obtiene información ADS-B de todas las aeronaves del mensaje recibido
    
    try:                                                                                # Verifica el mensaje y extrae la información
        aeronaves=grupo["aeronaves"]
        timestamp_envio=grupo["timestamp_envio"]                                                 
    except Exception as e:
        logging.error(f"{ID_SERVICE}:Mensaje incorrecto.")      
        continue
    
    latencia_mensajeria=(timestamp_recepcion-timestamp_envio)*1000                      # Cálculo de lantencia de mensajería en ms
    logging.info(f"{ID_SERVICE}***Latencia_mensajeria***{latencia_mensajeria}***ms")    
    
    aeronaves_correctas=[]                                                              # Grupo vacío inicial

    # Bucle secundario sobre cada aeronave del mensaje recibido para chequeo de claves y establecer el conjunto de aeronaves correctas para almacenar
    for aeronave in aeronaves:                                                          
        
        # El análisis previo de los datos indica que los mensajes son susceptibles de ser corruptos
        #   debido a información incompleta o incorrecta en los campos lat, lon, geoaltitude, baroaltitude
        #   No se aceptan mensajes que no contengan lat, lon y alguna de las opciones geoaltitude,baroaltitude
        
        if not all(                                                                     # Chequeo de atributos lat y lon
            aeronave.get(k) not in [None, "", [], {}] for k in ["lat", "lon"]):    
            continue

        altitud = definir_altitud(aeronave)                                             # Define la altitud de la aeronave, baroaltitude o geoaltitude
        aeronave['altitude'] = altitud                                                  # Añade el campo de altitud al mensaje

        if altitud is None:                                                            # Chequeo de atributo altitude
            continue
        elif altitud<0:                                                                 # Chequeo de aeronave en tierra
            if aeronave.get("onground") is True:                                        # Si está en tierra asigna valor 0 de altitud
                aeronave['geoaltitude']  = 0
                aeronave['baroaltitude'] = 0
                aeronave['altitude']     = 0
            else:
                continue
   

        aeronaves_correctas.append(aeronave)                                            # Se acepta la aeronave y se añade a un listado

    # Una vez procesadas las aeronaves del mensaje, se realizan las operaciones de almacenamiento en Redis
    try:
        rdb.actualizar_aeronaves(aeronaves_correctas, ttl=REDIS_TTL)                    # Llama a la función del cliente Redis para almacenar las aeronaves
        rdb.aeronaves_inactivas(ttl=REDIS_TTL)                                          # Llama a la función del cliente Redis para limpiar aeronaves inactivas


        timestamp_escritura = time.time()                                               # Obtiene la hora actual para cálculos de latencia
        latencia_almacenamiento = (timestamp_escritura - timestamp_recepcion)*1000      # Calcula la latencia (ms) de procesado y almacenamiento      
        logging.info(f"{ID_SERVICE}***Latencia_ConsumidorRedis***{latencia_almacenamiento}***ms")          
        
    except Exception as e:                                                              # Captura cualquier excepción al actualizar la aeronave
        logging.error(f"{ID_SERVICE}:Error de almacenamiento: {e}")
