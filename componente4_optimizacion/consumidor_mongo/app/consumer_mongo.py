# Código del consumidor de Kafka para recibir datos de aeronaves y almacenarlos en MongoDB
#   Este script consume mensajes de un topic de Kafka y procesa la información para 
#   sectorizar las aeronaves, calcular el nivel de vuelo y almacenar los datos en MongoDB
#   Junto al archivo mongo_preproc.py
#   Kafka y mongo deben estar corriendo antes de ejecutar este script. Se ajusta a traves de docker-compose.yml
#   El mensaje de Kafka contiene
#       {"timestamp_envio", aeronaves:[{aeronave1},{aeronave2}, ...]} 
#   El primer campo permite calcular latencias del sistema. 
#   La lista de aeronaves recibidas comparten el mismo valor del atributo 'time'.

# Importaciones necesarias
import  json
import  os
import  time
import  logging


# Librerías del archivo requeriments.txt y mongo_preproc.py
from    kafka           import KafkaConsumer
from    kafka.admin     import KafkaAdminClient, NewTopic
from    kafka.errors    import NoBrokersAvailable, TopicAlreadyExistsError
from    pymongo         import MongoClient
from    pymongo.errors  import ConnectionFailure
from    mongo_preproc   import sectorizar_aeronave, definir_altitud, definir_FL, insertar_aeronaves

# Configuración de variables de entorno para Kafka y MongoDB (.env)
TOPIC = os.getenv("KAFKA_TOPIC", "adsb.aeronaves")                              # Nombre del topic de Kafka del que se consumirán los datos
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")               # Dirección del servidor de Kafka (gracias a la red Docker se puede usar el nombre del servicio)
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_MONGO", "adsb_mongo_group")             # ID del grupo de consumidores de Kafka
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")                     # URI de conexión a MongoDB
MONGO_DB = os.getenv("MONGO_DB", "adsb_database")                               # Nombre de la base de datos en MongoDB
ID_SERVICE = os.getenv("ID_SERVICE", "consumidor_mongo")                        # Identificador del servicio para trazas
PARTICIONES= int(os.getenv("PARTICIONES_TOPIC", 1))                             # Número de particiones del topic de Kafka, por defecto 1

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

# Conexión a MongoDB
uri_id=f"{MONGO_URI}/?appname={ID_SERVICE}"                                     # Identificador del servicio en la conexión
try:
    cliente_mongo = MongoClient(uri_id)                                         # Crea un cliente de MongoDB
    cliente_mongo.admin.command('ping')                                         # Verifica la conexión a MongoDB
    logging.info(f"{ID_SERVICE}: conectado a MongoDB en {MONGO_URI}.")
except ConnectionFailure as e:                
    logging.error(f"{ID_SERVICE}: No se pudo conectar a MongoDB: {e}")
    raise RuntimeError(f"{ID_SERVICE}: No se pudo conectar a MongoDB.")



# Intentos para conectarse a Kafka
max_retries = 3


# Bucle para intentar conectar a Kafka y preparar la creación del topic antes de iniciar el consumidor
for attempt in range(max_retries):                                              
    try:
        admin= KafkaAdminClient(bootstrap_servers=[KAFKA_SERVER])               # Crea un cliente administrador de Kafka para verificar la existencia del topic
        topic= NewTopic(TOPIC, num_partitions=PARTICIONES, replication_factor=1)# Define el topic con el número de particiones especificado
        admin.create_topics([topic])                                            # Crea el topic si no existe
        admin.close()                                                           # Cierra el cliente administrador de Kafka
        time.sleep(10)                                                          # Espera 10 segundos para asegurar que el topic está listo
        break                                                                   # Sale del bucle si se conecta exitosamente
    except TopicAlreadyExistsError:                                             # Si el topic ya existe, continúa con la conexión
        logging.info(f"{ID_SERVICE}:El topic {TOPIC} ya existe en Kafka.")
        admin.close()                                                           # Cierra el cliente administrador de Kafka
        time.sleep(10)                                                          # Espera 10 segundos para asegurar que el topic está listo
        break
    except NoBrokersAvailable:                                                   # Si no hay brokers disponibles, espera e intenta de nuevo
        logging.info(f"{ID_SERVICE}:No hay brokers disponibles en Kafka. Nuevo intento...")
        time.sleep(5)                                                            # Espera 5 segundos antes de reintentar
else:
    raise RuntimeError("{ID_SERVICE}:No se pudo conectar a Kafka.")


# Bucle para crear el consumidor con Kafka


