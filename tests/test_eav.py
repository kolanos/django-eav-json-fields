"""Unit tests for the EAV schema system."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from eav_fields.eav import (
    EAVAttribute,
    EAVBoolean,
    EAVDecimal,
    EAVFloat,
    EAVInteger,
    EAVSchema,
    EAVString,
)

# ---------------------------------------------------------------------------
# EAVString
# ---------------------------------------------------------------------------


class TestEAVString:
    def test_accepts_valid_string(self) -> None:
        attr = EAVString()
        attr.name = "name"
        assert attr.validate("hello") == "hello"

    def test_rejects_non_string(self) -> None:
        attr = EAVString()
        attr.name = "name"
        with pytest.raises(ValidationError, match="string"):
            attr.validate(42)

    def test_max_length_constraint(self) -> None:
        attr = EAVString(max_length=5)
        attr.name = "code"
        assert attr.validate("abcde") == "abcde"
        with pytest.raises(ValidationError, match="at most 5"):
            attr.validate("abcdef")

    def test_choices_constraint(self) -> None:
        attr = EAVString(choices=["a", "b", "c"])
        attr.name = "option"
        assert attr.validate("a") == "a"
        with pytest.raises(ValidationError, match="one of"):
            attr.validate("d")

    def test_required_none_raises(self) -> None:
        attr = EAVString(required=True)
        attr.name = "name"
        with pytest.raises(ValidationError, match="required"):
            attr.validate(None)

    def test_optional_none_returns_default(self) -> None:
        attr = EAVString(required=False, default="fallback")
        attr.name = "name"
        assert attr.validate(None) == "fallback"

    def test_optional_none_no_default_returns_none(self) -> None:
        attr = EAVString(required=False)
        attr.name = "name"
        assert attr.validate(None) is None


# ---------------------------------------------------------------------------
# EAVBoolean
# ---------------------------------------------------------------------------


class TestEAVBoolean:
    def test_accepts_true(self) -> None:
        attr = EAVBoolean()
        attr.name = "flag"
        assert attr.validate(True) is True

    def test_accepts_false(self) -> None:
        attr = EAVBoolean()
        attr.name = "flag"
        assert attr.validate(False) is False

    def test_rejects_int(self) -> None:
        attr = EAVBoolean()
        attr.name = "flag"
        with pytest.raises(ValidationError, match="boolean"):
            attr.validate(1)

    def test_rejects_string(self) -> None:
        attr = EAVBoolean()
        attr.name = "flag"
        with pytest.raises(ValidationError, match="boolean"):
            attr.validate("true")

    def test_optional_with_default(self) -> None:
        attr = EAVBoolean(required=False, default=False)
        attr.name = "flag"
        assert attr.validate(None) is False


# ---------------------------------------------------------------------------
# EAVInteger
# ---------------------------------------------------------------------------


class TestEAVInteger:
    def test_accepts_valid_int(self) -> None:
        attr = EAVInteger()
        attr.name = "count"
        assert attr.validate(42) == 42

    def test_rejects_bool(self) -> None:
        attr = EAVInteger()
        attr.name = "count"
        with pytest.raises(ValidationError, match="integer"):
            attr.validate(True)

    def test_rejects_float(self) -> None:
        attr = EAVInteger()
        attr.name = "count"
        with pytest.raises(ValidationError, match="integer"):
            attr.validate(3.14)

    def test_min_value(self) -> None:
        attr = EAVInteger(min_value=0)
        attr.name = "count"
        assert attr.validate(0) == 0
        with pytest.raises(ValidationError, match=">= 0"):
            attr.validate(-1)

    def test_max_value(self) -> None:
        attr = EAVInteger(max_value=100)
        attr.name = "count"
        assert attr.validate(100) == 100
        with pytest.raises(ValidationError, match="<= 100"):
            attr.validate(101)

    def test_choices(self) -> None:
        attr = EAVInteger(choices=[1, 2, 3])
        attr.name = "level"
        assert attr.validate(2) == 2
        with pytest.raises(ValidationError, match="one of"):
            attr.validate(4)


# ---------------------------------------------------------------------------
# EAVFloat
# ---------------------------------------------------------------------------


class TestEAVFloat:
    def test_accepts_float(self) -> None:
        attr = EAVFloat()
        attr.name = "rate"
        assert attr.validate(3.14) == 3.14

    def test_coerces_int_to_float(self) -> None:
        attr = EAVFloat()
        attr.name = "rate"
        result = attr.validate(5)
        assert result == 5.0
        assert isinstance(result, float)

    def test_rejects_bool(self) -> None:
        attr = EAVFloat()
        attr.name = "rate"
        with pytest.raises(ValidationError, match="number"):
            attr.validate(True)

    def test_rejects_string(self) -> None:
        attr = EAVFloat()
        attr.name = "rate"
        with pytest.raises(ValidationError, match="number"):
            attr.validate("3.14")

    def test_min_value(self) -> None:
        attr = EAVFloat(min_value=0.0)
        attr.name = "rate"
        with pytest.raises(ValidationError, match=">= 0"):
            attr.validate(-0.1)

    def test_max_value(self) -> None:
        attr = EAVFloat(max_value=1.0)
        attr.name = "rate"
        with pytest.raises(ValidationError, match="<= 1"):
            attr.validate(1.1)


# ---------------------------------------------------------------------------
# EAVDecimal
# ---------------------------------------------------------------------------


class TestEAVDecimal:
    def test_accepts_decimal(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        result = attr.validate(Decimal("0.065"))
        assert result == Decimal("0.065")

    def test_coerces_string_to_decimal(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        result = attr.validate("0.065")
        assert result == Decimal("0.065")
        assert isinstance(result, Decimal)

    def test_coerces_int_to_decimal(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        result = attr.validate(5)
        assert result == Decimal("5")

    def test_coerces_float_to_decimal(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        result = attr.validate(0.065)
        assert isinstance(result, Decimal)

    def test_rejects_bool(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        with pytest.raises(ValidationError, match="decimal"):
            attr.validate(True)

    def test_rejects_invalid_string(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        with pytest.raises(ValidationError, match="valid decimal"):
            attr.validate("not_a_number")

    def test_min_value(self) -> None:
        attr = EAVDecimal(min_value=0)
        attr.name = "rate"
        with pytest.raises(ValidationError, match=">= 0"):
            attr.validate(Decimal("-0.01"))

    def test_max_value(self) -> None:
        attr = EAVDecimal(max_value=1)
        attr.name = "rate"
        with pytest.raises(ValidationError, match="<= 1"):
            attr.validate(Decimal("1.01"))

    def test_decimal_places_constraint(self) -> None:
        attr = EAVDecimal(decimal_places=2)
        attr.name = "amount"
        assert attr.validate(Decimal("10.50")) == Decimal("10.50")
        with pytest.raises(ValidationError, match="decimal places"):
            attr.validate(Decimal("10.501"))

    def test_max_digits_constraint(self) -> None:
        attr = EAVDecimal(max_digits=5, decimal_places=2)
        attr.name = "amount"
        assert attr.validate(Decimal("999.99")) == Decimal("999.99")
        with pytest.raises(ValidationError, match="too many digits"):
            attr.validate(Decimal("10000.00"))

    def test_to_json_returns_string(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        assert attr.to_json(Decimal("0.06500")) == "0.06500"

    def test_to_json_none(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        assert attr.to_json(None) is None

    def test_from_json_returns_decimal(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        result = attr.from_json("0.06500")
        assert result == Decimal("0.06500")
        assert isinstance(result, Decimal)

    def test_roundtrip_preserves_precision(self) -> None:
        attr = EAVDecimal()
        attr.name = "rate"
        original = Decimal("0.06500")
        json_val = attr.to_json(original)
        restored = attr.from_json(json_val)
        assert original == restored
        assert str(original) == str(restored)


# ---------------------------------------------------------------------------
# EAVSchemaMeta
# ---------------------------------------------------------------------------


class TestEAVSchemaMeta:
    def test_collects_attributes(self) -> None:
        class MySchema(EAVSchema):
            name = EAVString()
            count = EAVInteger()

        attrs = MySchema.get_attributes()
        assert "name" in attrs
        assert "count" in attrs
        assert isinstance(attrs["name"], EAVString)
        assert isinstance(attrs["count"], EAVInteger)

    def test_sets_attribute_names(self) -> None:
        class MySchema(EAVSchema):
            name = EAVString()

        attrs = MySchema.get_attributes()
        assert attrs["name"].name == "name"

    def test_removes_from_class_namespace(self) -> None:
        class MySchema(EAVSchema):
            name = EAVString()

        # Attribute descriptors should not be on the class itself
        assert not isinstance(getattr(MySchema, "name", None), EAVAttribute)

    def test_inheritance(self) -> None:
        class Parent(EAVSchema):
            name = EAVString()

        class Child(Parent):
            count = EAVInteger()

        attrs = Child.get_attributes()
        assert "name" in attrs
        assert "count" in attrs

    def test_child_overrides_parent(self) -> None:
        class Parent(EAVSchema):
            name = EAVString(max_length=50)

        class Child(Parent):
            name = EAVString(max_length=100)

        attrs = Child.get_attributes()
        assert isinstance(attrs["name"], EAVString)
        assert attrs["name"].max_length == 100

    def test_parent_not_affected_by_child(self) -> None:
        class Parent(EAVSchema):
            name = EAVString(max_length=50)

        class Child(Parent):
            count = EAVInteger()

        parent_attrs = Parent.get_attributes()
        assert "count" not in parent_attrs


# ---------------------------------------------------------------------------
# EAVSchema
# ---------------------------------------------------------------------------


class TestEAVSchema:
    def test_validates_valid_data(self) -> None:
        class Config(EAVSchema):
            name = EAVString()
            enabled = EAVBoolean(default=False, required=False)

        result = Config.validate({"name": "test", "enabled": True})
        assert result == {"name": "test", "enabled": True}

    def test_validates_with_defaults(self) -> None:
        class Config(EAVSchema):
            name = EAVString()
            enabled = EAVBoolean(default=False, required=False)

        result = Config.validate({"name": "test"})
        assert result == {"name": "test", "enabled": False}

    def test_rejects_unknown_keys(self) -> None:
        class Config(EAVSchema):
            name = EAVString()

        with pytest.raises(ValidationError) as exc_info:
            Config.validate({"name": "test", "extra": "val"})

        err = exc_info.value
        assert hasattr(err, "message_dict")
        assert "extra" in err.message_dict

    def test_collects_multiple_errors(self) -> None:
        class Config(EAVSchema):
            name = EAVString()
            count = EAVInteger()

        with pytest.raises(ValidationError) as exc_info:
            Config.validate({"name": 123, "count": "bad"})

        err = exc_info.value
        assert hasattr(err, "message_dict")
        assert "name" in err.message_dict
        assert "count" in err.message_dict

    def test_cross_validation_hook(self) -> None:
        class Config(EAVSchema):
            min_val = EAVInteger()
            max_val = EAVInteger()

            @classmethod
            def validate_cross(cls, data: dict) -> None:
                if data.get("min_val", 0) >= data.get("max_val", 0):
                    raise ValidationError({"max_val": ["max_val must be > min_val."]})

        # Valid
        result = Config.validate({"min_val": 1, "max_val": 10})
        assert result == {"min_val": 1, "max_val": 10}

        # Invalid cross-validation
        with pytest.raises(ValidationError) as exc_info:
            Config.validate({"min_val": 10, "max_val": 5})
        err = exc_info.value
        assert hasattr(err, "message_dict")
        assert "max_val" in err.message_dict

    def test_none_data_treated_as_empty_dict(self) -> None:
        class Config(EAVSchema):
            name = EAVString(required=False, default="default")

        result = Config.validate(None)
        assert result == {"name": "default"}

    def test_non_dict_data_raises(self) -> None:
        class Config(EAVSchema):
            name = EAVString()

        with pytest.raises(ValidationError, match="dict"):
            Config.validate("not_a_dict")  # type: ignore[arg-type]

    def test_apply_defaults_fills_missing(self) -> None:
        class Config(EAVSchema):
            name = EAVString(required=False, default="unnamed")
            enabled = EAVBoolean(default=False, required=False)

        result = Config.apply_defaults({})
        assert result == {"name": "unnamed", "enabled": False}

    def test_apply_defaults_preserves_existing(self) -> None:
        class Config(EAVSchema):
            name = EAVString(required=False, default="unnamed")

        result = Config.apply_defaults({"name": "existing"})
        assert result == {"name": "existing"}

    def test_apply_defaults_none_input(self) -> None:
        class Config(EAVSchema):
            name = EAVString(required=False, default="unnamed")

        result = Config.apply_defaults(None)
        assert result == {"name": "unnamed"}

    def test_decimal_stored_as_string_in_result(self) -> None:
        class Config(EAVSchema):
            rate = EAVDecimal(required=False, default=Decimal("0.05"))

        result = Config.validate({"rate": "0.065"})
        # EAVDecimal.to_json stores as string
        assert result["rate"] == "0.065"

    def test_optional_attributes_omitted_when_none(self) -> None:
        class Config(EAVSchema):
            name = EAVString()
            note = EAVString(required=False)

        result = Config.validate({"name": "test"})
        assert "note" not in result

    def test_empty_schema_accepts_empty_dict(self) -> None:
        class Config(EAVSchema):
            pass

        result = Config.validate({})
        assert result == {}

    def test_empty_schema_rejects_unknown_keys(self) -> None:
        class Config(EAVSchema):
            pass

        with pytest.raises(ValidationError) as exc_info:
            Config.validate({"extra": "val"})
        err = exc_info.value
        assert hasattr(err, "message_dict")
        assert "extra" in err.message_dict
