# ./cliente_atm/Dockerfile
# Dockerfile para el cliente que simula un gestor de trafico aéreo

# Utiliza una imagen base de Python ligera
FROM python:3.10-slim

# Instala las herramientas auxiliares de Python para chequeo del sistema
RUN apt-get update && apt-get install -y procps curl netcat-openbsd iputils-ping && apt-get clean

# Establece la carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copia el contenido del directorio actual al directorio de trabajo en el contenedor
# Esto incluye el código fuente y otros archivos necesarios
COPY app /app

# Instala las dependencias desde requirements.txt
COPY requirements.txt /app/requirements.txt

# Lanza la instalación de las dependencias necesarias para el productor
# Utiliza --no-cache-dir para evitar almacenar en caché los paquetes descargados
# Esto reduce el tamaño de la imagen final y evita problemas de espacio
RUN pip install --no-cache-dir -r requirements.txt

# Evita que Python genere archivos .pyc, lo que puede ahorrar espacio
ENV PYTHONDONTWRITEBYTECODE=1

# Este comando se ejecutará cuando se inicie el contenedor para emitir mensajes automáticamente
CMD ["python", "cliente_atm.py"]