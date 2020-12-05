from inspect import getfullargspec, isclass, isfunction
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
from typing import Callable, List, Union, Any, Optional
from types import ModuleType


__version__ = '0.0.1'


class Recipe:
    """A callable that computes a value of an input of a given name.

    Wraps around a callable, and uses its signature as a specification of what
    type of input it produces, and what inputs it needs to operate.

    It works in a similar way to pytest fixtures.

    The name of the callable will be interpretted as the name of the input type
    that it produces.
    The names of its arguments will be interpretted as the list of names of
    required input types.

    Attributes
    ----------
    requires
    name
    """

    def __init__(self, func: Callable):
        """Initialize Recipe object, perform basic checks.

        Parameters
        ----------
        func
            A callable which will be used to produce the value.

            This function's arguments will be considered its "inputs", i.e. the
            objects required for the calculation it performs.

        Raises
        ------
        AssertionError
            If ``func`` is a class or not a callable.
        """
        assert callable(func), f"{repr(func)} is not callable."
        assert not isclass(func), f"{repr(func)} is a class."
        self._func = func

    @property
    def requires(self) -> List[str]:
        """The list of inputs required by the rule (its arguments)."""
        argspec = getfullargspec(self._func)
        return tuple(argspec.args + argspec.kwonlyargs)

    # XXX: Rule names are not unique!
    @property
    def name(self) -> str:
        """Name of the rule.

        Name of the class of the given callable, or, if given
        a function, the name from the function's signature.
        """
        return (self._func.__name__ if isfunction(self._func)
                else self._func.__class__.__name__)

    def __call__(self, *args, **kwargs) -> Any:
        """Use the recipe.

        Passes all of the given arguments to the underlying function.

        Parameters
        ----------
        *args
            Positional arguments to pass to the recipe function.
        **kwargs
            Keyword arguments to pass to the recipe function.

        Returns
        -------
        Any
            Recipe output, i.e. the value returned by the underlying function.

        """
        return self._func(*args, **kwargs)


class Rule(Recipe):
    """A callable that computes a value of a logic statement.

    Objects of this class provide a streamlined way of usage of predicate
    functions by other components of this module. It is meant to provide an
    abstraction over inspection of the given callable.

    Attributes
    ----------
    requires
    name
    """

    def __call__(self, *args, **kwargs) -> bool:
        """Perform the check on the inputs.

        Passes all of the given arguments to the underlying function. Checks
        whether the resulting value is a boolean, and returns it.

        Parameters
        ----------
        *args
            Positional arguments to pass to the predicate function.
        **kwargs
            Keyword arguments to pass to the predicate function.

        Returns
        -------
        bool
            Value returned by the predicate.

        Raises
        ------
        AssertionError
            If the predicate returned a value that is not an instance of bool.
        """

        verdict = super().__call__(*args, **kwargs)
        assert isinstance(verdict, bool), (
            f"{repr(self._func)} returned a non-boolean: {repr(verdict)}."
        )
        return verdict


def import_rules(rulebook_path: Union[str, Path]) -> List[Rule]:
    """Return list of rules as defined in a module specified by a path.

    Dynamically Imports the specified module, finds all of the predicates in
    it, wraps each into a ``Rule`` object, and returns a list of them.

    A module member is considered a rule if:
        - It is a callble.
        - It is not a class.
        - It has been defined inside the specified module.

    Paramters
    ---------
    rulebook_path
        Path to the python module to read rules from.

    Returns
    -------
    List[Rule]
        List of rules imported from the specified module.

    See Also
    --------
    is_rule : Used to check if the module member should be used as a rule.
    """
    rulebook_path = Path(rulebook_path)

    spec = spec_from_file_location(rulebook_path.stem, rulebook_path.absolute())
    rulebook = module_from_spec(spec)
    spec.loader.exec_module(rulebook)

    members = [getattr(rulebook, name) for name in dir(rulebook)]
    rules = [Rule(member) for member in members if is_rule(member, rulebook)]

    return rules


def is_rule(member: Any, rulebook: ModuleType) -> bool:
    """Return True if a given module member should be considered a rule."""
    return (
        callable(member)
        and member.__module__ == rulebook.__name__
        and not isclass(member)
    )
