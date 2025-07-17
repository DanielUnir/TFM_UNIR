# Código del cliente histórico para descargar información del espacio aéreo
# Este script define las rutas y funciones para descargar información de aeronaves y sectores específicos


# Importaciones necesarias
from    flask           import Flask, Response, jsonify
from    pymongo         import MongoClient
from    pymongo.errors  import ConnectionFailure
from    datetime        import datetime, timedelta
import  time
import  logging
import  os
import  json

# Librería de archivo config.py
from    config.config          import centro_sectores


# Configuración del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/cliente_historico.log'),
        logging.StreamHandler()
    ]
)

# Inicialización de la aplicación Flask
app = Flask(__name__)

# Configuración de Mongo
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")                             # URI de conexión a MongoDB
MONGO_DB = os.getenv("MONGO_DB", "adsb_database")                                       # Nombre de la base de datos en MongoDB
COLECCION_INTERVALO = int(os.getenv('MONGO_COLECCION_INTERVALO', 15))                   # Intervalo de tiempo en minutos para crear colecciones
ID_SERVICE = os.getenv("ID_SERVICE", "cliente_historico")                               # Identificador del servicio para trazas

# Conexión a MongoDB
uri_id=f"{MONGO_URI}/?appname={ID_SERVICE}"                                             # Identificador del servicio en la conexión

# Conexión a MongoDB
try:
    cliente_mongo = MongoClient(uri_id,maxPoolSize=2,serverSelectionTimeoutMS=2000)     # Crea un cliente de MongoDB, limita las conexiones simultaneas a dos y tiempo de seleccionde servidor
                                                                                        # Evita conexiones automáticas de Flask excesivas o errores por exceso de tiempo en conectar con Mongo
    cliente_mongo.admin.command('ping')                                                 # Verifica la conexión a MongoDB
    logging.info(f"Conectado a MongoDB en {MONGO_URI}.")
except ConnectionFailure as e:                  
    logging.error(f"No se pudo conectar a MongoDB: {e}")
    raise RuntimeError("No se pudo conectar a MongoDB.")


#-------------------------------------------------------------
@app.route('/info', methods=['GET'])
def info():
    """ Proporciona información de las rutas existentes para este cliente."""
    sectores = [s['nombre'] for s in centro_sectores]                                   # Obtiene nombres de sectores definidos en el archivo config.py

    informacion=(
        "Acciones disponibles:\n"
        "1. /descargar/icao24/<icao24>/<fecha_inicio>/<fecha_fin>"
        "Descargar el histórico de una aeronave en un rango de fechas. Use 'YYYY-MM-DD_HH-MM'"
        "2. /descargar/sector/<sector_id>/<fecha_inicio>/<fecha_fin>'"
        "Descargar el tráfico histórico de un sector en un rango de fechas. Use 'YYYY-MM-DD_HH-MM'"
        f"Sectores: {sectores}"
        )
    return Response(
        response=informacion,
        status=200,
        mimetype='text/plain'
    )  # Devuelve la información como texto plano

#-------------------------------------------------------------
# Ruta de prueba para verificar que el servidor está funcionando
@app.route('/ping', methods=['GET'])

# Función para manejar la ruta de prueba a través de un ping
def ping():
    """
    Ruta de prueba para verificar que el servidor está funcionando.
    """
    logging.info("Ping recibido")
    return jsonify({"message": "Pong"}), 200


#-------------------------------------------------------------
# Ruta para obtener la ruta histórica de una aeronave
@app.route('/descargar/icao24/<icao24>/<fecha_inicio>/<fecha_fin>', methods=['GET'])

