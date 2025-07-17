#!/bin/bash

# ------------------------------------------------------------------------------
# Script de pruebas automatizadas para el TFM
# ------------------------------------------------------------------------------
# Pruebas de rendimiento sobre la arquitectura completa.

# Funcionalidades principales:
# - Inicialización, monitorización y parada controlada de los contenedores de prueba.
# - Ejecución de métricas sobre Kafka (lag por grupo de consumidores), Redis (uso de operaciones),
#       MongoDB (estadísticas de escritura) y uso de recursos en Docker.
# - Recolección, almacenamiento y limpieza de logs por caso de prueba.
# - Manejo seguro de interrupciones (SIGINT/SIGTERM) garantizando la limpieza del entorno.

# El propósito es garantizar condiciones homogéneas y reproducibles para cada caso,
#   posibilitando un análisis objetivo del rendimiento del sistema bajo distintas configuraciones.

# Para los test 1-2-3 se debe usar el archivo states_2022-06-27-12_UE_reducido.json
# Para los test 4-5-6 se debe usar el archivo states_2022-06-27-12_UE_medio.json
# Para los test 1-2-3 se debe usar el archivo states_2022-06-27-12_UE_completo.json

# Recordar que el archivo se debe ubicar en la carpeta /datos y ajustar el nombre a 'aeronaves_completo.json'

# ------------------------------------------------------------------------------



TIEMPO_EJECUCION=300
DIRECTORIO_BASE=$(pwd)
#DIRECTORIO_TESTS="$DIRECTORIO_BASE/tests"
LOGS_GLOBALES="$DIRECTORIO_BASE/logs_globales"

# Función de parada en caso de interrupción manual
interrumpir_ejecucion() {
    echo "Interrupción detectada. Terminando procesos..."

    # Función auxiliar definida para detener la monitorización
    parar_monitores
    
    # Limpiar recursos de Kafka, Redis y MongoDB
    docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic adsb.aeronaves
    docker exec redis redis-cli FLUSHALL
    #docker exec mongodb mongo adsb_database --quiet --eval 'db.getCollectionNames().forEach(function(c) {db.getCollection(c).drop();})'
    docker exec cliente_historico mongo mongodb://mongodb/adsb_database --quiet --eval 'db.getCollectionNames().forEach(function(c) {db.getCollection(c).drop();})'

    # Parar cualquier contenedor que esté corriendo
    docker-compose down -v 2>/dev/null

    # Eliminar archivos temporales si corresponde
    find ./kafka_datos -mindepth 1 -exec rm -rf {} +
    find ./mongo_datos -mindepth 1 -exec rm -rf {} +
    find ./redis_datos -mindepth 1 -exec rm -rf {} +

    exit 1
}

# Asociar señales SIGINT y SIGTERM a la interrupción para que se pueda detener el script de forma segura
trap interrumpir_ejecucion SIGINT SIGTERM

# Función de monitorización
lanzar_monitores() {
    
    # Monitorización del grupo de consumidores de Redis en Kafka
    (
        while true; do
            docker exec kafka bash -c "/opt/bitnami/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group adsb_redis_group --timeout 45000 >> /bitnami/kafka/data/kafka_lag.log"
            sleep 1
        done
    ) & MON1=$!

    # Monitorización del grupo de consumidores de MongoDB en Kafka
    (
        while true; do
            docker exec kafka bash -c "/opt/bitnami/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group adsb_mongo_group --timeout 45000 >> /bitnami/kafka/data/kafka_lag.log"
            sleep 1
        done
    ) & MON2=$!

    # Monitorización de Redis
    (
        while true; do
            docker exec redis sh -c 'echo $(date -u +%Y-%m-%dT%H:%M:%SZ) | tr -d "\n" >> /data/redis_stats.log && redis-cli INFO stats >> /data/redis_stats.log'
            sleep 10
        done
    ) & MON3=$!

    # Monitorización de MongoDB
    (
        while true; do
            docker exec mongodb sh -c "mongostat --rowcount 1 --noheaders >> /data/db/mongostat.log"
            sleep 30
        done
    ) & MON4=$!

    # Monitorización de Docker
    (
        while true; do
            docker stats --no-stream >> logs/recursos.log
            sleep 2
        done
    ) & MON5=$!

    # Consulta de monitorización de espacio aéreo con Cliente_atm

    (
        while true; do
            echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> logs/estado_atm.log
            curl -s http://localhost:5000/estado_atm | jq . >> logs/estado_atm.log
            sleep 5
        done
    ) & MON6=$!
}

