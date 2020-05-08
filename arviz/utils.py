# pylint: disable=too-many-nested-blocks
"""General utilities."""
import importlib
import functools
import re
import warnings

import matplotlib.pyplot as plt
import numpy as np

from numpy import newaxis
from .rcparams import rcParams


def _var_names(var_names, data, filter_vars=None):
    """Handle var_names input across arviz.

    Parameters
    ----------
    var_names: str, list, or None
    data : xarray.Dataset
        Posterior data in an xarray
    filter_vars: {None, "like", "regex"}, optional, default=None
        If `None` (default), interpret var_names as the real variables names. If "like",
         interpret var_names as substrings of the real variables names. If "regex",
         interpret var_names as regular expressions on the real variables names. A la
        `pandas.filter`.

    Returns
    -------
    var_name: list or None
    """
    if var_names is not None:

        if isinstance(var_names, str):
            var_names = [var_names]

        if isinstance(data, (list, tuple)):
            all_vars = []
            for dataset in data:
                dataset_vars = list(dataset.data_vars)
                for var in dataset_vars:
                    if var not in all_vars:
                        all_vars.append(var)
        else:
            all_vars = list(data.data_vars)

        all_vars_tilde = [var for var in all_vars if var.startswith("~")]
        if all_vars_tilde:
            warnings.warn(
                """ArviZ treats '~' as a negation character for variable selection.
                   Your model has variables names starting with '~', {0}. Please double check
                   your results to ensure all variables are included""".format(
                    ", ".join(all_vars_tilde)
                )
            )

        excluded_vars = [
            var[1:] for var in var_names if var.startswith("~") and var not in all_vars
        ]
        filter_vars = str(filter_vars).lower()

        if excluded_vars:
            if filter_vars in ("like", "regex"):
                for pattern in excluded_vars[:]:
                    excluded_vars.remove(pattern)
                    if filter_vars == "like":
                        real_vars = [real_var for real_var in all_vars if pattern in real_var]
                    else:
                        # i.e filter_vars == "regex"
                        real_vars = [
                            real_var for real_var in all_vars if re.search(pattern, real_var)
                        ]
                    excluded_vars.extend(real_vars)
            var_names = [var for var in all_vars if var not in excluded_vars]

        else:
            if filter_vars == "like":
                var_names = [var for var in all_vars for name in var_names if name in var]
            elif filter_vars == "regex":
                var_names = [var for var in all_vars for name in var_names if re.search(name, var)]

        existing_vars = np.isin(var_names, all_vars)
        if not np.all(existing_vars):
            raise KeyError(
                "{} var names are not present in dataset".format(
                    np.array(var_names)[~existing_vars]
                )
            )

    return var_names


class lazy_property:  # pylint: disable=invalid-name
    """Used to load numba first time it is needed."""

    def __init__(self, fget):
        """Lazy load a property with `fget`."""
        self.fget = fget

        # copy the getter function's docstring and other attributes
        functools.update_wrapper(self, fget)

    def __get__(self, obj, cls):
        """Call the function, set the attribute."""
        if obj is None:
            return self

        value = self.fget(obj)
        setattr(obj, self.fget.__name__, value)
        return value


class maybe_numba_fn:  # pylint: disable=invalid-name
    """Wrap a function to (maybe) use a (lazy) jit-compiled version."""

    def __init__(self, function, **kwargs):
        """Wrap a function and save compilation keywords."""
        self.function = function
        self.kwargs = kwargs

    @lazy_property
    def numba_fn(self):
        """Memoized compiled function."""
        try:
            numba = importlib.import_module("numba")
            numba_fn = numba.jit(**self.kwargs)(self.function)
        except ImportError:
            numba_fn = self.function
        return numba_fn

    def __call__(self, *args, **kwargs):
        """Call the jitted function or normal, depending on flag."""
        if Numba.numba_flag:
            return self.numba_fn(*args, **kwargs)
        else:
            return self.function(*args, **kwargs)


