"""
Definition of CBS rbg colors. Based on the color rgb definitions from the cbs LaTeX template
"""

import logging
import math

import matplotlib as mpl
from matplotlib import colors as mcolors

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


class FigureSizeForPaper(object):
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

    Th  variables are set to make sure that the figure have the exact same size as the document,
    such that we do not have to rescale them. In this way the fonts will have the same size
    here as in the document

    """

    def __init__(self,
                 fig_width_in_inch: float = None,
                 number_of_figures_cols: int = 1,
                 number_of_figures_rows: int = 2,
                 text_width_in_pt: float = 392.64813,
                 text_height_in_pt: float = 693,
                 text_margin_bot_in_inch: float = 1.0,  # margin in inch
                 text_height_in_inch = None,
                 text_width_in_inch = None,
                 height_from_gold_ratio = False
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

        if height_from_gold_ratio:
            self.fig_height = self.fig_width * golden_mean
        else:
            self.fig_height = (text_height - text_margin_bot) / number_of_figures_rows

        self.fig_size = (self.fig_width, self.fig_height)
