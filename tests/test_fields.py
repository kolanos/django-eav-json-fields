"""Unit tests for custom Django model fields."""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from eav_fields.eav import EAVBoolean, EAVDecimal, EAVInteger, EAVSchema, EAVString
from eav_fields.fields import EAVField


class _StaticSchema(EAVSchema):
    name = EAVString()
    enabled = EAVBoolean(default=False, required=False)


class _SchemaA(EAVSchema):
    count = EAVInteger(min_value=0)


class _SchemaB(EAVSchema):
    rate = EAVDecimal(min_value=0, max_value=1)


class TestEAVFieldStaticSchema:
    """EAVField with a single static schema."""

    def test_accepts_valid_data(self) -> None:
        field = EAVField(schema=_StaticSchema)
        field.validate({"name": "test", "enabled": True}, model_instance=None)

    def test_rejects_invalid_data(self) -> None:
        field = EAVField(schema=_StaticSchema)
        with pytest.raises(ValidationError):
            field.validate({"name": 123}, model_instance=None)

    def test_rejects_unknown_keys(self) -> None:
        field = EAVField(schema=_StaticSchema)
        with pytest.raises(ValidationError) as exc_info:
            field.validate({"name": "test", "extra": "bad"}, model_instance=None)
        err = exc_info.value
        assert hasattr(err, "message_dict")
        assert "extra" in err.message_dict

    def test_accepts_empty_dict_with_optional_fields(self) -> None:
        class OptionalSchema(EAVSchema):
            note = EAVString(required=False)

        field = EAVField(schema=OptionalSchema)
        field.validate({}, model_instance=None)


class TestEAVFieldPolymorphicSchema:
    """EAVField with schema_map + schema_key_field."""

    def _make_instance(self, config_type: str) -> SimpleNamespace:
        return SimpleNamespace(config_type=config_type)

    def test_validates_against_correct_schema(self) -> None:
        field = EAVField(
            schema_map={"a": _SchemaA, "b": _SchemaB},
            schema_key_field="config_type",
        )
        instance = self._make_instance("a")
        field.validate({"count": 5}, model_instance=instance)

    def test_rejects_wrong_data_for_schema(self) -> None:
        field = EAVField(
            schema_map={"a": _SchemaA, "b": _SchemaB},
            schema_key_field="config_type",
        )
        instance = self._make_instance("a")
        with pytest.raises(ValidationError):
            field.validate({"count": -1}, model_instance=instance)

    def test_unknown_key_skips_validation(self) -> None:
        field = EAVField(
            schema_map={"a": _SchemaA},
            schema_key_field="config_type",
        )
        instance = self._make_instance("unknown_type")
        # Should NOT raise -- unknown schema key means no validation
        field.validate({"anything": "goes"}, model_instance=instance)

    def test_none_key_field_skips_validation(self) -> None:
        field = EAVField(
            schema_map={"a": _SchemaA},
            schema_key_field="config_type",
        )
        instance = SimpleNamespace(config_type=None)
        field.validate({"anything": "goes"}, model_instance=instance)


class TestEAVFieldInit:
    def test_rejects_both_schema_and_schema_map(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            EAVField(schema=_StaticSchema, schema_map={"a": _SchemaA})

    def test_rejects_schema_map_without_key_field(self) -> None:
        with pytest.raises(ValueError, match="schema_key_field"):
            EAVField(schema_map={"a": _SchemaA})


class TestEAVFieldDeconstruct:
    def test_static_schema_deconstruct(self) -> None:
        field = EAVField(schema=_StaticSchema)
        _name, _path, _args, kwargs = field.deconstruct()
        assert "schema" in kwargs
        assert kwargs["schema"] == f"{_StaticSchema.__module__}.{_StaticSchema.__qualname__}"

    def test_polymorphic_schema_deconstruct(self) -> None:
        field = EAVField(
            schema_map={"a": _SchemaA, "b": _SchemaB},
            schema_key_field="config_type",
        )
        _name, _path, _args, kwargs = field.deconstruct()
        assert "schema_map" in kwargs
        assert kwargs["schema_key_field"] == "config_type"
        assert kwargs["schema_map"]["a"] == f"{_SchemaA.__module__}.{_SchemaA.__qualname__}"
        assert kwargs["schema_map"]["b"] == f"{_SchemaB.__module__}.{_SchemaB.__qualname__}"

    def test_roundtrip(self) -> None:
        """deconstruct values can reconstruct an identical field via string paths."""
        original = EAVField(
            schema_map={"a": _SchemaA, "b": _SchemaB},
            schema_key_field="config_type",
        )
        _name, _path, args, kwargs = original.deconstruct()

        # Reconstruct from string paths (as Django migrations would)
        reconstructed = EAVField(*args, **kwargs)
        assert reconstructed.schema_key_field == "config_type"
        assert reconstructed.schema_map is not None
        assert "a" in reconstructed.schema_map
        assert "b" in reconstructed.schema_map

    def test_lazy_import_from_string_path(self) -> None:
        """EAVField accepts string dotted paths and resolves them lazily."""
        path = f"{_StaticSchema.__module__}.{_StaticSchema.__qualname__}"
        field = EAVField(schema=path)
        # Resolve via validation
        field.validate({"name": "test"}, model_instance=None)

    def test_no_schema_params_excluded(self) -> None:
        field = EAVField()
        _name, _path, _args, kwargs = field.deconstruct()
        assert "schema" not in kwargs
        assert "schema_map" not in kwargs
        assert "schema_key_field" not in kwargs
