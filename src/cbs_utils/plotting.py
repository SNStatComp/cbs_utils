"""
Definition of CBS rbg colors. Based on the color rgb definitions from the cbs LaTeX template
"""

import logging
import math

import matplotlib as mpl
from matplotlib import colors as mcolors
from matplotlib.image import imread
from pathlib import Path

logger = logging.getLogger(__name__)

CBS_COLORS_RBG = {
    "corporateblauw": (39, 29, 108),
    "corporatelichtblauw": (0, 161, 205),
    "lichtgrijs": (236, 236, 236),
    "geel": (255, 204, 0),
    "geelvergrijsd": (255, 182, 0),
    "oranje": (243, 146, 0),
    "oranjevergrijsd": (206, 124, 0),
    "rood": (233, 76, 10),
    "roodvergrijsd": (178, 61, 2),
    "roze": (175, 14, 128),
    "rozevergrijsd": (130, 4, 94),
    "donkerblauw": (0, 88, 184),
    "donkerblauwvergrijsd": (22, 58, 114),
    "lichtblauwvergrijsd": (5, 129, 162),
    "grasgroen": (83, 163, 29),
    "grasgroenvergrijsd": (72, 130, 37),
    "appelgroen": (175, 203, 5),
    "appelgroenvergrijsd": (137, 157, 12),
    "violet": (172, 33, 142),
}

# prepend 'cbs:' to all color names to prevent collision
CBS_COLORS = {"cbs:" + name: (value[0] / 255, value[1] / 255, value[2] / 255)
              for name, value in CBS_COLORS_RBG.items()}

# update the matplotlib colors
mcolors.get_named_colors_mapping().update(CBS_COLORS)

CBS_COLORS_BLAUW = [
    "cbs:corporatelichtblauw",
    "cbs:corporateblauw",
    "cbs:appelgroen",
    "cbs:grasgroen",
    "cbs:oranje",
    "cbs:violet",
    "cbs:roze",
]
cbs_color_palette_blauw = mpl.cycler(color=CBS_COLORS_BLAUW)


# in order to set the cbs color palette default:
# import matplotlib as mpl
# from cbs_utils.plotting import cbs_color_palette
# mpl.rcParams.update({'axes.prop_cycle': cbs_color_palette}


def report_colors():
    for name, value in CBS_COLORS.items():
        logger.info("{:20s}: {}".format(name, value))


RATIO_OPTIONS = {"golden_ratio", "equal", "from_rows"}


class CBSPlotSettings(object):
    """
    Class to hold the figure size for a standard document

    Parameters
    ----------
    number_of_figures_rows: int
        Number of figure rows
    text_width_in_pt: float, optional
        Width of the text in pt, default = 392.64
    text_height_in_pt: float, optional
        Height of the text in pt, default = 693
    text_margin_bot_in_inch: float, optional
        Space at the bottom in inch. Default = 1 inch
     text_height_in_inch: float, optional
        Explicitly over rules the calculated text height if not None. Default = None
     text_width_in_inch = None,
        Explicitly over rules the calculated text height if not None. Default = None
    plot_parameters: dict, optional
        Dictionary with plot settings. If None (default), take the cbs defaults

    Th  variables are set to make sure that the figure have the exact same size as the document,
    such that we do not have to rescale them. In this way the fonts will have the same size
    here as in the document

    """

    def __init__(self,
                 fig_width_in_inch: float = None,
                 fig_heigt_in_inch: float = None,
                 number_of_figures_cols: int = 1,
                 number_of_figures_rows: int = 2,
                 text_width_in_pt: float = 392.64813,
                 text_height_in_pt: float = 693,
                 text_margin_bot_in_inch: float = 1.0,  # margin in inch
                 ratio_option="golden_ratio",
                 plot_parameters: dict = None,
                 ):

        # set scale factor
        inches_per_pt = 1 / 72.27

        self.number_of_figures_rows = number_of_figures_rows
        self.number_of_figures_cols = number_of_figures_cols
        self.text_width_in_pt = text_width_in_pt
        self.text_height_in_pt = text_height_in_pt
        self.text_margin_bot_in_inch = text_margin_bot_in_inch

        self.text_height = text_height_in_pt * inches_per_pt,
        self.text_width = text_width_in_pt * inches_per_pt

        inches_per_pt = 1 / 72.27
        text_width_in_pt = 392.64813  # add the line \showthe\columnwidth above you figure in latex
        text_height_in_pt = 693  # add the line \showthe\columnwidth above you figure in latex
        text_height = text_height_in_pt * inches_per_pt
        text_width = text_width_in_pt * inches_per_pt
        text_margin_bot = 1.0  # margin in inch

        golden_mean = (math.sqrt(5) - 1) / 2

        if fig_width_in_inch is not None:
            self.fig_width = fig_width_in_inch
        else:
            self.fig_width = text_width / number_of_figures_cols

        if fig_heigt_in_inch is not None:
            self.fig_width = fig_heigt_in_inch
        elif ratio_option == "golden_ratio":
            self.fig_height = self.fig_width * golden_mean
        elif ratio_option == "equal":
            self.fig_height = self.fig_width
        elif ratio_option == "from_rows":
            self.fig_height = (text_height - text_margin_bot) / number_of_figures_rows
        else:
            raise ValueError(f"fig height is not given by 'fig_height_in_inch' and 'ratio_option' "
                             f"= {ratio_option} is not in {RATIO_OPTIONS}")

        self.fig_size = (self.fig_width, self.fig_height)

        if plot_parameters is not None:
            params = plot_parameters
        else:
            params = {'axes.labelsize': 8,
                      'font.size': 8,
                      'legend.fontsize': 8,
                      'xtick.labelsize': 8,
                      'ytick.labelsize': 8,
                      'figure.figsize': self.fig_size,
                      'hatch.color': 'cbs:lichtgrijs',
                      'axes.prop_cycle': cbs_color_palette_blauw
                      }

        mpl.rcParams.update(params)


