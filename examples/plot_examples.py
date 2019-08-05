import seaborn as sns
import matplotlib.pyplot as plt
from cbs_utils.plotting import (CBSPlotSettings, add_axis_label_background)
from cbs_utils.misc import create_logger

logger = create_logger()
figure_properties = CBSPlotSettings()

iris = sns.load_dataset('iris')
logger.info(iris.head())
old_cols = iris.columns

# hernoem de kolommen
iris.rename(columns={
    "sepal_length": "Stempellengte",
    "sepal_width": "Stempelbreedte",
    "petal_length": "Kroonbladlengte",
    "petal_width": "Kroonbladbreedte"
}, inplace=True)

#  bereken gemiddelde waardes
geometry_df = iris.groupby("species").mean()
geometry_df.index.name = "Soort bloem"

logger.info(geometry_df)

# initieer plot
fig, axis = plt.subplots(nrows=1, ncols=1)

# pas marges aan
fig.subplots_adjust(left=0.2, bottom=0.2)

# plot data
geometry_df.plot(kind="barh", ax=axis)

sns.despine(ax=axis)
# axis.tick_params(which="both", bottom=True)
axis.xaxis.grid(True)

axis.set_xlabel("Gemiddelde afmeting [mm]", horizontalalignment="right")
axis.xaxis.set_label_coords(1.0, -0.1)

axis.set_ylabel(geometry_df.index.name, rotation="horizontal", horizontalalignment="left")
axis.yaxis.set_label_coords(0, 1.05)

axis.legend(loc="lower left",
            bbox_to_anchor=(0, 0),
            ncol=2,
            bbox_transform=fig.transFigure,
            frameon=False)

add_axis_label_background(fig, axes=axis)

plt.show()
