"""
Definition of CBS rbg colors. Based on the color rgb definitions from the cbs LaTeX template
"""

import logging
import math
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.patches as mpatches
from matplotlib.path import Path as mPath
from matplotlib.image import imread
import matplotlib.transforms as trn
from PIL import Image
from matplotlib import colors as mcolors

logger = logging.getLogger(__name__)

CBS_COLORS_RBG = {
    "corporateblauw": (39, 29, 108),
    "corporatelichtblauw": (0, 161, 205),
    "donkerblauw": (0, 88, 184),
    "donkerblauwvergrijsd": (22, 58, 114),
    "lichtblauw": (0, 161, 205),  # zelfde als corporatelichtblauw
    "lichtblauwvergrijsd": (5, 129, 162),
    "geel": (255, 204, 0),
    "geelvergrijsd": (255, 182, 0),
    "oranje": (243, 146, 0),
    "oranjevergrijsd": (206, 124, 0),
    "rood": (233, 76, 10),
    "roodvergrijsd": (178, 61, 2),
    "roze": (175, 14, 128),
    "rozevergrijsd": (130, 4, 94),
    "grasgroen": (83, 163, 29),
    "grasgroenvergrijsd": (72, 130, 37),
    "appelgroen": (175, 203, 5),
    "appelgroenvergrijsd": (137, 157, 12),
    "violet": (172, 33, 142),
    "lichtgrijs": (224, 224, 224),  # 12% zwart
    "grijs": (102, 102, 102),  # 60% zwart
    "logogrijs": (115, 115, 115),  # 55% zwart
    "codekleur": (88, 88, 88),
}

# prepend 'cbs:' to all color names to prevent collision
CBS_COLORS = {"cbs:" + name: (value[0] / 255, value[1] / 255, value[2] / 255)
              for name, value in CBS_COLORS_RBG.items()}

# update the matplotlib colors
mcolors.get_named_colors_mapping().update(CBS_COLORS)

# deze dictionairy bevat meerdere palettes
CBS_PALETS = dict(
    koel=[
        "cbs:corporatelichtblauw",
        "cbs:donkerblauw",
        "cbs:appelgroen",
        "cbs:grasgroen",
        "cbs:oranje",
        "cbs:roze",
    ],
    warm=[
        "cbs:rood",
        "cbs:geel",
        "cbs:roze",
        "cbs:oranje",
        "cbs:grasgroen",
        "cbs:appelgroen",
    ]
)


