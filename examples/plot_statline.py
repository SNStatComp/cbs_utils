import matplotlib.pyplot as plt

try:
    import mpld3
except ModuleNotFoundError:
    mpld3 = None

from cbs_utils.misc import (create_logger, merge_loggers)
from cbs_utils.plotting import CBSPlotSettings
from cbs_utils.readers import StatLineTable

fig_properties = CBSPlotSettings()

logger = create_logger()
merge_loggers(logger, logger_name_to_merge="cbs_utils.readers")

# de tabel id kan je vinden door naar de data set te gaan op statline en in de url op te zoeken.
# in dit geval is de url: https://opendata.cbs.nl/#/CBS/nl/dataset/84410NED/table?ts=1568706226304
# dus we gaan een plaatje maken uit de tabel 84410NED
table_id = "84410NED"

statline = StatLineTable(table_id=table_id)

statline.show_module_table()
statline.show_question_table()

# hiermee worden all vragen van module 13 geplot, dus ook de individuele opties die bij vraag 16
# horen
statline.modules_to_plot = 46

statline.plot()

# only save the first figure for inspection
fig = plt.figure(1)
fig.savefig("firstplot.png")

# toon de inhoud van de data nog een keer
statline.show_selection()
selection = [statline.selection_options[2], 
             statline.selection_options[6], 
             statline.selection_options[-1]]
statline.selection = selection
statline.apply_selection = True
logger.info(f"Select {selection}")

# verkrijg de vragen horen bij vraag 47
question_df = statline.get_question_df(47)
units = question_df[statline.units_key].values[0]
question_df = statline.prepare_data_frame(question_df)

fig, axis = plt.subplots()
fig.subplots_adjust(left=0.5, bottom=0.25, top=0.98)

question_df.plot(kind="barh", ax=axis)
axis.set_ylabel("")
axis.set_xlabel(units)
axis.xaxis.set_label_coords(0.98, -0.1)
axis.legend(bbox_to_anchor=(0.01, 0.00), ncol=2, bbox_transform=fig.transFigure, loc="lower left", 
            frameon=False)
axis.spines['top'].set_visible(False)
axis.spines['bottom'].set_visible(False)
axis.spines['right'].set_visible(False)
axis.spines['left'].set_position('zero')
axis.spines['left'].set_visible(True)
axis.tick_params(which="both", bottom=False, left=False)
axis.xaxis.grid(True)
axis.yaxis.grid(False)
axis.invert_yaxis()

fig.savefig("secondplot.png")

