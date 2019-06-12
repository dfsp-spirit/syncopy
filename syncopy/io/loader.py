# -*- coding: utf-8 -*-
#
# Manager for reading a variety of file formats
# 
# Created: 2019-01-23 14:33:12
# Last modified by: Stefan Fuertinger [stefan.fuertinger@esi-frankfurt.de]
# Last modification time: <2019-05-09 13:54:21>

# Local imports
from syncopy.shared.errors import SPYTypeError, SPYValueError
from syncopy.io import load_binary_esi, load_spy

__all__ = ["load_data"]


def load_data(in_name, filetype=None, out=None, **kwargs):
    """Load data from file into data object

    Supported data formats currently are

    Parameters
    ----------
        in_name : 
    
    """

    # Parsing of the actual file(s) happens later, first check `filetype`
    if filetype is not None:
        if not isinstance(filetype, str):
            raise SPYTypeError(filetype, varname="filetype", expected="str")

    # Depending on specified type, call appropriate reading routine
    if filetype is None or filetype in ".spy" or filetype in ["native", "syncopy"]:
        return load_spy(in_name, out=out, **kwargs)
        
    elif filetype in ["esi", "esi-binary"]:
        return load_binary_esi(in_name, out=out, **kwargs)

    else:
        lgl = "any of spy, syncopy, native, esi, esi-binary"
        act = "unknown data-format: `{}`".format(filetype)
        raise SPYValueError(legal=lgl, varname="filetype", actual=act)
