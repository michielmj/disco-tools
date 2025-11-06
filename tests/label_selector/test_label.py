import pytest

from tools.label_selector.label import Label
from tools.label_selector.rule import Rule
from tools.label_selector.core import normalize, compile_node


def test_operator_and_function_forms_equivalence():
    # eq vs .eq
    r1 = Label("env") == "prod"
    r2 = Label("env").eq("prod")
    assert r1.to_dict() == r2.to_dict()

    # gt vs .gt
    r3 = Label("version") > 10
    r4 = Label("version").gt(10)
    assert r3.to_dict() == r4.to_dict()


def test_logical_composition_and_or_not_flattening():
    a = Label("a").eq(1)
    b = Label("b").eq(2)
    c = Label("c").eq(3)

    and_rule = a + b + c
    d = and_rule.to_dict()
    assert "all" in d and len(d["all"]) == 3  # flattened AND list

    or_rule = (a | b) | c
    e = or_rule.to_dict()
    assert "any" in e and len(e["any"]) == 3  # flattened OR list

    not_rule = ~a
    assert not_rule.to_dict() == {"not": a.to_dict()}


def test_yaml_roundtrip():
    rule = (Label("env").eq("prod") | Label("tag").eq("blue")) + Label("v").gte(10)
    s = rule.to_yaml()
    rule2 = Rule.from_yaml(s)
    # Compare normalized to be robust to order/shape
    assert normalize(rule.to_dict()) == normalize(rule2.to_dict())


def test_select_is_lazy_iterator_and_filters_correctly_fixed():
    # Match env=prod AND v>=2, OR tag=blue
    rule = (Label("env").eq("prod") + Label("v").gte(2)) | Label("tag").eq("blue")

    seen = []

    def gen():
        for i in range(6):
            seen.append(i)
            yield {
                "id": i,
                "env": "prod" if i % 2 == 0 else "dev",
                "v": i,
                "tag": "blue" if i == 5 else "none"
            }

    it = rule.select(gen())
    assert iter(it) is it

    first = next(it)
    # i=0 -> env=prod but v=0 < 2, no; i=1 dev; i=2 env=prod and v=2 -> yes
    assert first["id"] == 2
    # Ensure laziness: only items up to first match should have been produced
    assert seen == [0, 1, 2]

    rest = list(it)
    # Remaining matches: i=4 (prod & v>=2), i=5 (tag=blue)
    assert [m["id"] for m in rest] == [4, 5]
    # Generator must have been fully consumed
    assert seen == [0, 1, 2, 3, 4, 5]


def test_exists_and_missing_key_semantics():
    r_exists = Label("x").exists()
    pred = r_exists.compile()
    assert pred({"x": 1}) is True
    assert pred({}) is False


def test_missing_key_for_comparators_and_membership():
    # Missing key -> False for comparators
    assert (Label("y").gt(0).compile())({}) is False

    # `notin` with missing value behaves as True (sentinel not in set)
    assert (Label("y").notin([1, 2]).compile())({}) is True

    # `in` with missing value -> False
    assert (Label("y").isin([1, 2]).compile())({}) is False


def test_between_validation_and_logic():
    with pytest.raises(ValueError):
        Label("x").between()  # both None

    # Inclusive/exclusive checks
    r = Label("score").between(10, 20, inc_low=True, inc_high=False)
    p = r.compile()
    assert p({"score": 10})
    assert p({"score": 19.999})
    assert not p({"score": 20})


def test_primitive_validation_errors():
    class Obj: pass

    with pytest.raises(TypeError):
        Label("x").eq(Obj())

    with pytest.raises(TypeError):
        Label("x").isin([1, "a", Obj()])

    with pytest.raises(TypeError):
        Label("x").between(low=Obj(), high=2)


def test_rule_compile_and_to_yaml_from_yaml_roundtrip():
    r = (~(Label("region").notin(["eu", "us"]))) + Label("v").lte(5)
    s = r.to_yaml()
    r2 = Rule.from_yaml(s)
    p1 = r.compile()
    p2 = r2.compile()
    assert p1({"region": "eu", "v": 5})
    assert p2({"region": "eu", "v": 5})
    assert not p1({"region": "apac", "v": 5})
    assert not p2({"region": "apac", "v": 5})
