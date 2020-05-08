"""Forest plot."""
from ..data import convert_to_dataset
from .plot_utils import get_plotting_function
from ..utils import _var_names, get_coords
from ..rcparams import rcParams
from ..utils import credible_interval_warning


def plot_forest(
    data,
    kind="forestplot",
    model_names=None,
    var_names=None,
    filter_vars=None,
    transform=None,
    coords=None,
    combined=False,
    hpd_interval=None,
    rope=None,
    quartiles=True,
    ess=False,
    r_hat=False,
    colors="cycle",
    textsize=None,
    linewidth=None,
    markersize=None,
    ridgeplot_alpha=None,
    ridgeplot_overlap=2,
    ridgeplot_kind="auto",
    ridgeplot_quantiles=None,
    figsize=None,
    ax=None,
    backend=None,
    backend_config=None,
    backend_kwargs=None,
    show=None,
    credible_interval=None,
):
    """Forest plot to compare hpd intervals from a number of distributions.

    Generates a forest plot of 100*(hpd_interval)% hpd intervals from
    a trace or list of traces.

    Parameters
    ----------
    data: obj or list[obj]
        Any object that can be converted to an az.InferenceData object
        Refer to documentation of az.convert_to_dataset for details
    kind: str
        Choose kind of plot for main axis. Supports "forestplot" or "ridgeplot"
    model_names: list[str], optional
        List with names for the models in the list of data. Useful when
        plotting more that one dataset
    var_names: list[str], optional
        List of variables to plot (defaults to None, which results in all
        variables plotted) Prefix the variables by `~` when you want to exclude them
        from the plot.
    filter_vars: {None, "like", "regex"}, optional, default=None
        If `None` (default), interpret var_names as the real variables names. If "like",
        interpret var_names as substrings of the real variables names. If "regex",
        interpret var_names as regular expressions on the real variables names. A la
        `pandas.filter`.
    transform: callable
        Function to transform data (defaults to None i.e.the identity function)
    coords: dict, optional
        Coordinates of var_names to be plotted. Passed to `Dataset.sel`
    combined: bool
        Flag for combining multiple chains into a single chain. If False (default),
        chains will be plotted separately.
    hpd_interval: float, optional
        Plots highest posterior density interval for chosen percentage of density. Defaults to 0.94.
    rope: tuple or dictionary of tuples
        Lower and upper values of the Region Of Practical Equivalence. If a list with one
        interval only is provided, the ROPE will be displayed across the y-axis. If more than one
        interval is provided the length of the list should match the number of variables.
    quartiles: bool, optional
        Flag for plotting the interquartile range, in addition to the hpd_interval intervals.
        Defaults to True
    r_hat: bool, optional
        Flag for plotting Split R-hat statistics. Requires 2 or more chains. Defaults to False
    ess: bool, optional
        Flag for plotting the effective sample size. Defaults to False
    colors: list or string, optional
        list with valid matplotlib colors, one color per model. Alternative a string can be passed.
        If the string is `cycle`, it will automatically chose a color per model from the
        matplotlibs cycle. If a single color is passed, eg 'k', 'C2', 'red' this color will be used
        for all models. Defauls to 'cycle'.
    textsize: float
        Text size scaling factor for labels, titles and lines. If None it will be autoscaled based
        on figsize.
    linewidth: int
        Line width throughout. If None it will be autoscaled based on figsize.
    markersize: int
        Markersize throughout. If None it will be autoscaled based on figsize.
    ridgeplot_alpha: float
        Transparency for ridgeplot fill.  If 0, border is colored by model, otherwise
        a black outline is used.
    ridgeplot_overlap: float
        Overlap height for ridgeplots.
    ridgeplot_kind: string
        By default ("auto") continuous variables are plotted using KDEs and discrete ones using
        histograms. To override this use "hist" to plot histograms and "density" for KDEs
    ridgeplot_quantiles: list
        Quantiles in ascending order used to segment the KDE. Use [.25, .5, .75] for quartiles.
        Defaults to None.
    figsize: tuple
        Figure size. If None it will be defined automatically.
    ax: axes, optional
        Matplotlib axes or bokeh figures.
    backend: str, optional
        Select plotting backend {"matplotlib","bokeh"}. Default "matplotlib".
    backend_config: dict, optional
        Currently specifies the bounds to use for bokeh axes. Defaults to value set in rcParams.
    backend_kwargs: bool, optional
        These are kwargs specific to the backend being used. For additional documentation
        check the plotting method of the backend.
    show: bool, optional
        Call backend show function.
    credible_interval: float, optional
        deprecated: Please see hpd_interval

    Returns
    -------
    gridspec: matplotlib GridSpec or bokeh figures

    Examples
    --------
    Forestpĺot

    .. plot::
        :context: close-figs

        >>> import arviz as az
        >>> non_centered_data = az.load_arviz_data('non_centered_eight')
        >>> axes = az.plot_forest(non_centered_data,
        >>>                            kind='forestplot',
        >>>                            var_names=["^the"],
        >>>                            filter_vars="regex",
        >>>                            combined=True,
        >>>                            ridgeplot_overlap=3,
        >>>                            figsize=(9, 7))
        >>> axes[0].set_title('Estimated theta for 8 schools model')

    Ridgeplot

    .. plot::
        :context: close-figs

        >>> axes = az.plot_forest(non_centered_data,
        >>>                            kind='ridgeplot',
        >>>                            var_names=['theta'],
        >>>                            combined=True,
        >>>                            ridgeplot_overlap=3,
        >>>                            colors='white',
        >>>                            figsize=(9, 7))
        >>> axes[0].set_title('Estimated theta for 8 schools model')
    """
    if credible_interval:
        hpd_interval = credible_interval_warning(credible_interval, hpd_interval)

    if not isinstance(data, (list, tuple)):
        data = [data]

    if coords is None:
        coords = {}

    datasets = [convert_to_dataset(datum) for datum in reversed(data)]
    if transform is not None:
        datasets = [transform(dataset) for dataset in datasets]
    datasets = get_coords(
        datasets, list(reversed(coords)) if isinstance(coords, (list, tuple)) else coords
    )

    var_names = _var_names(var_names, datasets, filter_vars)

    ncols, width_ratios = 1, [3]

    if ess:
        ncols += 1
        width_ratios.append(1)

    if r_hat:
        ncols += 1
        width_ratios.append(1)

    if hpd_interval is None:
        hpd_interval = rcParams["stats.hpd_interval"]
    else:
        if not 1 >= hpd_interval > 0:
            raise ValueError("The value of credible_interval should be in the interval (0, 1]")

    plot_forest_kwargs = dict(
        ax=ax,
        datasets=datasets,
        var_names=var_names,
        model_names=model_names,
        combined=combined,
        colors=colors,
        figsize=figsize,
        width_ratios=width_ratios,
        linewidth=linewidth,
        markersize=markersize,
        kind=kind,
        ncols=ncols,
        hpd_interval=hpd_interval,
        quartiles=quartiles,
        rope=rope,
        ridgeplot_overlap=ridgeplot_overlap,
        ridgeplot_alpha=ridgeplot_alpha,
        ridgeplot_kind=ridgeplot_kind,
        ridgeplot_quantiles=ridgeplot_quantiles,
        textsize=textsize,
        ess=ess,
        r_hat=r_hat,
        backend_kwargs=backend_kwargs,
        show=show,
    )

    if backend is None:
        backend = rcParams["plot.backend"]
    backend = backend.lower()

    if backend == "bokeh":
        plot_forest_kwargs.update(backend_config=backend_config)

    # TODO: Add backend kwargs
    plot = get_plotting_function("plot_forest", "forestplot", backend)
    axes = plot(**plot_forest_kwargs)
    return axes
