"""
General utilities
"""


def _var_names(var_name):
    """Handles var_name input across arviz

    Parameters
    ----------
    var_name: str, list or None

    Returns
    -------
    var_name: list or None
    """
    if var_name is None:
        return None

    elif isinstance(var_name, str):
        return [var_name]

    else:
        return var_name
