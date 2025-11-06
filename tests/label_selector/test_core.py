from tools.label_selector.core import normalize, compile_node


def test_normalize_basic_eq():
    spec = {"match": {"key": "env", "op": "eq", "value": "prod"}}
    out = normalize(spec)
    assert out == spec  # already normalized


def test_normalize_in_notin_and_between_inclusive_bool():
    spec = {"match": {"key": "tier", "op": "in", "values": [1, 2, 3]}}
    assert normalize(spec) == spec

    spec2 = {"match": {"key": "tier", "op": "notin", "values": ["a", "b"]}}
    assert normalize(spec2) == spec2

    spec3 = {
        "match": {
            "key": "score",
            "op": "between",
            "range": {"low": 10, "high": 20, "inclusive": True},
        }
    }
    out3 = normalize(spec3)
    assert out3["match"]["range"]["inclusive"] == {"low": True, "high": True}


def test_compile_node_eq_and_missing_behavior():
    rule = {"match": {"key": "env", "op": "eq", "value": "prod"}}
    pred = compile_node(normalize(rule))
    assert pred({"env": "prod"}) is True
    assert pred({"env": "dev"}) is False
    assert pred({}) is False  # missing -> False for eq


def test_compile_node_comparators_and_any_all_not():
    spec = {
        "all": [
            {"match": {"key": "v", "op": "gte", "value": 10}},
            {"any": [
                {"match": {"key": "tag", "op": "eq", "value": "blue"}},
                {"not": {"match": {"key": "region", "op": "in", "values": ["cn"]}}},
            ]},
        ]
    }
    pred = compile_node(normalize(spec))
    assert pred({"v": 10, "tag": "blue", "region": "eu"}) is True
    assert pred({"v": 11, "region": "eu"}) is True  # second branch via NOT(in ["cn"])
    assert pred({"v": 9, "tag": "blue"}) is False  # fails gte
    assert pred({"v": 10, "region": "cn"}) is False  # any-branch false


def test_between_inclusive_exclusive_logic():
    # [10, 20)  => low inclusive, high exclusive
    spec = {
        "match": {
            "key": "x",
            "op": "between",
            "range": {"low": 10, "high": 20, "inclusive": {"low": True, "high": False}},
        }
    }
    pred = compile_node(normalize(spec))
    assert pred({"x": 10}) is True
    assert pred({"x": 19.999}) is True
    assert pred({"x": 20}) is False
    assert pred({"x": 9.999}) is False


def test_notbetween_is_inverse_of_between_for_present_values():
    between = {
        "match": {
            "key": "x",
            "op": "between",
            "range": {"low": 1, "high": 2, "inclusive": {"low": True, "high": True}},
        }
    }
    notbetween = {
        "match": {
            "key": "x",
            "op": "notbetween",
            "range": {"low": 1, "high": 2, "inclusive": {"low": True, "high": True}},
        }
    }
    p_between = compile_node(normalize(between))
    p_notbetween = compile_node(normalize(notbetween))
    assert p_between({"x": 1}) is True and p_notbetween({"x": 1}) is False
    assert p_between({"x": 1.5}) is True and p_notbetween({"x": 1.5}) is False
    assert p_between({"x": 3}) is False and p_notbetween({"x": 3}) is True
