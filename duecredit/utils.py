# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the duecredit package for the
#   copyright and license terms.   Originates from datalad package distributed
#   under MIT license
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

import os
import logging
import sys
from functools import wraps
from six import string_types

lgr = logging.getLogger("duecredit.utils")

#
# Little helpers
#


def is_interactive():
    """Return True if all in/outs are tty"""
    # TODO: check on windows if hasattr check would work correctly and add value:
    #
    return sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty()



#
# Decorators
#

# Borrowed from pandas
# Copyright: 2011-2014, Lambda Foundry, Inc. and PyData Development Team
# Licese: BSD-3
def optional_args(decorator):
    """allows a decorator to take optional positional and keyword arguments.
        Assumes that taking a single, callable, positional argument means that
        it is decorating a function, i.e. something like this::

            @my_decorator
            def function(): pass

        Calls decorator with decorator(f, *args, **kwargs)"""

    @wraps(decorator)
    def wrapper(*args, **kwargs):
        def dec(f):
            return decorator(f, *args, **kwargs)

        is_decorating = not kwargs and len(args) == 1 and callable(args[0])
        if is_decorating:
            f = args[0]
            args = []
            return dec(f)
        else:
            return dec

    return wrapper


def never_fail(f):
    """Assure that function never fails -- all exceptions are caught"""
    @wraps(f)
    def wrapped_func(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            lgr.warning("DueCredit internal failure while running %s: %r. "
                        "Please report to developers at https://github.com/duecredit/duecredit/issues"
                        % (f, e))

    if os.environ.get('DUECREDIT_ALLOW_FAIL', False):
        return f
    else:
        return wrapped_func


def borrowdoc(cls, methodname=None, replace=None):
    """Return a decorator to borrow docstring from another `cls`.`methodname`

    Common use is to borrow a docstring from the class's method for an
    adapter function (e.g. sphere_searchlight borrows from Searchlight)

    Examples
    --------
    To borrow `__repr__` docstring from parent class `Mapper`, do::

       @borrowdoc(Mapper)
       def __repr__(self):
           ...

    Parameters
    ----------
    cls
      Usually a parent class
    methodname : None or str
      Name of the method from which to borrow.  If None, would use
      the same name as of the decorated method
    replace : None or str, optional
      If not None, then not entire docstring gets replaced but only the
      matching to "replace" value string
    """

    def _borrowdoc(method):
        """Decorator which assigns to the `method` docstring from another
        """
        if methodname is None:
            other_method = getattr(cls, method.__name__)
        else:
            other_method = getattr(cls, methodname)
        if hasattr(other_method, '__doc__'):
            if not replace:
                method.__doc__ = other_method.__doc__
            else:
                method.__doc__ = method.__doc__.replace(replace, other_method.__doc__)
        return method
    return _borrowdoc


#
# Context Managers
#


#
# Additional handlers
#
_sys_excepthook = sys.excepthook # Just in case we ever need original one

def setup_exceptionhook():
    """Overloads default sys.excepthook with our exceptionhook handler.

       If interactive, our exceptionhook handler will invoke
       pdb.post_mortem; if not interactive, then invokes default handler.
    """

    def _duecredit_pdb_excepthook(type, value, tb):

        if is_interactive():
            import traceback, pdb
            traceback.print_exception(type, value, tb)
            print
            pdb.post_mortem(tb)
        else:
            lgr.warn("We cannot setup exception hook since not in interactive mode")
            # we are in interactive mode or we don't have a tty-like
            # device, so we call the default hook
            #sys.__excepthook__(type, value, tb)
            _sys_excepthook(type, value, tb)

    sys.excepthook = _duecredit_pdb_excepthook

from distutils.version import StrictVersion, LooseVersion

# To depict an unknown version, which can't be compared by mistake etc
class UnknownVersion:
    """For internal use
    """

    def __str__(self):
        return "UNKNOWN"

    def __cmp__(self, other):
        if other is self:
            return 0
        raise TypeError("UNKNOWN version is not comparable")


class ExternalVersions(object):
    """Helper to figure out/use versions of the external modules.

    It maintains a dictionary of `distuil.version.StrictVersion`s to make
    comparisons easy.  If version string doesn't conform the StrictVersion
    LooseVersion will be used.  If version can't be deduced for the module,
    'None' is assigned
    """

    UNKNOWN = UnknownVersion()

    def __init__(self):
        self._versions = {}

    @classmethod
    def _deduce_version(klass, module):
        version = None
        for attr in ('__version__', 'version'):
            if hasattr(module, attr):
                version = getattr(module, attr)
                break

        if isinstance(version, tuple) or isinstance(version, list):
            #  Generate string representation
            version = ".".join(str(x) for x in version)

        if version:
            try:
                return StrictVersion(version)
            except ValueError:
                # let's then go with Loose one
                return LooseVersion(version)
        else:
            return klass.UNKNOWN

    def __getitem__(self, module):
        if not isinstance(module, string_types):
            modname = module.__name__
        else:
            modname = module
            module = None

        if modname not in self._versions:
            if module is None:
                if modname not in sys.modules:
                    try:
                        module = __import__(modname)
                    except ImportError:
                        return None
                else:
                    module = sys.modules[modname]

            self._versions[modname] = self._deduce_version(module)

        return self._versions.get(modname, self.UNKNOWN)

external_versions = ExternalVersions()
