"""
General utilities
"""


def _var_names(var_name):
    """Handles var_name input across arviz

    Parameters
    ----------
    var_name: str or iter

    Returns
    -------
    var_name: tuple
    """
    if var_name is None:
        return None

    elif isinstance(var_name, str):
        return (var_name,)

    else:
        return tuple(var_name)