# Función para parar los monitores
parar_monitores() {
    kill $MON1 $MON2 $MON3 $MON4 $MON5 $MON6 2>/dev/null
    wait $MON1 $MON2 $MON3 $MON4 $MON5 $MON6 2>/dev/null
}

# Construir las imágenes Docker para los consumidores, necesarios para la ejecución de los archivos docker-copmpose, pues están definidos por anchors.
docker build -t consumidor_redis:latest ./consumidor_redis
docker build -t consumidor_mongo:latest ./consumidor_mongo


# Bucle principal de ejecución
for i in $(seq -w 7 8); do
    CASO="caso$i"
    RUTA_CASO="$DIRECTORIO_TESTS/$CASO"
    COMPOSE_FILE="docker-compose.test$i.yml"

    echo "=============================="
    echo "Iniciando test: $CASO"
    echo "=============================="


    if [ ! -f "$COMPOSE_FILE" ] || [ ! -f ".env" ]; then
        echo "Faltan archivos necesarios en $CASO. Saltando..."
        continue
    fi

    docker-compose -f "$COMPOSE_FILE" stop                          # Detener contenedores activos si existen
    docker-compose -f "$COMPOSE_FILE" build                         # Construir las imágenes marcadas en el docker-compose del test
    docker-compose -f "$COMPOSE_FILE" up -d --force-recreate|| {    # Reconstruir los contenedores y lanzarlos
        echo "Error al lanzar docker-compose para $CASO"
        continue
    }

    # Espera a que los contenedores estén en proceso de activación y lanza la monitorización definida
    sleep 30
    lanzar_monitores

    echo "Sistema en ejecución..."
    # Tiempo de ejecución definido
    sleep $TIEMPO_EJECUCION

    parar_monitores

    # Eliminacición de parámetros para iniciar el siguiente sistema desde cero, evitando cualquier incidencia en la ejecución siguiente
    docker exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic adsb.aeronaves
    docker exec redis redis-cli FLUSHALL
    #docker exec mongodb mongo adsb_database --quiet --eval 'db.getCollectionNames().forEach(function(c) {db.getCollection(c).drop();})'
    docker exec cliente_historico mongo mongodb://mongodb/adsb_database --quiet --eval 'db.getCollectionNames().forEach(function(c) {db.getCollection(c).drop();})'

    sleep 10

    # Detener contenedores
    docker-compose -f "$COMPOSE_FILE" stop

    # Recuperar estadisticas de las bases de datos y kafka
    mv mongo_datos/mongostat.log logs/mongostat_$CASO.log
    mv redis_datos/redis_stats.log logs/redis_stats_$CASO.log
    mv kafka_datos/kafka_lag.log logs/kafka_lag_$CASO.log

    # Prepraración de logs
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    LOGS_DESTINO="$LOGS_GLOBALES/${CASO}_$TIMESTAMP"
    mkdir -p "$LOGS_DESTINO"
    mv logs/* "$LOGS_DESTINO"/ 2>/dev/null

    # Eliminar archivos temporales 
    find ./kafka_datos -mindepth 1 -exec rm -rf {} +
    find ./mongo_datos -mindepth 1 -exec rm -rf {} +
    find ./redis_datos -mindepth 1 -exec rm -rf {} +

    sleep 10

    echo "Finalizado: $CASO"
done