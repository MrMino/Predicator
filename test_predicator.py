import pytest
from predicator import Rule, import_rules
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


class TestRule:
    @pytest.fixture
    def truism(self):
        return CallableProbe(True)

    def test_must_be_given_a_callable(self):
        with pytest.raises(AssertionError):
            Rule(None)

    def test_calls_given_callable(self, truism):
        rule = Rule(truism)
        rule()
        assert truism.called, (
            "Rule objects should call the given callable."
        )

    def test_returns_value_from_call(self):
        expected = True
        rule = Rule(lambda: expected)
        returned = rule()

        assert returned == expected, (
            "Call to a Rule object should return the value from given callable."
        )

    def test_callable_must_return_boolean(self):
        with pytest.raises(AssertionError):
            rule = Rule(lambda: "not a boolean")
            rule()

    def test_requires_is_a_tuple(self, truism):
        assert isinstance(Rule(truism).requires, tuple), (
            "Rule.requires should return a tuple."
        )

    def test_requires_returns_names_of_arguments_for_lambda(self):
        rule = Rule(lambda a, b, c, d: False)
        assert rule.requires == ('a', 'b', 'c', 'd'), (
            "Rule.requires should return the names of given lambda arguments."
        )

    def test_requires_returns_names_of_arguments_for_callable_objects(self):
        class CallableClass:
            def __call__(a, b, c, d):
                pass

        rule = Rule(CallableClass())
        assert rule.requires == ('a', 'b', 'c', 'd'), (
            "Rule.requires should return the names of given callable object "
            "arguments."
        )

    def test_requires_returns_names_of_arguments_for_functions(self):
        def func(a, b, c, d):
            pass

        rule = Rule(func)
        assert rule.requires == ('a', 'b', 'c', 'd'), (
            "Rule.requires should return the names of given function arguments."
        )

    def test_requires_handles_kwonlyargs_correctly(self):
        def func(a, b, *, c=None, d=123):
            pass

        rule = Rule(func)
        assert rule.requires == ('a', 'b', 'c', 'd'), (
            "Rule.requires should return the names of given function "
            "arguments, even if some are keyword-only."
        )

    def test_call_forwards_arguments_to_func(self):
        def func(a, b, c, d):
            assert a == 1 and b == 2 and c == 3 and d == 4
            return True

        rule = Rule(func)
        try:
            rule(1, 2, 3, 4)
        except TypeError:
            pytest.fail(
                "Rule should pass its arguments to the underlying callable."
            )

    def test_name_returns_name_of_function(self):
        def example_rule_name():
            pass
        assert Rule(example_rule_name).name == "example_rule_name", (
            "If Rule was instantiated with a function, Rule.name should return "
            "the name of the underlying function."
        )

    def test_name_returns_name_of_class_if_given_a_non_function_callable(self):
        class MyClass:
            def __call__(self):
                pass
        assert Rule(MyClass()).name == 'MyClass', (
            "If Rule was instantiated with a non-function callable object, "
            "Rule.name should return the name of its class."
        )

    def test_forbids_usage_of_a_class_as_func(self):
        class MyClass:
            pass
        with pytest.raises(AssertionError):
            Rule(MyClass)


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
