# Código del cliente ATM para visualizar el estado del espacio aéreo en cada instante
# Este script define las rutas y funciones para obtener el estado del espacio aéreo,
#    información de aeronaves y aeronaves en sectores específicos

# Importaciones necesarias
from    flask      import Flask, jsonify, Response
from    datetime   import datetime
import  json
import  time
import  logging
import  os


# Librerías de archivos redis_cliente_atm.py, config.py
from redis_cliente_atm  import RedisClienteATM
from config.config      import centro_sectores

# Configuración del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/cliente_atm.log'),
        logging.StreamHandler()
    ]
)

# Inicialización de la aplicación Flask
app = Flask(__name__)

# Configuración de Redis
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))

# Inicialización del cliente Redis
redis_cliente = RedisClienteATM(host=redis_host, port=redis_port)

#-------------------------------------------------------------
# Ruta para obtener información de uso
@app.route('/info', methods=['GET'])
# Función para obtener información de uso
def info():
    """ Proporciona información de las rutas existentes para este cliente."""
    sectores = [s['nombre'] for s in centro_sectores]                               # Obtiene nombres de sectores definidos en el archivo config.py

    informacion=(
        "Acciones disponibles:\n"
        "1. /estado_atm Obtiene el estado del espacio aéreo en el instante actual: conteo de aeronaves en cada sector."
        "2. /aeronave/<icao24>  Obtiene la información de una aeronave específica."
        "3. /sector/<sector> Obtiene la lista de aeronaves en un sector específico."
        f"Sectores: {sectores}"
        )
    return Response(
        json.dumps({'info': informacion}, ensure_ascii=False, indent=4), status=200, content_type='application/json; charset=utf-8')

#-------------------------------------------------------------
# Ruta para obtener el estado del espacio aéreo
@app.route('/estado_atm', methods=['GET'])
# Función para obtener el estado del espacio aéreo
def estado_atm():  
    """
    Obtiene el estado del espacio aéreo en el instante actual: conteo de aeronaves en cada sector.
    Devuelve un JSON con la hora de la solicitud y el conteo de aeronaves por sector.
    """
    
    logging.info("Consulta del estado del espacio aéreo iniciada.")

    try:       
        timestamp_solicitud = time.time()                                           # Obtiene la hora actual para el cálculo de latencia
        sectores,time_utc = redis_cliente.conteo_aeronaves_sector()                 # Obtiene el conteo de aeronaves del sector desde Redis y la hora de sectorización
        latencia = (time.time() - timestamp_solicitud)*1000                         # Calcula la latencia (ms) de la solicitud
        logging.info(f"***Latencia_ClienteATM_estadoatm***{latencia}***ms")        
                
        # Devuelve por pantalla el estado del espacio aéreo y la hora aplicable UTC
        return Response(
            json.dumps({
                'Hora UTC': time_utc,
                'Sectorización aplicable': sectores
            }, ensure_ascii=False, indent=4), 
            status=200, 
            content_type='application/json; charset=utf-8'
        )
    except Exception as e:
        logging.error(f"Error al obtener el estado del espacio aéreo: {e}")
        return jsonify({'error': 'Error al obtener el estado del espacio aéreo'}), 500

#-------------------------------------------------------------
# Ruta para obtener la información de una aeronave específica
@app.route('/aeronave/<icao24>', methods=['GET'])
# Función para obtener la información de una aeronave específica
def info_aeronave(icao24):
    """
    Obtiene la información de una aeronave específica.
    Parámetro: icao24. Identificador único de la aeronave (24 bits).
    Devuelve un JSON con la información de la aeronave o un error si no se encuentra.
    """

    logging.info(f"Consulta de información de la aeronave {icao24}.")
 
    try:
        timestamp_solicitud = time.time()                                       # Obtiene la hora actual para cálculo de latencia
        info = redis_cliente.info_aeronave(icao24)                              # Obtiene la información de la aeronave desde Redis
        latencia = (time.time() - timestamp_solicitud)*1000                     # Calcula la latencia (ms) de la solicitud
        logging.info(f"***Latencia_ClienteATM_aeronave***{latencia}***ms")        
        return Response(
            json.dumps({
                'time': datetime.utcfromtimestamp(info['time']).strftime('%Y-%m-%d %H:%M:%S'),
                'icao24': info['icao24'],
                'lat': info['lat'],
                'lon': info['lon'],
                'velocity': info['velocity'],
                'heading': info['heading'],
                'callsign': info['callsign'],
                'altitude': info['altitude']
            }, ensure_ascii=False, indent=4), 
            status=200, 
            content_type='application/json; charset=utf-8'
        )
    except Exception as e:
        logging.error(f"Error al obtener la aeronave {e}")
        return jsonify({'error': 'Error al obtener la aeronave'}), 500

#-------------------------------------------------------------
# Ruta para obtenerla lista de aeronaves en un sector específico
@app.route('/sector/<sector>', methods=['GET'])
# Función para obtener la lista de aeronaves en un sector específico
def aeronaves_sector(sector):
    """
    Obtiene la lista de aeronaves en un sector específico.
    Parámetro: sector. Identificador del sector (por ejemplo, LEAM, LEJR, LEGR, LEMG, LEZL).
    Devuelve un JSON con el sector, el número de aeronaves y la lista de aeronaves en ese sector.
    """

    logging.info(f"Consulta de aeronaves en el sector {sector}.")

    try:
        timestamp_solicitud = time.time()                                       # Obtiene la hora actual para cálculo de latencia
        aeronaves = redis_cliente.obtener_aeronaves_sector(sector)              # Obtiene la lista de aeronaves en el sector desde Redis
        latencia = (time.time() - timestamp_solicitud)*1000  
        logging.info(f"***Latencia_ClienteATM_sector***{latencia}***ms")    
        return Response(
            json.dumps({
                'sector': sector,
                'Número de aeronaves': len(aeronaves),
                'aeronaves': aeronaves
            }, ensure_ascii=False, indent=4), 
            status=200, 
            content_type='application/json; charset=utf-8'
        )
    except Exception as e:
        logging.error(f"Error al obtener las aeronaves en el sector {sector}: {e}")
        return jsonify({'error': 'Error al obtener las aeronaves en el sector'}), 500

#-------------------------------------------------------------
# Punto de entrada para ejecutar la aplicación Flask
if __name__ == '__main__':
    logging.info("Cliente ATM iniciado correctamente.")
    app.run(host="0.0.0.0", port=5000)