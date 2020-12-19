import pytest
from predicator import Recipe, Rule, import_rules, is_rule, Cookbook
from textwrap import dedent


class CallableProbe:
    def __init__(self, return_value=True):
        self.called = False
        self.return_value = return_value
        self.args = self.kwargs = None

    def __call__(self, *args, **kwargs):
        self.called = True
        self.args = args
        self.kwargs = kwargs
        return self.return_value

    def __bool__(self):
        return self.called


class TestRecipe:
    class_under_test = Recipe

    @pytest.fixture
    def truism(self):
        return CallableProbe(True)

    def test_must_be_given_a_callable(self):
        with pytest.raises(AssertionError):
            self.class_under_test(None)

    def test_calls_given_callable(self, truism):
        recipe = self.class_under_test(truism)
        recipe()
        assert truism.called, (
            "Recipe objects should call the given callable."
        )

    def test_returns_value_from_call(self):
        expected = True
        recipe = self.class_under_test(lambda: expected)
        returned = recipe()

        assert returned == expected, (
            "Call to a Recipe object should return the value from given "
            "callable."
        )

    def test_requires_is_a_tuple(self, truism):
        assert isinstance(self.class_under_test(truism).requires, tuple), (
            "Recipe.requires should return a tuple."
        )

    def test_requires_returns_names_of_arguments_for_lambda(self):
        recipe = self.class_under_test(lambda a, b, c, d: False)
        assert recipe.requires == ('a', 'b', 'c', 'd'), (
            "Recipe.requires should return the names of given lambda arguments."
        )

    def test_requires_returns_names_of_arguments_for_callable_objects(self):
        class CallableClass:
            def __call__(a, b, c, d):
                pass

        recipe = self.class_under_test(CallableClass())
        assert recipe.requires == ('a', 'b', 'c', 'd'), (
            "Recipe.requires should return the names of given callable object "
            "arguments."
        )

    def test_requires_returns_names_of_arguments_for_functions(self):
        def func(a, b, c, d):
            pass

        recipe = self.class_under_test(func)
        assert recipe.requires == ('a', 'b', 'c', 'd'), (
            "Recipe.requires should return the names of given function "
            "arguments."
        )

    def test_requires_handles_kwonlyargs_correctly(self):
        def func(a, b, *, c=None, d=123):
            pass

        recipe = self.class_under_test(func)
        assert recipe.requires == ('a', 'b', 'c', 'd'), (
            "Recipe.requires should return the names of given function "
            "arguments, even if some are keyword-only."
        )

    def test_call_forwards_arguments_to_func(self):
        def func(a, b, c, d):
            assert a == 1 and b == 2 and c == 3 and d == 4
            return True

        recipe = self.class_under_test(func)
        try:
            recipe(1, 2, 3, 4)
        except TypeError:
            pytest.fail(
                "Recipe should pass its arguments to the underlying callable."
            )

    def test_name_returns_name_of_function(self):
        def example_name():
            pass

        assert self.class_under_test(example_name).name == "example_name", (
            "If Recipe was instantiated with a function, Recipe.name should "
            "return the name of the underlying function."
        )

    def test_name_returns_name_of_class_if_given_a_non_function_callable(self):
        class MyClass:
            def __call__(self):
                pass
        assert self.class_under_test(MyClass()).name == 'MyClass', (
            "If Recipe was instantiated with a non-function callable object, "
            "Recipe.name should return the name of its class."
        )

    def test_forbids_usage_of_a_class_as_func(self):
        class MyClass:
            pass
        with pytest.raises(AssertionError):
            self.class_under_test(MyClass)

    def test_name_is_settable(self):
        try:
            self.class_under_test(lambda: None).name = "different name"
        except AttributeError:
            pytest.fail("Recipe.name attribute should be settable.")

    def test_gives_new_name_after_name_is_set(self):
        new_name = "different_name"
        recipe = self.class_under_test(lambda: None)
        recipe.name = new_name
        assert recipe.name == new_name, "Newly set name should be memorized."

    def test_init_takes_name_argument(self):
        try:
            self.class_under_test(lambda: None, name="supplied name")
        except TypeError:
            pytest.fail("Recipe.__init__() should take a 'name' argument.")

    def test_init_name_argument_is_keyword_only(self):
        with pytest.raises(TypeError):
            self.class_under_test(lambda: None, "name goes here")

    def test_gives_name_from_init_argument(self):
        name = "supplied name"
        assert self.class_under_test(lambda: None, name=name).name == name, (
            "Recipe.name should be the name supplied to Recipe.__init__()."
        )


class TestRule(TestRecipe):
    class_under_test = Rule

    def test_callable_must_return_boolean(self):
        with pytest.raises(AssertionError):
            rule = self.class_under_test(lambda: "not a boolean")
            rule()


