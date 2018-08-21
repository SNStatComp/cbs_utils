# -*- coding: utf-8 -*-
from pkg_resources import get_distribution, DistributionNotFound

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = get_distribution(dist_name).version
except DistributionNotFound:
    __version__ = 'unknown'

try:
    import pint
except ImportError as err:
    print("WARNING: {}".format(err))
else:
    from pint.unit import UnitDefinition
    try:
        # the convention starting from pint t0.8
        from pint.converters import ScaleConverter
    except ImportError:
        # this is only possible in version pint 0.7
        from pint.unit import ScaleConverter

    ureg = pint.UnitRegistry()

    # define short cut for quantity specifier using Q_. e.g. Q_("1 m/s") define 1 meter/second
    Q_ = ureg.Quantity

    # define percentage unit. It is not standard available format
    ureg.define(UnitDefinition('percent', 'pct', (), ScaleConverter(1 / 100.0)))