def get_color_palette(style="koel"):
    """
    Set the color palette

    Parameters
    ----------
    style: {"koel", "warm"), optional
        Color palette to pick. Default = "koel"

    Returns
    -------
    mpl.cycler:
        cbs_color_cycle

    Notes
    -----
    in order to set the cbs color palette default::

        import matplotlib as mpl
        from cbs_utils.plotting import get_color_palette
        mpl.rcParams.update({'axes.prop_cycle': get_color_palette("warm")}
    """
    try:
        cbs_palette = CBS_PALETS[style]
    except KeyError:
        raise KeyError(f"Did not recognised style {style}. Should be one of {CBS_PALETS.keys()}")
    else:
        cbs_color_cycle = mpl.cycler(color=cbs_palette)

    return cbs_color_cycle


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
    color_palette: {"koel", "warm"}, optional
        Pick color palette for the plot. Default is "koel"
    font_size: int, optional
        Size of all fonts. Default = 8


    Th  variables are set to make sure that the figure have the exact same size as the document,
    such that we do not have to rescale them. In this way the fonts will have the same size
    here as in the document

    """

    def __init__(self,
                 fig_width_in_inch: float = None,
                 fig_height_in_inch: float = None,
                 number_of_figures_cols: int = 1,
                 number_of_figures_rows: int = 2,
                 text_width_in_pt: float = 392.64813,
                 text_height_in_pt: float = 693,
                 text_margin_bot_in_inch: float = 1.0,  # margin in inch
                 ratio_option="golden_ratio",
                 plot_parameters: dict = None,
                 color_palette: str = "koel",
                 font_size: int = 8
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

        if fig_height_in_inch is not None:
            self.fig_height = fig_height_in_inch
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
            params = {'axes.labelsize': font_size,
                      'font.size': font_size,
                      'legend.fontsize': font_size,
                      'xtick.labelsize': font_size,
                      'ytick.labelsize': font_size,
                      'figure.figsize': self.fig_size,
                      'hatch.color': 'cbs:lichtgrijs',
                      'axes.prop_cycle': get_color_palette(color_palette),
                      'axes.edgecolor': "cbs:grijs",
                      'axes.linewidth': 1.5,
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


def add_cbs_pnglogo_to_plot(fig,
                            axes=None,
                            image=None,
                            margin_x=6,
                            margin_y=6,
                            loc="lower left",
                            zorder=10, color="blauw", alpha=1.0,
                            logo_width_in_mm=3.234,
                            logo_height_in_mm=4.995,
                            resample=False,
                            ):
    """
    Add a CBS logo to a plot

    Parameters
    ----------
    fig : `mpl.pyplot.axes.Axes` object
    image: mpl.image or None
        To prevent reading the logo many time you can read it once and pass the return image as an
        argument in the next call
    color: {"blauw", "wit", "grijs"}
        Color of the logo. Three colors are available: blauw (blue), wit (white) and grijs (grey).
        Default = "blauw"
    margin_x, margin_y : int
        The *x*/*y* image offset in mm.
    alpha : None or float
        The alpha blending value.
    loc: {"lower left", "upper left", "upper right", "lower right"} or tuple
        Location of the logo.
    size: int
        Size of the icon in pixels

    Returns
    -------
    mpl.image:
        The image of the logo

    """
    bbox = fig.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    width = bbox.width * fig.dpi
    height = bbox.height * fig.dpi

    size_x = (logo_width_in_mm / 25.4) * fig.dpi
    size_y = (logo_height_in_mm / 25.4) * fig.dpi

    if image is None:
        # only load the image if it is not already defined. The image is returned by the
        # function, so you can use this retrun value for the next call, speeding up the code
        image_dir = Path(__file__).parent / "logos"
        if color == "blauw":
            logo_name = "cbs_logo_tiny.png"
        elif color == "wit":
            logo_name = "cbs_logo_wit.png"
        elif color == "grijs":
            logo_name = "cbs_logo_tiny_grijs.pdf"
        else:
            raise ValueError(f"Color {color} not recognised. Please check")
        image_name = image_dir / logo_name

        # image = Image.open(str(image_name))
        # image = imread(str(image_name))
        image = PyPDF2.PdfFileReader(str(image_name))
        if resample:
            image.thumbnail((size_x, size_y))
            # image.resize((int(size_x), int(size_y)), Image.ANTIALIAS)

    # concerteer de marge van mm naar pixles
    margin_x = (margin_x / 25.4) * fig.dpi
    margin_x = (margin_x / 25.4) * fig.dpi

    if isinstance(loc, str):
        # if loc is a string, set the coordinates based on the value
        if loc == "lower left":
            xp = margin_x
            yp = margin_y
        elif loc == "upper left":
            xp = margin_x
            yp = height - image.size[1] - margin_y
        elif loc == "upper right":
            xp = width - image.size[0] - margin_x
            yp = height - image.size[1] - margin_y
        elif loc == "lower right":
            xp = width - image.size[0] - margin_x
            yp = margin_y
        else:
            raise ValueError(f"loc {loc} not recognised. Pleas check")
    else:
        # if it is a tuple, get the values
        xp = width * loc[0]
        yp = height * loc[1]

    # image.shape = [logo_width_in_mm, logo_height_in_mm]
    fig.figimage(image, xo=xp, yo=yp, zorder=zorder, alpha=alpha)

    return image


def add_cbs_logo_to_plot(fig,
                         axes=None,
                         margin_x_in_mm=6.0,
                         margin_y_in_mm=6.0,
                         x0=0,
                         y0=0,
                         width=None,
                         height=None,
                         zorder_start=1,
                         ):
    # maak een box met de coordinaten van de linker onderhoek van het grijze vierkant in axis
    # fractie coordinaten
    if width is None:
        ww = 1
    else:
        ww = width
    if height is None:
        hh = 1
    else:
        hh = height

    if axes is not None:
        tb = trn.Bbox.from_bounds(x0, y0, ww, hh).transformed(axes.transAxes)

        # bereken de linker onderhoek van het figure in Figure coordinaten (pt van linker onderhoek)
        x0 = tb.x0 + (margin_x_in_mm / 25.4) * fig.dpi
        y0 = tb.y0 + (margin_y_in_mm / 25.4) * fig.dpi
    else:
        x0 = (margin_x_in_mm / 25.4) * fig.dpi
        y0 = (margin_y_in_mm / 25.4) * fig.dpi

    all_points = get_cbs_logo_points()

    if axes is not None:
        trans = axes.transAxes
    else:
        trans = fig.transFigure

    zorder = zorder_start
    for points_in_out in all_points:

        for ii, points in enumerate(points_in_out):
            points[:, :2] *= (fig.dpi / 25.4)
            points[:, 0] += x0
            points[:, 1] += y0
            pl = points[:, :2]
            dr = points[:, 2]
            tr_path = mPath(pl, dr).transformed(trans.inverted())
            if ii == 0:
                color = "cbs:logogrijs"
            else:
                color = "cbs:lichtgrijs"
            poly = mpatches.PathPatch(tr_path, fc=color,
                                      linewidth=0,
                                      zorder=zorder,
                                      transform=trans)
            poly.set_clip_on(False)
            if axes is not None:
                axes.add_patch(poly)
            else:
                fig.patches.append(poly)
            zorder += 1


def get_cbs_logo_points(logo_width_in_mm=3.234, logo_height_in_mm=4.995, rrcor=0.171):
    """
    Maak een array met de letters van het CBS logog
    
    Parameters
    ----------
    logo_width_in_mm: float
        Breeedte van het logo
    logo_height_in_mm: float
        Hoogte van het logo
    rrcor: float
        Radius of corners
    
    Returns
    -------
    list
        List met 3 Nx2 arrays

    """

    ww = logo_width_in_mm

    # punten C, beginnen links onder, tegen klok in, binnen en buiten kant
    points_c = [
        np.array(list([
            [0.000, 2.663, mPath.MOVETO],
            [1.430, 2.663, mPath.LINETO],
            [1.430, 3.308, mPath.LINETO],
            [0.644, 3.308, mPath.LINETO],
            [0.644, 3.577, mPath.LINETO],
            [1.430, 3.577, mPath.LINETO],
            [1.430, 4.221, mPath.LINETO],
            [rrcor, 4.221, mPath.LINETO],
            [0.000, 4.221, mPath.CURVE3],
            [0.000, 4.221 - rrcor, mPath.CURVE3],
            [0.000, 2.663, mPath.CLOSEPOLY],
        ])),
        np.array(list([
            [0.188, 2.851, mPath.MOVETO],
            [1.242, 2.851, mPath.LINETO],
            [1.242, 3.120, mPath.LINETO],
            [1.242, 3.120, mPath.LINETO],
            [0.457, 3.120, mPath.LINETO],
            [0.457, 3.765, mPath.LINETO],
            [1.242, 3.765, mPath.LINETO],
            [1.242, 4.033, mPath.LINETO],
            [0.188, 4.033, mPath.LINETO],
            [0.188, 2.851, mPath.CLOSEPOLY],
        ])),
    ]

    points_b1 = [
        np.array(list([
            [1.674, 2.663, mPath.MOVETO],
            [3.234, 2.663, mPath.LINETO],
            [3.234, 4.221 - rrcor, mPath.LINETO],
            [3.234, 4.221, mPath.CURVE3],
            [3.063, 4.221, mPath.CURVE3],
            [2.318, 4.221, mPath.LINETO],
            [2.318, 4.996 - rrcor, mPath.LINETO],
            [2.318, 4.996, mPath.CURVE3],
            [2.147, 4.996, mPath.CURVE3],
            [1.674, 4.996, mPath.LINETO],
            [1.674, 2.663, mPath.CLOSEPOLY],
        ])),
        np.array(list([
            [1.862, 2.851, mPath.MOVETO],
            [3.046, 2.851, mPath.LINETO],
            [3.046, 4.034, mPath.LINETO],
            [2.130, 4.034, mPath.LINETO],
            [2.130, 4.808, mPath.LINETO],
            [1.862, 4.808, mPath.LINETO],
            [1.862, 2.851, mPath.CLOSEPOLY],
        ])),
    ]

    # in binnen stuk van de b
    points_b2 = [
        np.array(list([
            [2.129, 3.121, mPath.MOVETO],
            [2.775, 3.121, mPath.LINETO],
            [2.775, 3.766, mPath.LINETO],
            [2.129, 3.766, mPath.LINETO],
            [2.129, 3.121, mPath.CLOSEPOLY],
        ])),
        np.array(list([
            [2.317, 3.309, mPath.MOVETO],
            [2.588, 3.309, mPath.LINETO],
            [2.588, 3.578, mPath.LINETO],
            [2.317, 3.578, mPath.LINETO],
            [2.317, 3.309, mPath.CLOSEPOLY],
        ])),
    ]

    # de punten van de S, beginnende linksboven, tegen de klok in. Eerst array is de
    # buitenkant, tweede array is de binnenkant
    points_s = [
        np.array(list([
            [0.000, 2.420, mPath.MOVETO],
            [0.000, 0.888, mPath.LINETO],
            [2.589, 0.888, mPath.LINETO],
            [2.589, 0.645, mPath.LINETO],
            [0.000, 0.645, mPath.LINETO],
            [0.000, rrcor, mPath.LINETO],
            [0.000, 0.000, mPath.CURVE3],
            [rrcor, 0, mPath.CURVE3],
            [ww - rrcor, 0, mPath.LINETO],
            [ww, 0, mPath.CURVE3],
            [ww, rrcor, mPath.CURVE3],
            [ww, 1.533, mPath.LINETO],
            [0.646, 1.533, mPath.LINETO],
            [0.646, 1.772, mPath.LINETO],
            [3.234, 1.772, mPath.LINETO],
            [3.234, 2.420, mPath.LINETO],
            [0.000, 2.420, mPath.CLOSEPOLY],
        ])),
        np.array(list([
            [0.188, 2.232, mPath.MOVETO],
            [0.188, 1.076, mPath.LINETO],
            [2.777, 1.076, mPath.LINETO],
            [2.777, 0.457, mPath.LINETO],
            [0.188, 0.457, mPath.LINETO],
            [0.188, 0.188, mPath.LINETO],
            [3.045, 0.188, mPath.LINETO],
            [3.045, 1.345, mPath.LINETO],
            [0.458, 1.345, mPath.LINETO],
            [0.458, 1.960, mPath.LINETO],
            [3.045, 1.960, mPath.LINETO],
            [3.045, 2.232, mPath.LINETO],
            [0.188, 2.232, mPath.CLOSEPOLY],
        ])),
    ]

    return [points_c, points_b1, points_b2, points_s]


def add_axis_label_background(fig, axes, alpha=1,
                              margin=0.05,
                              x0=None,
                              y0=None,
                              loc="east",
                              radius_corner_in_mm=1,
                              logo_margin_x_in_mm=1,
                              logo_margin_y_in_mm=1,
                              add_logo=True,
                              aspect=None
                              ):
    """
    Add a background to the axis label

    Parameters
    ----------
    fig : `mpl.figure.Figure` object
        The total canvas of the Figure
    axes : `mpl.axes.Axes` object
        The axes of the plot to add a box
    alpha: float, optional
        Transparency of the box. Default = 1 (not transparent)
    margin: float, optional
        The margin between the labels and the side of the gray box
    loc: {"east", "south"}
        Location of the background. Default = "east" (left to y-axis. Only "east" and "south" are
        implemented
    add_logo: bool, optional
        If true, add the cbs logo. Default = True
    radius_corner_in_mm: float, optional
        Radius of the corner in mm. Default = 2
    logo_margin_x_in_mm: float
        Distance from bottom of logo in mm. Default = 2
    logo_margin_y_in_mm=2,
        Distance from left of logo in mm. Default = 2
    """

    # the bounding box with respect to the axis in Figure coordinates
    # (0 is bottom left canvas, 1 is top right)
    bbox_axis_fig = axes.get_window_extent().transformed(fig.dpi_scale_trans.inverted())

    # the bounding box with respect to the axis coordinates
    # (0 is bottom left axis, 1 is top right axis)
    bbox_axi = axes.get_tightbbox(fig.canvas.get_renderer()).transformed(axes.transAxes.inverted())

    if loc == "east":
        if x0 is None:
            x0 = bbox_axi.x0 - margin * bbox_axi.width
        x1 = 0

        y0 = 0
        y1 = 1

    elif loc == "south":
        x0 = 0
        x1 = 1

        if y0 is None:
            y0 = bbox_axi.y0 - margin * bbox_axi.height
        y1 = 0
    else:
        raise ValueError(f"Location loc = {loc} is not recognised. Only east and south implemented")

    # width and height of the grey box area
    width = x1 - x0
    height = y1 - y0

    logger.debug(f"Adding rectangle with width {width} and height {height}")

    # eerste vierkant zorgt voor rechte hoeken aan de rechter kant
    if loc == "east":
        rec_p = (x0 + width / 2, y0)
        rec_w = width / 2
        rec_h = height
    elif loc == "south":
        rec_p = (x0, y0 + height / 2)
        rec_w = width
        rec_h = height / 2
    else:
        raise AssertionError(f"This should not happen")

    p1 = mpl.patches.Rectangle(rec_p,
                               width=rec_w,
                               height=rec_h,
                               alpha=alpha,
                               facecolor='cbs:lichtgrijs',
                               edgecolor='cbs:lichtgrijs',
                               zorder=0
                               )
    p1.set_transform(axes.transAxes)
    p1.set_clip_on(False)

    # tweede vierkant zorgt voor ronde hoeken aan de linker kant
    radius_in_inch = radius_corner_in_mm / 25.4
    xshift = radius_in_inch / bbox_axis_fig.width
    yshift = radius_in_inch / bbox_axis_fig.height
    pad = radius_in_inch / bbox_axis_fig.width
    # we moeten corrigeren voor de ronding van de hoeken als we een aspect ratio hebben
    if aspect is None:
        aspect = bbox_axis_fig.height / bbox_axis_fig.width
    logger.debug(f"Using aspect ratio {aspect}")
    p2 = mpl.patches.FancyBboxPatch((x0 + xshift, y0 + yshift),
                                    width=width - 2 * xshift,
                                    height=height - 2 * yshift,
                                    mutation_aspect=1 / aspect,
                                    alpha=alpha,
                                    facecolor='cbs:lichtgrijs',
                                    edgecolor='cbs:lichtgrijs',
                                    transform=fig.transFigure,
                                    zorder=0)
    p2.set_boxstyle("round", pad=pad)
    p2.set_transform(axes.transAxes)
    p2.set_clip_on(False)

    axes.add_artist(p1)
    axes.add_artist(p2)

    if add_logo:
        add_cbs_logo_to_plot(fig=fig,
                             axes=axes,
                             x0=x0,
                             y0=y0,
                             width=width,
                             height=height,
                             margin_x_in_mm=logo_margin_x_in_mm,
                             margin_y_in_mm=logo_margin_y_in_mm)