class TestImportRules:
    @pytest.fixture
    def module_with_rules(self, tmp_path):
        module_code = dedent("""
            def my_rule(a, b, c):
                return False

            def other_rule():
                return True
            """)
        module_path = tmp_path/"rules.py"
        module_path.write_text(module_code)

        return module_path

    def test_returns_rule_objects(self, module_with_rules):
        rules = import_rules(module_with_rules)
        assert all(isinstance(item, Rule) for item in rules), (
            "import_rules should return a collection of Rule objects."
        )

    def test_returns_rule_for_each_func_in_rule_module(self, module_with_rules):
        rules = import_rules(module_with_rules)
        assert len(rules) == 2, (
            "import_rules should return a Rule object for each function "
            "defined in the specified file."
        )

    def test_returns_rules_with_funcs_from_rule_module(self, module_with_rules):
        rules = import_rules(module_with_rules)
        assert (rules[0].name == 'my_rule' and rules[1].name == 'other_rule'), (
            "import_rules should return Rule objects with func set to "
            "functions defined in the specified file."
        )

    @pytest.fixture
    def noisy_module(self, module_with_rules):
        additional_code = dedent("""
            x = "a variable"

            # Some callables that shouldn't be considered rules
            from functools import reduce
            from itertools import chain

            not_a_rule = reduce
        """)
        with open(module_with_rules, 'a') as f:
            f.write(additional_code)
        return module_with_rules

    def test_excludes_callables_defined_outside(self, noisy_module):
        rules = import_rules(noisy_module)
        assert len(rules) == 2, (
            "import_rules should omit callables that were defined outside of "
            "the specified module."
        )

    @pytest.fixture
    def classes_module(self, tmp_path):
        module_code = dedent("""
            class RuleClass:
                def __call__(self):
                    return False
            """)
        module_path = tmp_path/"rules.py"
        module_path.write_text(module_code)

        return module_path

    def test_excludes_classes(self, classes_module):
        rules = import_rules(classes_module)
        assert len(rules) == 0, (
            "Classes should not be considered rules."
        )

    @pytest.fixture
    def object_module(self, classes_module):
        additional_code = dedent("""
            rule_obj = RuleClass()
        """)
        with open(classes_module, 'a') as f:
            f.write(additional_code)
        return classes_module

    def test_includes_callable_objects(self, object_module):
        rules = import_rules(object_module)
        assert len(rules) == 1, (
            "Instantiated callable objects should be considered rules too."
        )


class TestIsRule:
    @pytest.fixture
    def this_module(self):
        return __import__(self.__module__)

    def test_function_is_rule(self, this_module):
        def func():
            pass
        assert is_rule(func, this_module)

    def test_lambda_is_rule(self, this_module):
        assert is_rule(lambda: None, this_module)

    class Callable:
        def __call__(self):
            pass

    def test_callable_object_is_rule(self, this_module):
        callable_obj = self.Callable()
        assert is_rule(callable_obj, this_module)

    def test_class_is_not_rule(self, this_module):
        assert not is_rule(self.Callable, this_module)


