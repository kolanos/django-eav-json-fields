"""Custom Django model fields with EAV schema validation."""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from django.db import models

if TYPE_CHECKING:
    from django.forms import Field as FormField

    from .eav import EAVSchema


def _resolve_schema_class(ref: type[EAVSchema] | str) -> type[EAVSchema]:
    """Resolve a schema class from either a direct reference or dotted path."""
    if isinstance(ref, str):
        module_path, _, class_name = ref.rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    return ref


def _schema_to_path(schema: type[EAVSchema] | str) -> str:
    """Convert a schema class to its dotted import path string."""
    if isinstance(schema, str):
        return schema
    return f"{schema.__module__}.{schema.__qualname__}"


class EAVField(models.JSONField):
    """JSONField with EAV schema validation.

    Validates during ``full_clean()`` that the JSON dict conforms to an
    :class:`~eav_fields.eav.EAVSchema` definition.  Storage remains plain JSONB.

    Supports two modes:

    **Static schema** -- single schema for all instances::

        config = EAVField(schema=MyConfigSchema)

    **Polymorphic schema** -- schema selected by a sibling model field::

        config = EAVField(
            schema_map={"type_a": SchemaA, "type_b": SchemaB},
            schema_key_field="config_type",
        )

    Schema references can be either class objects or dotted import path
    strings (for migration serialization).
    """

    def __init__(
        self,
        *args: Any,
        schema: type[EAVSchema] | str | None = None,
        schema_map: Mapping[str, type[EAVSchema] | str] | None = None,
        schema_key_field: str | None = None,
        **kwargs: Any,
    ) -> None:
        if schema and schema_map:
            msg = "Specify either 'schema' or 'schema_map', not both."
            raise ValueError(msg)
        if schema_map and not schema_key_field:
            msg = "'schema_key_field' is required when using 'schema_map'."
            raise ValueError(msg)

        self.schema = schema
        self.schema_map = schema_map
        self.schema_key_field = schema_key_field

        kwargs.setdefault("default", dict)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    def _resolve_schema(self, model_instance: Any) -> type[EAVSchema] | None:
        """Determine which EAVSchema applies for the given model instance."""
        if self.schema is not None:
            return _resolve_schema_class(self.schema)

        if self.schema_map is not None and self.schema_key_field is not None:
            key_value = getattr(model_instance, self.schema_key_field, None)
            if key_value is None:
                return None
            schema_ref = self.schema_map.get(key_value)
            if schema_ref is None:
                return None
            return _resolve_schema_class(schema_ref)

        return None

    def validate(self, value: Any, model_instance: Any) -> None:
        """Run parent JSON validation then delegate to EAV schema."""
        super().validate(value, model_instance)
        if not isinstance(value, dict):
            return

        schema_cls = self._resolve_schema(model_instance)
        if schema_cls is None:
            return

        # EAVSchema.validate raises Django ValidationError with message_dict
        schema_cls.validate(value)

    def formfield(
        self,
        **kwargs: Any,
    ) -> FormField | None:
        """Return a form field with EAVWidget for Django admin."""
        from .widgets import EAVWidget

        widget = EAVWidget(
            schema=self.schema,
            schema_map=self.schema_map,
            schema_key_field=self.schema_key_field,
        )
        kwargs["widget"] = widget
        return super().formfield(**kwargs)

    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()

        if self.schema is not None:
            kwargs["schema"] = _schema_to_path(self.schema)
        if self.schema_map is not None:
            kwargs["schema_map"] = {k: _schema_to_path(v) for k, v in self.schema_map.items()}
        if self.schema_key_field is not None:
            kwargs["schema_key_field"] = self.schema_key_field

        return name, path, args, kwargs