# Función para manejar la descarga del histórico de una aeronave
def descargar_historico(icao24, fecha_inicio, fecha_fin):
    """
    Ruta para descargar el histórico de una aeronave en un rango de fechas. Use 'YYYY-MM-DD_HH-MM'
    """
    # Obtiene la hora actual para el cálculo de latencia
    timestamp_solicitud = time.time()  
   
    logging.info(f"Descargando histórico para ICAO24: {icao24}, desde {fecha_inicio} hasta {fecha_fin}")
    
    # Convertir las fechas a objetos datetime
    try:
        inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d_%H-%M')
        fin = datetime.strptime(fecha_fin, '%Y-%m-%d_%H-%M')
    except ValueError as e:
        logging.error(f"Error al parsear las fechas: {e}")
        return jsonify({"error": "Formato de fecha incorrecto. Use 'YYYY-MM-DD_HH-MM'"}), 400
    
    
    # Convertir las fechas a timestamps
    inicio_timestamp = int(inicio.timestamp())
    fin_timestamp = int(fin.timestamp())
    logging.info(f"Fechas convertidas a timestamps: inicio={inicio_timestamp}, fin={fin_timestamp}")

    # Colecciones de MongoDB aplicables
        # Se asume que las colecciones tienen el formato 'YYYYMMDDHHMM' y 
        # agrupan los datos de aeronaves en intervalos definidos por COLECCION_INTERVALO
    
    colecciones = []                                                                    # Lista para almacenar los nombres de las colecciones a consultar
    # Ajustar la colección inicial al bloque de tiempo más cercano
    coleccion_intermedia=inicio.replace(
        minute=inicio.minute // COLECCION_INTERVALO * COLECCION_INTERVALO,
        second=0, microsecond=0
        )
    
    while coleccion_intermedia <= fin:                                                  # Iterar desde la colección inicial hasta la final
        coleccion_nombre = coleccion_intermedia.strftime("%Y%m%d%H%M")                  # Formatear la colección como 'YYYYMMDDHHMM'
        colecciones.append(coleccion_nombre)                                            # Añadir la colección a la lista
        coleccion_intermedia += timedelta(minutes=COLECCION_INTERVALO)                  # Incrementar la colección al siguiente bloque de tiempo
    
    logging.info(f"Colecciones a consultar: {colecciones}")


    # Consulta a MongoDB
    try:
        db = cliente_mongo[MONGO_DB]                                                    # Selecciona la base de datos
        resultados = []                                                                 # Lista para almacenar los resultados de la consulta
        for coleccion in colecciones:                                                   # Iterar sobre las colecciones
            # Buscar en la colección actual los datos de la aeronave en el rango de fechas
            datos = db[coleccion].find({"icao24": icao24,"time": {"$gte": inicio_timestamp, "$lte": fin_timestamp}})
            
            for dato in datos:                                                          # Iterar sobre los datos encontrados
                # Convertir el campo 'time' a un formato legible
                dato['time'] = datetime.utcfromtimestamp(dato['time']).strftime('%Y-%m-%d %H-%M:%S')         
                dato.pop('_id', None)                                                   # Eliminar el campo '_id' de los resultados
                logging.info(f"Datos encontrados en {coleccion}: {dato}")
                resultados.append(dato)                                                 # Añadir el dato a los resultados

        if not resultados:
            logging.warning(f"No se encontraron datos para ICAO24: {icao24} en el rango de fechas especificado.")
            return jsonify({"message": "No se encontraron datos para el ICAO24 especificado en el rango de fechas."}), 404
        logging.info(f"Datos encontrados: {len(resultados)} registros.")
        
        resultados.sort(key=lambda x: x['time'])                                        # Ordenar los resultados por fecha
        json_data = json.dumps(resultados, indent=4)                                    # Convertir los resultados a JSON con indentación para mejor legibilidad
        filename = f"historico_{icao24}_{fecha_inicio}_a_{fecha_fin}.json"              # Nombre del archivo JSON a generar
        logging.info(f"Generando archivo JSON: {filename}")
        # Crear una respuesta de Flask con el JSON generado
        response = app.response_class(response=json_data,status=200,mimetype='application/json')
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'    # Configurar la cabecera para descarga
        
        # Calcula la latencia (ms) de la solicitud
        latencia = (time.time() - timestamp_solicitud)*1000  
        logging.info(f"***Latencia_ClienteHistorico_aeronave***{latencia}***ms")        
 
        
        return response                                                                 # Devolver la respuesta con el archivo JSON
    
    except Exception as e:
        logging.error(f"Error al consultar MongoDB: {e}")
        return jsonify({"error": "Error al consultar la base de datos."}), 500

#-------------------------------------------------------------
# Ruta para obtener el tráfico histórica de un sector
@app.route('/descargar/sector/<sector_id>/<fecha_inicio>/<fecha_fin>', methods=['GET'])

