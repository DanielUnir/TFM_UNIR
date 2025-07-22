# Código fuente del microservicio productor
#   Este script envía datos de aeronaves al topic especificado en Kafka agrupados en batches.
#   Modifica el atributo 'time' de cada aeronave por instante UTC actual para simular detección real.
#   Hace uso de la función agrupar_por_segundo del módulo utilidades para agrupar los datos.
#   Kafka, Redis, los consumidores y clientes deben estar corriendo antes de ejecutar este script. Se ajusta a traves de docker-compose.yml


# Librerías necesarias
import  json
import  os
import  time
from    datetime        import datetime, timezone
import  logging
from    kafka           import KafkaProducer
from    utilidades      import cargar_datos, agrupar_por_segundo


# Configuración de variables de entorno
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "adsb.aeronaves")            # Nombre del topic de Kafka al que se enviarán los datos
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")   # Dirección del servidor de Kafka (gracias a la red Docker se puede usar el nombre del servicio)
MAX_BATCH = os.getenv("KAFKA_MAX_BATCH_SIZE",100)                   # Número máximo de aeronaves en cada mensaje enviado a Kafka
ID_SERVICE = os.getenv("ID_SERVICE", "productor")                   # Identificador del servicio para trazas
INTERVALO_ADSB= os.getenv("INTERVALO_ADSB_MENSAJES",10)             # Este valor representa la diferencia de tiempos del atributo 'time' de los mensajes ADS-B
                                                                    # Es decir, en cada intervalo sistema ADSB recupera todos los datos de aeronaves que encuentra
                                                                    # No vuelve a recibir hasta el siguiente intervalo.


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


# Función principal para enviar datos agrupados por intervalo
def enviar_datos_por_intervalo():                                     
    """Envia datos de aeronaves agrupados por intervalos al topic de Kafka especificado.
    Se adapta el campo 'time' para asignarlo al instante actual, simulando detección real."""


#   Se ha analizado de los datos disponibles que el archivo cargado, cada registro de aeronave tiene una marca de tiempo
#   los registros están ordenados por esta marca de tiempo de forma que cada 10 segundos aproximadamente
#   existe un conjunto de registros de todas las aeronaves que estaban emitiendo información en ese momento
#   por este motivo, para simular la emisión de datos a intervalos regualres, el productor enviará mensajes 
#   con todos los registros que comparten la misma marca de tiempo cada diez segundos de forma ordenada.

# Crea un productor de Kafka
    producer = KafkaProducer(                                       
        bootstrap_servers=KAFKA_SERVER,                             # Conecta al servidor de Kafka
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),   # Serializa los datos a JSON y los codifica a bytes
        retries=5,                                                  # Reintentos en caso de fallo por partición
        acks='all',                                                 # Espera la confirmación de los líderes y réplicas          
        max_block_ms=45000,                                         # Tiempo max esperando asignación de particiones, evita fallo si el broker es más lento
        request_timeout_ms=20000,                                   # Tiempo max esperando ok del broker, evita fallo por broker lento
        max_request_size=5242880,                                   # Tamaño máximo del mensaje. No es óptimo superior a 1Mb, pero se aumenta para los test a 5 MB
        client_id=ID_SERVICE
    )
    

    datos = cargar_datos()                                          # Carga el archivo completo de datos a traves de la función cargar_datos del módulo utilidades


    t_0 = datetime.now(timezone.utc).timestamp()+40                 # Selecciona el instante t0 del primer envío dentro de x segundos
                                                                    # En este lapso se hará un procesado de los datos de aeronaves
                                                                    # haciendo coincidir el tiempo del envío con el atributo 'time' de las aeronaves
                                                                    # aproximadamente
    intervalo = float(INTERVALO_ADSB)                               # Formatear la variable de entorno

    datos_agrupados = agrupar_por_segundo (datos,t_0, intervalo)    # Agrupa los datos que tengan el mismo valor del atributo 'time' usando la función 
                                                                    # agrupar_por_segundo del módulo utilidades. Así los datos recibidos al mismo tiempo se envían
                                                                    # al mismo tiempo. además ajusta el atributo 'time' de las aeronaves para los envíos.

    maximo_aeronaves= int(MAX_BATCH)                                # Formatear la variable de entorno
                                                                    # Simula que el envío anterior se hizo a falta de tres segundos para completar el intervalo
                                                                    # por lo que el proceso antes del siguiente envío (el primero) debe ser 3 segundos o menos
    

    for k, (segundo, grupo) in enumerate(datos_agrupados.items()):                  # Itera sobre cada grupo de datos, que todos deben tener mismo valor de 'time'
        t_restante= t_0+k*intervalo-datetime.now(timezone.utc).timestamp()          # Calcula el tiempo restante hasta el siguiente envío basado en t_0
        if t_restante>0:
            time.sleep(t_restante)                                                  # Espera el tiempo restante
        
        for i in range(0,len(grupo),maximo_aeronaves):                              # Itera sobre cada subconjunto de tamaño el máximo número de aeronaves por mensaje
            subgrupo=grupo[i:i+maximo_aeronaves]                                    # Conforma el subconjunto
            
            mensaje={                                                               # Crea mensaje a enviar por el productor, con timestamp para cálculo de latencias
                "timestamp_envio":time.time(),
                "aeronaves":subgrupo
            }
            producer.send(KAFKA_TOPIC, value=mensaje)                               # Envía cada mensaje al topic de Kafka
            logging.info(
                f"{ID_SERVICE}: Enviadas {len(subgrupo)} aeronaves al topic '{KAFKA_TOPIC}'.")
    
    producer.flush()                                                                # Asegura que todos los mensajes se envían antes del siguiente grupo        
#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Ejecuta la función si este script es el principal
# Esto permite que el script se ejecute directamente solo si el archivo es ejecutado directamente, no si es importado como módulo
# Esto es útil para pruebas o para ejecutar el productor de forma independiente
# Para dar tiempo al sistema completo espera 30 segundos
if __name__ == "__main__":
    enviar_datos_por_intervalo()
#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


