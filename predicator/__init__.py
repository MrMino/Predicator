# Add a glossary: Rule, Recipe, Checklist, Input, Requirement, Ingredients
from typing import Callable, List, Union, Any, Optional, Set, Tuple
from importlib.abc import Loader

from inspect import getfullargspec, isclass, isfunction
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
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

    def __init__(self, func: Callable, *, name: str = None):
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
        self._supplied_name = name

    @property
    def requires(self) -> Tuple[str, ...]:
        """The list of inputs required by the rule (its arguments)."""
        argspec = getfullargspec(self._func)
        return tuple(argspec.args + argspec.kwonlyargs)

    @property
    def name(self) -> str:
        """Name of the rule.

        Name of the class of the given callable, or, if given
        a function, the name from the function's signature.

        Note
        ----
        Rule names are not unique, even if supplied by the signature of the
        callable.
        """
        return (self._supplied_name if self._supplied_name is not None
                else self._func.__name__ if isfunction(self._func)
                else self._func.__class__.__name__)

    @name.setter
    def name(self, new_name):
        self._supplied_name = new_name

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
    assert spec.loader is not None
    assert isinstance(spec.loader, Loader)

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


class Cookbook:
    """Dynamic list of rule inputs that are required for checks to be performed.

    Used to compute which recipes should be used and in what order, to satisfy
    requirements of every specified rule.

    A recipe may supply an intermediate input that will feed to other recipes.

    If two recipes exist for the same input type, only the first one in the
    list will be used.

    Attributes
    ----------
    rules : List[Rule]
        Rules for which the inputs should be computed.
    recipes: List[Recipes]
        Recipes which should be used to create the required inputs.
    required : Set[str]
        Names of inputs that are required by rules and used recipes.
    """

    def __init__(
        self,
        rules: Optional[List[Rule]] = None,
        recipes: Optional[List[Recipe]] = None
    ):
        if rules is None:
            rules = []
        if recipes is None:
            recipes = []
        self.rules = rules
        self.recipes = recipes

    def recipe_for(self, input_name: str) -> Recipe:
        """Get the recipe that will be used to generate the speicified input.

        Parameters
        ----------
        input_name
            Input that the returned recipe generates.

        Returns
        -------
        Recipe
            Callable that can generate the specified input.

        Raises
        ------
        ValueError
            If there's no recipe for the specified input in this cookbook.
        """
        for recipe in self.recipes:
            if recipe.name == input_name:
                return recipe
        else:
            raise ValueError(f"Recipe for {input_name} is not in the cookbook.")

    def missing_inputs(self, *primary_inputs: str) -> Set[str]:
        """For given inputs, calculate inputs missing to satisfy requirements.

        Note
        ----
        This does not consider duplicate rules - only the first recipe for each
        input is considered.
        If an input is specified as primary, the recipe for it is ignored.

        Parameters
        ----------
        *primary_inputs
            Input types that are provided beforehand, i.e. do not require
            generation by any recipe. These inputs will be removed from the
            returned set.

        Returns
        -------
        Set[str]
            List of inputs that are required to satisfy the rules (directly or
            via intermediate recipes), yet there are no known recipes for them
            in the cookbook.

        Raises
        ------
        ValueError
            If there's a cycle in the recipes that are used to satisfy rules
            requirements.
        """
        recipe_graph = self._generate_used_recipes_graph(primary_inputs)
        self._ensure_no_recipe_cycles(recipe_graph, primary_inputs)
        required_for_recipes: Set[str] = set()
        for recipe in self.recipes:
            if recipe.name in self.required:
                required_for_recipes.update(recipe.requires)
        return (self.required
                - set(recipe.name for recipe in self.recipes)).union(
                    required_for_recipes
                )

    # This one is a bitch.
    def _ensure_no_recipe_cycles(self, primary_inputs: Tuple[str, ...]):
        provided: Set[str] = set(primary_inputs)
        required = self.required - provided

        for checked_input in required:
            used_recipes = set()
            next_recipes = {self.recipe_for(checked_input)}

            while True:
                next_recipes = self._get_next(next_recipes)


    @property
    def required(self) -> Set[str]:
        required_inputs: Set[str] = set()
        for rule in self.rules:
            required_inputs.update(rule.requires)
        return required_inputs
