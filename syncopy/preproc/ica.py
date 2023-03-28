# -*- coding: utf-8 -*-
#
# Syncopy 'Independent Component Analysis' (ICA) frontend.
# Our implementation is based on the FastICA algorithm by Aapo Hyvärinen,
# which is available in scikit-learn.
#

# Builtin/3rd party package imports
import numpy as np

# Syncopy imports
from syncopy import AnalogData
from syncopy.shared.parsers import data_parser, scalar_parser, array_parser
from syncopy.shared.tools import get_defaults, get_frontend_cfg
from syncopy.shared.errors import SPYValueError

from syncopy.shared.kwarg_decorators import (
    unwrap_cfg,
    unwrap_select,
    detect_parallel_client,
)

from syncopy.shared.input_processors import (
    check_effective_parameters,
    check_passed_kwargs,
)

from .compRoutines import SpyFastICA

available_methods = ("fastica",)

@unwrap_cfg
@unwrap_select
@detect_parallel_client
def runica(
    data,
    n_components=None,
    algorithm='parallel',
    whiten='unit-variance',
    fun='logcosh',
    fun_args=None,
    max_iter=200,
    tol=1e-4,
    w_init=None,
    whiten_solver='svd',
    random_state=None,
    **kwargs,
):
    """
    Independent component analysis (ICA) of AnalogData objects.

    Parameters
    ----------
    data : `~syncopy.AnalogData`
        A non-empty Syncopy :class:`~syncopy.AnalogData` object

    Returns
    -------
    weights : `~syncopy.AnalogData`
        The weights
    sphere : numpy.ndarray
        The computed sphering matrix

    Examples
    --------
    In the following, `adata` is an instance of :class:`~syncopy.AnalogData`.

    ICA with the default FastICA method:

    >>> weights, sphere = spy.runica(adata)

    References
    ----------
    Aapo Hyvärinen. Fast and robust fixed-point algorithms for independent component analysis.
    IEEE Transactions on Neural Networks, 10(3):626-634, 1999. doi:10.1109/72.761722.

    See also
    ---------
    `The EEGLAB tutorial on ICA <https://eeglab.org/tutorials/06_RejectArtifacts/RunICA.html>`_
    sklearn.decomposition.FastICA : the FastICA implementation in `scikit-learn`
    """


    method="fastica"  # Currently only one method is available.

    fit_params = {
        'n_components': n_components,
        'algorithm': algorithm,
        'whiten' : whiten,
        'fun': fun,
        'fun_args' : fun_args,
        'max_iter' : max_iter,
        'tol' : tol,
        'w_init' : w_init,
        'whiten_solver' : whiten_solver,
        'random_state': random_state
    }

    # Validate input


    # Make sure our one mandatory input object can be processed
    data_parser(data, varname="data", dataclass="AnalogData", writable=None, empty=False)
    timeAxis = data.dimord.index("time")

    # Get everything of interest in local namespace
    defaults = get_defaults(runica)
    lcls = locals()
    # check for ineffective additional kwargs
    check_passed_kwargs(lcls, defaults, frontend_name="runica")

    new_cfg = get_frontend_cfg(defaults, lcls, kwargs)

    if method not in available_methods:
        raise SPYValueError(f"one of {available_methods}", "method", method)

    # If a subset selection is present, get sampleinfo and check for equidistancy.
    if data.selection is not None:
        # user picked discrete set of time points
        if isinstance(data.selection.time[0], list):
            lgl = "equidistant time points (toi) or time slice (toilim)"
            actual = "non-equidistant set of time points"
            raise SPYValueError(legal=lgl, varname="select", actual=actual)

    # Prepare keyword dict for logging history in data object.
    log_dict = {
        "ica_method": method,
        "ica_params": fit_params
    }

    out = AnalogData(dimord=data.dimord)

    if method == "fastica":
        icaMethod = SpyFastICA(
            samplerate=data.samplerate,
            timeAxis=timeAxis,
            fit_params=fit_params
        )

    icaMethod.initialize(
        data,
        data._stackingDim,
        chan_per_worker=kwargs.get("chan_per_worker"),
        keeptrials=True,
    )

    icaMethod.compute(
        data, out, parallel=kwargs.get("parallel"), log_dict=log_dict
    )

    out.cfg.update(data.cfg)
    out.cfg.update({'runica': new_cfg})
    return out