class interactive_backend:  # pylint: disable=invalid-name
    """Context manager to change backend temporarily in ipython sesson.

    It uses ipython magic to change temporarily from the ipython inline backend to
    an interactive backend of choice. It cannot be used outside ipython sessions nor
    to change backends different than inline -> interactive.

    Notes
    -----
    The first time ``interactive_backend`` context manager is called, any of the available
    interactive backends can be chosen. The following times, this same backend must be used
    unless the kernel is restarted.

    Parameters
    ----------
    backend : str, optional
        Interactive backend to use. It will be passed to ``%matplotlib`` magic, refer to
        its docs to see available options.

    Examples
    --------
    Inside an ipython session (i.e. a jupyter notebook) with the inline backend set:

    .. code::

        >>> import arviz as az
        >>> idata = az.load_arviz_data("centered_eight")
        >>> az.plot_posterior(idata) # inline
        >>> with az.interactive_backend():
        ...     az.plot_density(idata) # interactive
        >>> az.plot_trace(idata) # inline

    """

    # based on matplotlib.rc_context
    def __init__(self, backend=""):
        """Initialize context manager."""
        try:
            from IPython import get_ipython
        except ImportError as err:
            raise ImportError(
                "The exception below was risen while importing Ipython, this "
                "context manager can only be used inside ipython sessions:\n{}".format(err)
            )
        self.ipython = get_ipython()
        if self.ipython is None:
            raise EnvironmentError("This context manager can only be used inside ipython sessions")
        self.ipython.magic("matplotlib {}".format(backend))

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Exit context manager."""
        plt.show(block=True)
        self.ipython.magic("matplotlib inline")


def conditional_jit(_func=None, **kwargs):
    """Use numba's jit decorator if numba is installed.

    Notes
    -----
        If called without arguments  then return wrapped function.

        @conditional_jit
        def my_func():
            return

        else called with arguments

        @conditional_jit(nopython=True)
        def my_func():
            return

    """
    if _func is None:
        return lambda fn: functools.wraps(fn)(maybe_numba_fn(fn, **kwargs))
    else:
        lazy_numba = maybe_numba_fn(_func, **kwargs)
        return functools.wraps(_func)(lazy_numba)


def conditional_vect(function=None, **kwargs):  # noqa: D202
    """Use numba's vectorize decorator if numba is installed.

    Notes
    -----
        If called without arguments  then return wrapped function.
        @conditional_vect
        def my_func():
            return
        else called with arguments
        @conditional_vect(nopython=True)
        def my_func():
            return

    """

    def wrapper(function):
        try:
            numba = importlib.import_module("numba")
            return numba.vectorize(**kwargs)(function)

        except ImportError:
            return function

    if function:
        return wrapper(function)
    else:
        return wrapper


def numba_check():
    """Check if numba is installed."""
    numba = importlib.util.find_spec("numba")
    return numba is not None


class Numba:
    """A class to toggle numba states."""

    numba_flag = numba_check()

    @classmethod
    def disable_numba(cls):
        """To disable numba."""
        cls.numba_flag = False

    @classmethod
    def enable_numba(cls):
        """To enable numba."""
        if numba_check():
            cls.numba_flag = True
        else:
            raise ValueError("Numba is not installed")


def _numba_var(numba_function, standard_numpy_func, data, axis=None, ddof=0):
    """Replace the numpy methods used to calculate variance.

    Parameters
    ----------
    numba_function : function()
        Custom numba function included in stats/stats_utils.py.

    standard_numpy_func: function()
        Standard function included in the numpy library.

    data : array.
    axis : axis along which the variance is calculated.
    ddof : degrees of freedom allowed while calculating variance.

    Returns
    -------
    array:
        variance values calculate by appropriate function for numba speedup
        if Numba is installed or enabled.

    """
    if Numba.numba_flag:
        return numba_function(data, axis=axis, ddof=ddof)
    else:
        return standard_numpy_func(data, axis=axis, ddof=ddof)


def _stack(x, y):
    assert x.shape[1:] == y.shape[1:]
    return np.vstack((x, y))


def arange(x):
    """Jitting numpy arange."""
    return np.arange(x)


def one_de(x):
    """Jitting numpy atleast_1d."""
    if not isinstance(x, np.ndarray):
        return np.atleast_1d(x)
    if x.ndim == 0:
        result = x.reshape(1)
    else:
        result = x
    return result


def two_de(x):
    """Jitting numpy at_least_2d."""
    if not isinstance(x, np.ndarray):
        return np.atleast_2d(x)
    if x.ndim == 0:
        result = x.reshape(1, 1)
    elif x.ndim == 1:
        result = x[newaxis, :]
    else:
        result = x
    return result


def expand_dims(x):
    """Jitting numpy expand_dims."""
    if not isinstance(x, np.ndarray):
        return np.expand_dims(x, 0)
    shape = x.shape
    return x.reshape(shape[:0] + (1,) + shape[0:])


@conditional_jit(cache=True)
def _dot(x, y):
    return np.dot(x, y)


def _cov_1d(x):
    x = x - x.mean(axis=0)
    ddof = x.shape[0] - 1
    return np.dot(x.T, x.conj()) / ddof


def _cov(data):
    if data.ndim == 1:
        return _cov_1d(data)
    elif data.ndim == 2:
        x = data.astype(float)
        avg, _ = np.average(x, axis=1, weights=None, returned=True)
        ddof = x.shape[1] - 1
        if ddof <= 0:
            warnings.warn("Degrees of freedom <= 0 for slice", RuntimeWarning, stacklevel=2)
            ddof = 0.0
        x -= avg[:, None]
        prod = _dot(x, x.T.conj())
        prod *= np.true_divide(1, ddof)
        prod = prod.squeeze()
        prod += 1e-6 * np.eye(prod.shape[0])
        return prod
    else:
        raise ValueError("{} dimension arrays are not supported".format(data.ndim))


@conditional_jit
def full(shape, x, dtype=None):
    """Jitting numpy full."""
    return np.full(shape, x, dtype=dtype)


def flatten_inference_data_to_dict(
    data,
    var_names=None,
    groups=None,
    dimensions=None,
    group_info=False,
    var_name_format=None,
    index_origin=None,
):
    """Transform data to dictionary.

    Parameters
    ----------
    data : obj
        Any object that can be converted to an az.InferenceData object
        Refer to documentation of az.convert_to_inference_data for details
    var_names : str or list of str, optional
        Variables to be processed, if None all variables are processed.
    groups : str or list of str, optional
        Select groups for CDS. Default groups are
        {"posterior_groups", "prior_groups", "posterior_groups_warmup"}
            - posterior_groups: posterior, posterior_predictive, sample_stats
            - prior_groups: prior, prior_predictive, sample_stats_prior
            - posterior_groups_warmup: warmup_posterior, warmup_posterior_predictive,
                                       warmup_sample_stats
    ignore_groups : str or list of str, optional
        Ignore specific groups from CDS.
    dimension : str, or list of str, optional
        Select dimensions along to slice the data. By default uses ("chain", "draw").
    group_info : bool
        Add group info for `var_name_format`
    var_name_format : str or tuple of tuple of string, optional
        Select column name format for non-scalar input.
        Predefined options are {"brackets", "underscore", "cds"}
            "brackets":
                - add_group_info == False: theta[0,0]
                - add_group_info == True: theta_posterior[0,0]
            "underscore":
                - add_group_info == False: theta_0_0
                - add_group_info == True: theta_posterior_0_0_
            "cds":
                - add_group_info == False: theta_ARVIZ_CDS_SELECTION_0_0
                - add_group_info == True: theta_ARVIZ_GROUP_posterior__ARVIZ_CDS_SELECTION_0_0
            tuple:
                Structure:
                    tuple: (dim_info, group_info)
                        dim_info: (str: `.join` separator,
                                   str: dim_separator_start,
                                   str: dim_separator_end)
                        group_info: (str: group separator start, str: group separator end)
                Example: ((",", "[", "]"), ("_", ""))
                    - add_group_info == False: theta[0,0]
                    - add_group_info == True: theta_posterior[0,0]
    index_origin : int, optional
        Start parameter indices from `index_origin`. Either 0 or 1.

    Returns
    -------
    dict
    """
    from .data import convert_to_inference_data

    data = convert_to_inference_data(data)

    if groups is None:
        groups = ["posterior", "posterior_predictive", "sample_stats"]
    elif isinstance(groups, str):
        if groups.lower() == "posterior_groups":
            groups = ["posterior", "posterior_predictive", "sample_stats"]
        elif groups.lower() == "prior_groups":
            groups = ["prior", "prior_predictive", "sample_stats_prior"]
        elif groups.lower() == "posterior_groups_warmup":
            groups = ["warmup_posterior", "warmup_posterior_predictive", "warmup_sample_stats"]
        else:
            raise TypeError(
                (
                    "Valid predefined groups are "
                    "{posterior_groups, prior_groups, posterior_groups_warmup}"
                )
            )

    if dimensions is None:
        dimensions = "chain", "draw"
    elif isinstance(dimensions, str):
        dimensions = (dimensions,)

    if var_name_format is None:
        var_name_format = "brackets"

    if isinstance(var_name_format, str):
        var_name_format = var_name_format.lower()

    if var_name_format == "brackets":
        dim_join_separator, dim_separator_start, dim_separator_end = ",", "[", "]"
        group_separator_start, group_separator_end = "_", ""
    elif var_name_format == "underscore":
        dim_join_separator, dim_separator_start, dim_separator_end = "_", "_", ""
        group_separator_start, group_separator_end = "_", ""
    elif var_name_format == "cds":
        dim_join_separator, dim_separator_start, dim_separator_end = (
            "_",
            "_ARVIZ_CDS_SELECTION_",
            "",
        )
        group_separator_start, group_separator_end = "_ARVIZ_GROUP_", ""
    elif isinstance(var_name_format, str):
        msg = 'Invalid predefined format. Select one {"brackets", "underscore", "cds"}'
        raise TypeError(msg)
    else:
        (
            (dim_join_separator, dim_separator_start, dim_separator_end),
            (group_separator_start, group_separator_end),
        ) = var_name_format

    if index_origin is None:
        index_origin = rcParams["data.index_origin"]

    data_dict = {}
    for group in groups:
        if hasattr(data, group):
            group_data = getattr(data, group).stack(stack_dimension=dimensions)
            for var_name, var in group_data.data_vars.items():
                var_values = var.values
                if var_names is not None and var_name not in var_names:
                    continue
                for dim_name in dimensions:
                    if dim_name not in data_dict:
                        data_dict[dim_name] = var.coords.get(dim_name).values
                if len(var.shape) == 1:
                    if group_info:
                        var_name_dim = (
                            "{var_name}" "{group_separator_start}{group}{group_separator_end}"
                        ).format(
                            var_name=var_name,
                            group_separator_start=group_separator_start,
                            group=group,
                            group_separator_end=group_separator_end,
                        )
                    else:
                        var_name_dim = "{var_name}".format(var_name=var_name)
                    data_dict[var_name_dim] = var.values
                else:
                    for loc in np.ndindex(var.shape[:-1]):
                        if group_info:
                            var_name_dim = (
                                "{var_name}"
                                "{group_separator_start}{group}{group_separator_end}"
                                "{dim_separator_start}{dim_join}{dim_separator_end}"
                            ).format(
                                var_name=var_name,
                                group_separator_start=group_separator_start,
                                group=group,
                                group_separator_end=group_separator_end,
                                dim_separator_start=dim_separator_start,
                                dim_join=dim_join_separator.join(
                                    (str(item + index_origin) for item in loc)
                                ),
                                dim_separator_end=dim_separator_end,
                            )
                        else:
                            var_name_dim = (
                                "{var_name}" "{dim_separator_start}{dim_join}{dim_separator_end}"
                            ).format(
                                var_name=var_name,
                                dim_separator_start=dim_separator_start,
                                dim_join=dim_join_separator.join(
                                    (str(item + index_origin) for item in loc)
                                ),
                                dim_separator_end=dim_separator_end,
                            )

                        data_dict[var_name_dim] = var_values[loc]
    return data_dict


def get_coords(data, coords):
    """Subselects xarray DataSet or DataArray object to provided coords. Raises exception if fails.

    Raises
    ------
    ValueError
        If coords name are not available in data

    KeyError
        If coords dims are not available in data

    Returns
    -------
    data: xarray
        xarray.DataSet or xarray.DataArray object, same type as input
    """
    if not isinstance(data, (list, tuple)):
        try:
            return data.sel(**coords)

        except ValueError:
            invalid_coords = set(coords.keys()) - set(data.coords.keys())
            raise ValueError("Coords {} are invalid coordinate keys".format(invalid_coords))

        except KeyError as err:
            raise KeyError(
                (
                    "Coords should follow mapping format {{coord_name:[dim1, dim2]}}. "
                    "Check that coords structure is correct and"
                    " dimensions are valid. {}"
                ).format(err)
            )
    if not isinstance(coords, (list, tuple)):
        coords = [coords] * len(data)
    data_subset = []
    for idx, (datum, coords_dict) in enumerate(zip(data, coords)):
        try:
            data_subset.append(get_coords(datum, coords_dict))
        except ValueError as err:
            raise ValueError("Error in data[{}]: {}".format(idx, err))
        except KeyError as err:
            raise KeyError("Error in data[{}]: {}".format(idx, err))
    return data_subset


def credible_interval_warning(credible_interval, hpd_interval):
    """Helper method to warn that credible interval will be deprecated"""

    warnings.warn(
        (
            "Keyword argument credible_interval has been deprecated "
            "Please replace with hpd_interval"
        ),
    )

    if isinstance(credible_interval, str) and credible_interval == "auto":
        warnings.warn(
            ("Argument value 'auto' has been renamed to 'hide'", PendingDeprecationWarning)
        )

    if hpd_interval:
        raise Exception(
            "Both 'credible_interval' and 'hpd_interval' are in "
            "keyword arguments. Please remove 'credible_interval'"
        )

    hpd_interval = credible_interval
    return hpd_interval
