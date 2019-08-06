import logging
import seaborn as sns
import matplotlib.pyplot as plt
from cbs_utils.plotting import (CBSPlotSettings, add_axis_label_background)
from cbs_utils.misc import (create_logger, merge_loggers)

logger = create_logger(console_log_level=logging.DEBUG)
logger = merge_loggers(logger, "cbs_utils.plotting", logger_level_to_merge=logging.DEBUG)
figure_properties = CBSPlotSettings()

iris = sns.load_dataset('iris')
logger.info(iris.head())
old_cols = iris.columns

# hernoem de kolommen
iris.rename(columns={
    "sepal_length": "Stempellengte",
    "sepal_width": "Stempelbreedte",
    "petal_length": "Bladlengte",
    "petal_width": "Bladbreedte"
}, inplace=True)

#  bereken gemiddelde waardes
geometry_df = iris.groupby("species").mean()
geometry_df.index.name = "Soort bloem"

logger.info(geometry_df)

# initieer plot
fig, axis = plt.subplots(nrows=1, ncols=1)

# pas marges aan
fig.subplots_adjust(left=0.2, bottom=0.2)

# plot data. Cbs stijl wil een ruimte tussen de bar van 0.75 pt. Los dit op door een witte rand
geometry_df.plot(kind="barh", ax=axis, edgecolor="white", linewidth=0.75)

# haal de x-as weg maar zet het verticale gris
sns.despine(ax=axis, bottom=True)
axis.xaxis.grid(True)
# haal de tick marks weg
axis.tick_params(which="both", bottom=False, left=False)
# pas de y-as dikte en kleur aan
axis.spines["left"].set_linewidth(1.5)
axis.spines["left"].set_color("cbs:grijs")

# xlabel aan de rechter zijde
axis.set_xlabel("Gemiddelde afmeting [mm]", horizontalalignment="right")
axis.xaxis.set_label_coords(1.0, -0.1)

# ylabel boven aan horizontaal geplot
axis.set_ylabel(geometry_df.index.name, rotation="horizontal", horizontalalignment="left")
axis.yaxis.set_label_coords(0, 1.05)

# de kleur volgorde is per default anders om dan de dataframe volgoeder. Zet hier weer goed
axis.invert_yaxis()

# de legend aan de onderkant
legend = axis.legend(loc="lower left",
                     bbox_to_anchor=(0, 0),
                     ncol=4,
                     bbox_transform=fig.transFigure,
                     frameon=False,
                     title="Afmeting bloemdeel")
legend._legend_box.align = "left"

# voeg het grijs flag met logo toe
add_axis_label_background(fig, axes=axis)

plt.show()