def add_values_to_bars(axis, type="bar",
                       position="c", format="{:.0f}", x_offset=0, y_offset=0, color="k",
                       horizontalalignment="center", verticalalignment="center"):
    """
    Add the values of the bars as number in the center

    Parameters
    ----------
    axis : `mpl.pyplot.axes.Axes` object
        Axis containing the bar plot
    position: {"c", "t", "l", "r", "b"}, optional
        Location of the numbers, where "c" is center, "t" is top, "l" is left, "r" is right and "b"
        is bottom. Default = "c"
    type: {"bar", "barh"}
        Direction of the bars. Default = "bar", meaning vertical bars. Alternatively you need to
        specify "barh" for horizontal bars.
    format: str, optional
        Formatter to use for the numbers. Default = "{:.0f}" (remove digits from float)
    x_offset: float, optional
        x offset in pt. Default = 0
    y_offset: float, optional
        y offset in pt. Default = 0
    color: "str", optional
        Color of the characters, Default is black
    horizontalalignment: str, optional
        Horizontal alignment of the numbers. Default = "center"
    verticalalignment: str, optional
        Vertical alignment of the numbers Default = "center"
    ):
    """

    # voeg percentage to aan bars
    for patch in axis.patches:
        b = patch.get_bbox()
        cx = (b.x1 + b.x0) / 2
        cy = (b.y1 + b.y0) / 2
        hh = (b.y1 - b.y0)
        ww = (b.x1 - b.x0)
        if position == "c":
            (px, py) = (cx, cy)
        elif position == "t":
            (px, py) = (cx, cy + hh / 2)
        elif position == "b":
            (px, py) = (cx, cy - hh / 2)
        elif position == "l":
            (px, py) = (cx - ww / 2, cy)
        elif position == "r":
            (px, py) = (cx + ww / 2, cy)
        else:
            raise ValueError(f"position = {position} not recognised. Please check")

        # add offsets
        (px, py) = (px + x_offset, py + y_offset)

        if type == "bar":
            value = hh
        elif type == "barh":
            value = ww
        else:
            raise ValueError(f"type = {type} not recognised. Please check")

        # make the value string using the format specifier
        value_string = format.format(value)

        axis.annotate(value_string, (px, py), color=color,
                      horizontalalignment=horizontalalignment,
                      verticalalignment=verticalalignment)


def add_log_to_plot(axis, scale=0.1, image=None, x_offset=0, y_offset=0, loc="lower left",
                    color="blauw"):
    """
    Add a CBS logo to a plot

    Parameters
    ----------
    axis : `mpl.pyplot.axes.Axes` object
    image: mpl.image or None
        To prevent reading the logo many time you can read it once and pass the return image as an
        argument in the next call
    color: {"blauw", "wit", "grijs"}
        Color of the logo. Three colors are available: blauw (blue), wit (white) and grijs (grey).
        Default = "blauw

    Returns
    -------
    mpl.image:
        The image of the logo

    """
    if image is None:
        image_dir = Path("logos")
        if color == "blauw":
            logo_name = "cbs_logo.png"
        elif color == "wit":
            logo_name = "cbs_logo_wit.png"
        elif color == "grijs":
            logo_name = "cbs_logo_grijs.png"
        else:
            raise ValueError(f"Color {color} not recognised. Please check")
        image_name = image_dir / logo_name
        image = imread(image_name)

    xlim = axis.xlim()
    ylim = axis.ylim()

    dx = scale * (xlim[1] - xlim[0])
    dy = scale * (ylim[1] - ylim[0])

    if loc == "lower left":
        x0 = xlim[0]
        y0 = ylim[0]
    elif loc == "upper left":
        x0 = xlim[0]
        y0 = ylim[1] - dy
    elif loc == "upper right":
        x0 = xlim[1] - dx
        y0 = ylim[1] - dy
    elif loc == "lower right":
        x0 = xlim[1] - dx
        y0 = ylim[0]
    else:
        raise ValueError(f"loc {loc} not recognised. Please check")

    x0 += x_offset
    y0 += y_offset

    x1 = x0 + dx
    y1 = y0 + dy

    axis.imshow(image, aspect='auto', extent=(x0, x1, y0, y1), zorder=-1)

    return image
