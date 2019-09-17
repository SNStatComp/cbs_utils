import logging

try:
    import mpld3
except ModuleNotFoundError:
    mpld3 = None

from cbs_utils.misc import (create_logger, merge_loggers)
from cbs_utils.readers import StatLineTable

logger = create_logger()
merge_loggers(logger, logger_name_to_merge="cbs_utils.readers")

# de tabel id kan je vinden door naar de data set te gaan op statline en in de url op te zoeken.
# in dit geval is de url: https://opendata.cbs.nl/#/CBS/nl/dataset/84410NED/table?ts=1568706226304
# dus we gaan een plaatje maken uit de tabel 84410NED
table_id = "84410NED"

statline = StatLineTable(table_id=table_id)

statline.show_question_table()

# hiermee worden all vragen van module 13 geplot, dus ook de individuele opties die bij vraag 16
# horen
statline.modules_to_plot = 13

statline.plot()


# toon de inhoud van de data nog een keer
statline.describe()

df = statline.get_question_df(16)

