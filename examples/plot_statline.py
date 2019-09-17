import logging

try:
    import mpld3
except ModuleNotFoundError:
    mpld3 = None

from cbs_utils.misc import create_logger
from cbs_utils.readers import StatLineTable

logger = create_logger()

# de tabel id kan je vinden door naar de data set te gaan op statline en in de url op te zoeken.
# in dit geval is de url: https://opendata.cbs.nl/#/CBS/nl/dataset/84410NED/table?ts=1568706226304
# dus we gaan een plaatje maken uit de tabel 84410NED
table_id = 84410

statline = StatLineTable(table_id=table_id)



