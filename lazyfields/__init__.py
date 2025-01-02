__version__ = "0.1.0"
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
__all__ = [
    "lazy",
    "lazyfield",
    "asynclazyfield",
    "setlazy",
    "dellazy",
    "is_initialized",
    "force_set",
    "force_del",
    "later",
    "asynclater",
    "make_lazy_descriptor",
    "getname",
]

from ._lazyfields import (
    asynclater,
    asynclazyfield,
    dellazy,
    force_del,
    force_set,
    getname,
    is_initialized,
    later,
    lazy,
    lazyfield,
    make_lazy_descriptor,
    setlazy,
)