class TestCookbook:
    class_under_test = Cookbook

    def test_creation_without_params(self):
        try:
            self.class_under_test()
        except TypeError:
            pytest.fail(
                "Cookbook class should not require any parameters to be "
                "instantiated."
            )

    def test_has_rules_attribute(self):
        try:
            self.class_under_test().rules
        except AttributeError:
            pytest.fail("Cookbook object should have .rules attribute.")

    def test_without_initialization_rules_should_return_empty_list(self):
        assert self.class_under_test().rules == [], (
            "If initialized without any rules, Cookbook.rules should return an "
            "empty list."
        )

    def test_if_initialized_should_return_given_rules(self):
        rules = [Rule(lambda: None) for _ in range(5)]
        cookbook = self.class_under_test(rules=rules)
        assert cookbook.rules == rules, (
            "If rules list given to init, Cookbook.rules should return that "
            "list."
        )

    def test_has_recipes_attribute(self):
        try:
            self.class_under_test().recipes
        except AttributeError:
            pytest.fail("Cookbook object should have .recipes attribute.")

    def test_without_initialization_recipes_should_return_empty_list(self):
        assert self.class_under_test().recipes == [], (
            "If initialized without any rules, Cookbook.recipes should return "
            "an empty list."
        )

    def test_if_initialized_should_return_given_recipes(self):
        recipes = [Recipe(lambda: None) for _ in range(5)]
        cookbook = self.class_under_test(recipes=recipes)
        assert cookbook.recipes == recipes, (
            "If recipes list given to init, Cookbook.recipes should return "
            "that list."
        )

    def test_recipe_for_raises_value_error_if_no_recipe_found(self):
        input_name = "some_input"
        cookbook = self.class_under_test()
        with pytest.raises(ValueError):
            cookbook.recipe_for(input_name)

    def test_recipe_for_returns_added_recipe(self):
        def some_input():
            pass
        cookbook = self.class_under_test()
        recipe = Recipe(some_input)
        cookbook.recipes.append(recipe)

        assert cookbook.recipe_for(recipe.name) == recipe, (
            "Cookbook.recipe_for() should return a recipe for the specified "
            "input."
        )

    def test_recipe_for_returns_the_first_added_recipe_for_an_input(self):
        def some_input():
            pass
        cookbook = self.class_under_test()
        recipe = Recipe(some_input)
        recipe2 = Recipe(some_input)
        cookbook.recipes.append(recipe)
        cookbook.recipes.append(recipe2)

        assert cookbook.recipe_for(recipe.name) == recipe, (
            "If there are multiple recipes for the same input, "
            "Cookbook.recipe_for() should only return the first one."
        )

    def test_has_required_attribute(self):
        cookbook = self.class_under_test()
        try:
            cookbook.required
        except AttributeError:
            pytest.fail("Cookbook object should have .required attribute")

    def test_without_initialization_required_should_return_empty_set(self):
        assert self.class_under_test().required == set(), (
            "Without any recipes added Cookbook.required should return an "
            "empty list."
        )

    def test_rules_requirements_show_up_in_required(self):
        def rule(a, b):
            pass

        def another_rule(c, d):
            pass

        cookbook = self.class_under_test(rules=[Rule(rule), Rule(another_rule)])
        assert cookbook.required == {'a', 'b', 'c', 'd'}, (
            "Cookbook.required should contain inputs required by every added "
            "rule."
        )

    def test_missing_inputs_returns_empty_set_when_uninitialized(self):
        assert self.class_under_test().missing_inputs() == set(), (
            "With an uninitialized cookbook, missing_inputs() method should "
            "return an empty set."
        )

    def test_without_recipes_missing_inputs_returns_all_required_inputs(self):
        rules = [Rule(lambda a, b, c: None), Rule(lambda c, d, e: None)]
        cookbook = self.class_under_test(rules=rules)
        assert cookbook.missing_inputs() == {'a', 'b', 'c', 'd', 'e'}, (
            "Without any added recipes, the value returned by "
            "Cookbook.missing_inputs() should contain inputs required by every "
            "added rule."
        )

    def test_adding_a_recipe_for_input_removes_it_from_missing(self):
        rules = [Rule(lambda a, b, c: None), Rule(lambda c, d, e: None)]

        cookbook = self.class_under_test(rules=rules)
        cookbook.recipes.append(Recipe(lambda: None, name="c"))
        cookbook.recipes.append(Recipe(lambda: None, name="e"))

        assert cookbook.missing_inputs() == {'a', 'b', 'd'}, (
            "Adding a recipe for an input should remove it from the missing "
            "inputs."
        )

    def test_input_needed_by_an_used_recipe_is_present_in_missing(self):
        rules = [Rule(lambda a, b, c: None), Rule(lambda c, d, e: None)]

        cookbook = self.class_under_test(rules=rules)
        cookbook.recipes.append(Recipe(lambda x, y: None, name="c"))

        assert cookbook.missing_inputs() == {'a', 'b', 'd', 'e', 'x', 'y'}, (
            "Adding a recipe for an input should add its required inputs to "
            "the missing inputs, as long as the recipe is used."
        )

    def test_unused_recipes_inputs_are_not_put_into_missing(self):
        cookbook = self.class_under_test()
        cookbook.recipes.append(Recipe(lambda unnecessary: None))
        assert 'unnecessary' not in cookbook.missing_inputs(), (
            "If the input generated by a recipe is not used by any rule, "
            "absent of other recipes, the recipe inputs should not be put into "
            "missing_inputs()."
        )

    @pytest.mark.skip
    def test_inputs_of_transitive_recipes_are_put_into_missing(self):
        cookbook = self.class_under_test(rules=[Rule(lambda a: None)])
        cookbook.recipes.append(Recipe(lambda b: None, name='a'))
        cookbook.recipes.append(Recipe(lambda c: None, name='b'))
        assert cookbook.missing_inputs() == {'c'}, (
            "Requirements of recipes that generate indirectly required inputs "
            "should be taken into account when calling missing_inputs()."
        )

    def test_cycles_in_used_recipes_are_not_allowed(self):
        cookbook = self.class_under_test(rules=[Rule(lambda a: None)])
        cookbook.recipes.append(Recipe(lambda b: None, name='a'))
        cookbook.recipes.append(Recipe(lambda c: None, name='b'))
        cookbook.recipes.append(Recipe(lambda a: None, name='c'))
        with pytest.raises(ValueError):
            cookbook.missing_inputs()

    def test_cycles_in_unused_recipes_are_allowed(self):
        cookbook = self.class_under_test(rules=[Rule(lambda x: None)])
        cookbook.recipes.append(Recipe(lambda b: None, name='a'))
        cookbook.recipes.append(Recipe(lambda c: None, name='b'))
        cookbook.recipes.append(Recipe(lambda a: None, name='c'))
        try:
            cookbook.missing_inputs()
        except ValueError:
            pytest.fail(
                "When calling missin_inputs(), cycles in the recipes that are "
                "left unused should be allowed."
            )
