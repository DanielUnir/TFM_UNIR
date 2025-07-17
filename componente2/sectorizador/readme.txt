# ./sectorizador/readme
# Sectorizador - Microservicio de agrupación de datos en Redis

# Imagen base
- Python 3.10 slim, más ligera que la oficial

# Variables de entorno (.env)
    - ID_SERVICE                                    # Identificador propio del contenedor, para identificarse al conectar con otros servicios

    - REDIS_HOST                                    # Dirección del servidor de Redis al que se conecta
    - REDIS_PORT                                    # Puerto del servidor de Redis al que accede
    - REDIS_TTL                                     # Tiempo de vida (TTL) de las claves en Redis que establecerá en el almacenamiento de datos

    - SECTORIZADOR_INTERVALO                        # Intervalo de cálculo de sectores

# Requerimientos
    - redis==5.0.1                                  # Cliente de Redis en Python
    - numpy==1.26.4                                 # Librería numpy para cálculos
# Dockerfile
- Establece la imagen base, heramientas python auxiliares, requerimientos, carpetas de trabajo y lanza el arranque con el código fuente

# Código fuente
- `sectorizador.py`

# Archivos auxiliares
- `redis_sectorizador.py`

# Proceso resumido
- Conexión con Redis
- Crea una estructura tipo set llamada sector:id_sector, Eliminando su contenido, si ya existía previamente
- Lanza los cálculos de distancia alrededor de los centros de los sectores contra la estructura "aeronaves:geo", e inserta los resultados en los set de cada sector
- Repite el cálculo a intervalos definidos constantes