# Función para manejar la descarga del tráfico histórica de un sector
def descargar_historico_sector(sector_id, fecha_inicio, fecha_fin):
    """
    Ruta para descargar el tráfico histórico de un sector en un rango de fechas. Use 'YYYY-MM-DD_HH-MM'
    """
    
    # Obtiene la hora actual para el cálculo de latencia
    timestamp_solicitud = time.time()

    logging.info(f"Descargando histórico para sector: {sector_id}, desde {fecha_inicio} hasta {fecha_fin}")
    
    # Convertir las fechas a objetos datetime
    try:
        inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d_%H-%M')
        fin = datetime.strptime(fecha_fin, '%Y-%m-%d_%H-%M')
    except ValueError as e:
        logging.error(f"Error al parsear las fechas: {e}")
        return jsonify({"error": "Formato de fecha incorrecto. Use 'YYYY-MM-DD_HH-MM'"}), 400
    
    # Convertir las fechas a timestamps
    inicio_timestamp = int(inicio.timestamp())
    fin_timestamp = int(fin.timestamp())
    logging.info(f"Fechas convertidas a timestamps: inicio={inicio_timestamp}, fin={fin_timestamp}")

    # Colecciones de MongoDB aplicables
        # Se asume que las colecciones tienen el formato 'YYYYMMDDHHMM' y 
        # agrupan los datos de aeronaves en intervalos definidos por COLECCION_INTERVALO
    
    colecciones = []                                                                    # Lista para almacenar los nombres de las colecciones a consultar
    # Ajustar la colección inicial al bloque de tiempo más cercano
    coleccion_intermedia=inicio.replace(minute=inicio.minute // COLECCION_INTERVALO * COLECCION_INTERVALO,second=0, microsecond=0)
    while coleccion_intermedia <= fin:                                                  # Iterar desde la colección inicial hasta la final
        coleccion_nombre = coleccion_intermedia.strftime("%Y%m%d%H%M")                  # Formatear la colección como 'YYYYMMDDHHMM'
        colecciones.append(coleccion_nombre)                                            # Añadir la colección a la lista
        coleccion_intermedia += timedelta(minutes=COLECCION_INTERVALO)                  # Incrementar la colección al siguiente bloque de tiempo

    logging.info(f"Colecciones a consultar: {colecciones}")

    # Consulta a MongoDB
    try:
        db = cliente_mongo[MONGO_DB]                                                    # Selecciona la base de datos
        resultados = []                                                                 # Lista para almacenar los resultados de la consulta
        for coleccion in colecciones:                                                   # Iterar sobre las colecciones
            datos = db[coleccion].find(                                                 # Buscar en la colección actual los datos del sector en el rango de fechas
                {"sector": sector_id, 
                 "time": {"$gte": inicio_timestamp, "$lte": fin_timestamp}})
            for dato in datos:                                                          # Iterar sobre los datos encontrados
                # Convertir el campo 'time' a un formato legible
                dato['time'] = datetime.utcfromtimestamp(dato['time']).strftime('%Y-%m-%d %H-%M:%S')
                dato.pop('_id', None)                                                   # Eliminar el campo '_id' de los resultados
                logging.info(f"Datos encontrados en {coleccion}: {dato}")
                resultados.append(dato)                                                 # Añadir el dato a los resultados
        
        if not resultados:
            logging.warning(f"No se encontraron datos para el sector: {sector_id} en el rango de fechas especificado.")
            return jsonify({"message": "No se encontraron datos para el sector especificado en el rango de fechas."}), 404
        logging.info(f"Datos encontrados: {len(resultados)} registros.")
        
        resultados.sort(key=lambda x: x['time'])                                        # Ordenar los resultados por fecha
        json_data = json.dumps(resultados, indent=4)                                    # Convertir los resultados a JSON con indentación para mejor legibilidad
        filename = f"historico_sector_{sector_id}_{fecha_inicio}_a_{fecha_fin}.json"    # Nombre del archivo JSON a generar
        logging.info(f"Generando archivo JSON: {filename}")
        # Crear una respuesta de Flask con el JSON generado
        response = app.response_class(response=json_data,status=200,mimetype='application/json')
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'    # Configurar la cabecera para descarga
        
        # Calcula la latencia (ms) de la solicitud
        latencia = (time.time()- timestamp_solicitud)*1000  
        logging.info(f"***Latencia_ClienteHistorico_sector***{latencia}***ms")        
        return response                                                                 # Devolver la respuesta con el archivo JSON
    
    except Exception as e:
        logging.error(f"Error al consultar MongoDB: {e}")
        return jsonify({"error": "Error al consultar la base de datos."}), 500


# Punto de entrada para ejecutar la aplicación Flask
if __name__ == '__main__':
    logging.info("Cliente Histórico iniciado correctamente.")
    app.run(host="0.0.0.0", port=5001)