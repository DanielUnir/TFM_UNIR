# ./config/config.py
#   Contiene la información para las operaciones de sectorización en Redis y en MongoDB.
#   Tras el análisis previo de la información contenida en los datos utilizados en el sistema,
#   se han agrupado los datos en torno a un conjunto de diez centroides obtenidos con técnicas de clustering

#   No se trata de sectores reales de tráfico aéreo
#   Se definen  sectores ficticios para representar zonas geográficas que agrupen las aeronaves

centro_sectores = [
    {"nombre": "sector_CZ_Centro",   "lat": 49.220685, "lon": 16.404559},  # Chequia (Brno)
    {"nombre": "sector_AD",          "lat": 42.557936, "lon": 1.418637},   # Andorra
    {"nombre": "sector_XK",          "lat": 42.503005, "lon": 21.922689},  # Kosovo
    {"nombre": "sector_GB_Oeste",    "lat": 52.535022, "lon": -3.260790},  # Reino Unido (Gales)
    {"nombre": "sector_BE_Este",     "lat": 50.584871, "lon": 5.036587},   # Bélgica (Lieja)
    {"nombre": "sector_PT_Este",     "lat": 38.689577, "lon": -7.024229},  # Portugal (Évora)
    {"nombre": "sector_TR_Oeste",    "lat": 38.013200, "lon": 29.833927},  # Turquía (Denizli)
    {"nombre": "sector_SE_Oeste",    "lat": 57.759383, "lon": 12.910626},  # Suecia (Gotemburgo)
    {"nombre": "sector_RU_Oeste",    "lat": 57.625047, "lon": 30.050872},  # Rusia (Pskov)
    {"nombre": "sector_IT_Norte",    "lat": 45.624955, "lon": 10.111400}   # Italia (Brescia)
]