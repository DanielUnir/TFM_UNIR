# Código auxiliar para `productor.py``
#   Define las funciones para cargar datos de aeronaves y agruparlos


# Librerías necesarias
import  json
import  os
import  logging
from    collections import defaultdict


# Configuración de variables de entorno para el archivo JSON y el identificador del servicio
BATCH_FILE = os.path.join(os.path.dirname(__file__),"data", "aeronaves_completo.json")                      # Obtiene el path del archivo
ID_SERVICE = os.getenv("ID_SERVICE", "productor")                                                           # Identificador del servicio para trazas


# Función para cargar los datos del batch de aeronaves desde un archivo JSON
def cargar_datos():
    """
      Esta función lee el archivo JSON y devuelve los datos como un objeto Python (lista de diccionarios)
    """
    try:
        with open(BATCH_FILE, "r") as f:
            data=json.load(f)                                                                               # Llama a la función _load_json para cargar los datos del archivo
            logging.getLogger(__name__).info(f"{ID_SERVICE}: Datos cargados desde {BATCH_FILE}.")           # Log de información sobre la carga de datos
            return data
    except FileNotFoundError:
        logging.getLogger(__name__).error(f"{ID_SERVICE}: Archivo {BATCH_FILE} no encontrado.")             # Log de error si el archivo no se encuentra
        return []                                                                                           # Retorna una lista vacía si el archivo no se encuentra
    except json.JSONDecodeError:
        logging.getLogger(__name__).error(f"{ID_SERVICE}: Error al decodificar el JSON en {BATCH_FILE}.")   # Log de error si hay un problema al decodificar el JSON
        return []                                                                                           # Retorna una lista vacía si hay un error de decodificación

#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Función para agrupar los datos de aeronaves por segundo
def agrupar_por_segundo(datos, t_inicial, intervalo):
    """
        Esta función toma una lista de datos de aeronaves y los agrupa por el segundo en que fueron recibidos
    """
    datos_agrupados = defaultdict(list)                                                                     # Crea un diccionario con listas como valores

    for aeronave in datos:                                                                                  # Itera sobre cada aeronave en los datos
        datos_agrupados[int(aeronave["time"])].append(aeronave)                                             # Agrupa por el atributo "time" de cada aeronave. 
                                                                                                            # Estos datos presentan conjuntos de aeronaves con el mismo valor de 'time'.
                                                                                                            # Los distintos valores de time están separados un intervalo constante.

    for k, (tiempo, grupo) in enumerate(sorted(datos_agrupados.items())):                                   # Itera sobre cada grupo de aeronaves
        time_aeronave=int(t_inicial+k*intervalo)                                                            # Establece el nuevo valor de 'time' en base al instante del primer envío
        for aeronave in grupo:                                                                              # Iterar sobre cada aeronave del grupo
            aeronave['time_original']=aeronave['time']                                                      # Guardar el valor original del valor 'time'
            aeronave['time']=time_aeronave                                                                  # Reasignar el valor 'time' a las aeronaves agrupadas
    
    return dict(sorted(datos_agrupados.items()))                                                            # Retorna un diccionario ordenado por el tiempo
#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#   ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