for attempt in range(max_retries):
    try:
        consumer = KafkaConsumer(                                               # Crea un consumidor de Kafka
            TOPIC,                                                              # Especifica el topic del que se consumirán los mensajes
            bootstrap_servers=[KAFKA_SERVER],                                   # Conecta al servidor de Kafka
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),         # Deserializa los mensajes de JSON a objetos Python
            group_id=KAFKA_GROUP_ID,                                            # Define un grupo de consumidores para manejar la carga de mensajes
            auto_offset_reset="earliest",                                       # Configura el consumidor para leer los mensajes del topic desde el inicio para asegurar no perderlos
            enable_auto_commit=True,                                            # Habilita el auto commit de offsets para que el consumidor registre automáticamente los mensajes leídos
            session_timeout_ms=30000,                                           # Tiempo para considerar fallo del consumidor
            heartbeat_interval_ms=10000,                                        # Envío de señal de actividad del consumidor a Kafka
            max_poll_interval_ms=300000,                                        # Tiempo máximo entre tandas de mensajes cuando el proceso el largo  
            client_id=ID_SERVICE                                                # Identificador del servicio para trazas       
        )
        logging.info(f"{ID_SERVICE}: Conectado a Kafka en {KAFKA_SERVER}.")
        break                                                                   # Sale del bucle si se conecta exitosamente

    except NoBrokersAvailable:                                      
        logging.info(f"{ID_SERVICE}: Esperando Kafka, intento {attempt+1}/{max_retries}")
        time.sleep(5)                                                           # Espera 5 segundos antes de reintentar la conexión a Kafka

else:
    raise RuntimeError(f"{ID_SERVICE}: no se pudo conectar a Kafka.")

logging.info(f"{ID_SERVICE}: esperando mensajes en el topic {TOPIC}...")        




for message in consumer:                                                        # Itera sobre los mensajes del topic especificado
        
    grupo = message.value                                                       # Obtiene información ADS-B de todas las aeronaves del mensaje recibido
    
    try:                                                                        # Verifica el mensaje y extrae la información
        aeronaves=grupo["aeronaves"]
        timestamp_envio=grupo["timestamp_envio"]                                                 
    except Exception as e:
        logging.error(f"{ID_SERVICE}: Mensaje incorrecto.")      
        continue
    timestamp_recepcion = time.time()                                           # Obtiene la hora actual para cálculos de latencia
    latencia_mensajeria=(timestamp_recepcion-timestamp_envio)*1000                      # Cálculo de lantencia de mensajería en ms
    logging.info(f"{ID_SERVICE}***Latencia_mensajeria***{latencia_mensajeria}***ms")    


    aeronaves_correctas=[]                                                              # Grupo vacío inicial


    for aeronave in aeronaves:                                                          # Itera sobre cada aeronave para chequeo de claves
        
        # El análisis de los datos indica que los mensajes son susceptibles de ser corruptos
        #   debido a información incompleta o incorrecta en los campos lat, lon, geoaltitude, baroaltitude
        #   No se aceptan mensajes que no contengan lat, lon y alguna de las opciones geoaltitude,baroaltitude
        
        if not all(                                                                     # Chequeo de atributos lat y lon
            aeronave.get(k) not in [None, "", [], {}] for k in ["lat", "lon"]):    
            continue

        altitud = definir_altitud(aeronave)                                             # Define la altitud de la aeronave, baroaltitude o geoaltitude
        aeronave['altitude'] = altitud                                                  # Añade el campo de altitud al mensaje

        if altitud is None:                                                             # Chequeo de atributo altitude
            continue
        elif altitud<0:                                                                 # Chequeo de aeronave en tierra
            if aeronave.get("onground") is True:                                        # Si está en tierra asigna valor 0 de altitud
                aeronave['geoaltitude']  = 0
                aeronave['baroaltitude'] = 0
                aeronave['altitude']     = 0
            else:                                                                       # Si no está en tierra pero tiene valor negativo de altitud se considera mensaje corrupto
                continue
        
        

        try:
            fl = definir_FL(altitud)                                                    # Calcula el nivel de vuelo (FL) de la aeronave
            sector = sectorizar_aeronave(aeronave)                                      # Sectoriza la aeronave según su latitud y longitud

            aeronave['FL'] = fl                                                         # Añade el campo de nivel de vuelo (FL) al mensaje
            aeronave['sector'] = sector                                                 # Añade el campo de sector al mensaje
            aeronave['location'] = {                                                    # Añade el campo de ubicación geoespacial al mensaje
                "type": "Point",
                "coordinates": [aeronave['lon'], aeronave['lat']]
            }
        except Exception as e: 
            continue
        
        aeronaves_correctas.append(aeronave)                                            # Se acepta la aeronave

    if not aeronaves_correctas:                                                         # Evita cálculos innecesarios si no hay aeronaves válidas
        logging.warning(f"{ID_SERVICE}: Ninguna aeronave válida en el mensaje.")        
        continue

    try:
        time_coleccion=aeronaves_correctas[-1]['time']                                  # Obtiene el valor de 'time' de una de las aeronaves del grupo (la última)
        insertar_aeronaves(                                                             # Llama a la función para almacenar en MongoDB en la colección correcta
            cliente_mongo[MONGO_DB],
            aeronaves_correctas,
            time_coleccion
        )

        timestamp_escritura = time.time()                                               # Obtiene la hora actual para cálculos de latencia
        latencia_almacenamiento = (timestamp_escritura - timestamp_recepcion)*1000      # Calcula la latencia (ms) de procesado y almacenamiento
        logging.info(f"{ID_SERVICE}***Latencia_ConsumidorMongo***{latencia_almacenamiento}***ms")
    except Exception as e:
        logging.error(f"{ID_SERVICE}: Error de almacenamiento: {e}")