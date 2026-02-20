"""EAV (Entity-Attribute-Value) schema system for validated JSONField data.

Provides a declarative DSL for defining expected keys, types, and constraints
on JSON dict values stored in Django JSONFields.  Storage remains plain JSONB
in PostgreSQL — the EAV layer adds validation, type coercion, and metadata.

Usage::

    class InstallmentConfig(EAVSchema):
        supports_variable_rate = EAVBoolean(default=False, help_text="Enable variable rate")
        variable_rate_index = EAVString(required=False, help_text="Index name")
        rate_floor = EAVDecimal(required=False, max_digits=7, decimal_places=5)

        @classmethod
        def validate_cross(cls, data: dict[str, Any]) -> None:
            if data.get("supports_variable_rate") and not data.get("variable_rate_index"):
                raise ValidationError({"variable_rate_index": ["Required."]})
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError

# ---------------------------------------------------------------------------
# EAV Attribute types
# ---------------------------------------------------------------------------


class EAVAttribute:
    """Base class for EAV attribute descriptors.

    Subclasses define a JSON-compatible type with validation and coercion.
    Instances are collected by :class:`EAVSchemaMeta` into a schema definition.
    """

    python_type: type
    json_type: str  # For documentation / widget hints

    def __init__(
        self,
        *,
        required: bool = True,
        default: Any = None,
        help_text: str = "",
        choices: list[Any] | None = None,
    ) -> None:
        self.name: str = ""  # Set by metaclass
        self.required = required
        self.default = default
        self.help_text = help_text
        self.choices = choices

    def validate(self, value: Any) -> Any:
        """Validate and coerce *value*, returning the cleaned value.

        Raises ``ValidationError`` with a list of error strings on failure.
        """
        if value is None:
            if self.required and self.default is None:
                raise ValidationError([f"{self.name} is required."])
            return self.default

        value = self._coerce(value)
        self._check_constraints(value)
        if self.choices is not None and value not in self.choices:
            allowed = ", ".join(repr(c) for c in self.choices)
            raise ValidationError([f"{self.name} must be one of: {allowed}."])
        return value

    def _coerce(self, value: Any) -> Any:
        """Coerce *value* to the attribute's Python type.

        Override in subclasses for type-specific coercion.
        """
        if not isinstance(value, self.python_type):
            raise ValidationError([f"{self.name} must be a {self.json_type}."])
        return value

    def _check_constraints(self, value: Any) -> None:
        """Check type-specific constraints beyond basic type checking.

        Override in subclasses (e.g., min_value/max_value for numerics).
        """

    def to_json(self, value: Any) -> Any:
        """Convert Python value to JSON-compatible representation."""
        return value

    def from_json(self, value: Any) -> Any:
        """Convert JSON value back to Python representation."""
        return self._coerce(value) if value is not None else self.default


class EAVString(EAVAttribute):
    """String attribute stored as JSON string."""

    python_type = str
    json_type = "string"

    def __init__(
        self,
        *,
        max_length: int | None = None,
        required: bool = True,
        default: Any = None,
        help_text: str = "",
        choices: list[str] | None = None,
    ) -> None:
        super().__init__(
            required=required,
            default=default,
            help_text=help_text,
            choices=choices,
        )
        self.max_length = max_length

    def _check_constraints(self, value: Any) -> None:
        if self.max_length is not None and len(value) > self.max_length:
            raise ValidationError([f"{self.name} must be at most {self.max_length} characters."])


class EAVBoolean(EAVAttribute):
    """Boolean attribute stored as JSON boolean."""

    python_type = bool
    json_type = "boolean"

    def _coerce(self, value: Any) -> Any:
        if not isinstance(value, bool):
            raise ValidationError([f"{self.name} must be a boolean."])
        return value


class EAVInteger(EAVAttribute):
    """Integer attribute stored as JSON number."""

    python_type = int
    json_type = "integer"

    def __init__(
        self,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        required: bool = True,
        default: Any = None,
        help_text: str = "",
        choices: list[int] | None = None,
    ) -> None:
        super().__init__(
            required=required,
            default=default,
            help_text=help_text,
            choices=choices,
        )
        self.min_value = min_value
        self.max_value = max_value

    def _coerce(self, value: Any) -> Any:
        # Reject bools (bool is subclass of int in Python)
        if isinstance(value, bool):
            raise ValidationError([f"{self.name} must be an integer."])
        if not isinstance(value, int):
            raise ValidationError([f"{self.name} must be an integer."])
        return value

    def _check_constraints(self, value: Any) -> None:
        if self.min_value is not None and value < self.min_value:
            raise ValidationError([f"{self.name} must be >= {self.min_value}."])
        if self.max_value is not None and value > self.max_value:
            raise ValidationError([f"{self.name} must be <= {self.max_value}."])


class EAVFloat(EAVAttribute):
    """Float attribute stored as JSON number."""

    python_type = float
    json_type = "number"

    def __init__(
        self,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
        required: bool = True,
        default: Any = None,
        help_text: str = "",
        choices: list[float] | None = None,
    ) -> None:
        super().__init__(
            required=required,
            default=default,
            help_text=help_text,
            choices=choices,
        )
        self.min_value = min_value
        self.max_value = max_value

    def _coerce(self, value: Any) -> Any:
        # Reject bools
        if isinstance(value, bool):
            raise ValidationError([f"{self.name} must be a number."])
        if isinstance(value, int):
            return float(value)
        if not isinstance(value, float):
            raise ValidationError([f"{self.name} must be a number."])
        return value

    def _check_constraints(self, value: Any) -> None:
        if self.min_value is not None and value < self.min_value:
            raise ValidationError([f"{self.name} must be >= {self.min_value}."])
        if self.max_value is not None and value > self.max_value:
            raise ValidationError([f"{self.name} must be <= {self.max_value}."])


class EAVDecimal(EAVAttribute):
    """Decimal attribute stored as JSON string for precision.

    JSON has no native decimal type, so values are serialized as strings
    (e.g., ``"0.06500"``) and deserialized back to ``Decimal``.
    """

    python_type = Decimal
    json_type = "decimal"

    def __init__(
        self,
        *,
        max_digits: int | None = None,
        decimal_places: int | None = None,
        min_value: Decimal | float | None = None,
        max_value: Decimal | float | None = None,
        required: bool = True,
        default: Any = None,
        help_text: str = "",
        choices: list[Decimal] | None = None,
    ) -> None:
        super().__init__(
            required=required,
            default=default,
            help_text=help_text,
            choices=choices,
        )
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        self.min_value = Decimal(str(min_value)) if min_value is not None else None
        self.max_value = Decimal(str(max_value)) if max_value is not None else None

    def _coerce(self, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValidationError([f"{self.name} must be a decimal."])
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float, str)):
            try:
                return Decimal(str(value))
            except InvalidOperation:
                raise ValidationError([f"{self.name} must be a valid decimal."]) from None
        raise ValidationError([f"{self.name} must be a decimal."])

    def _check_constraints(self, value: Any) -> None:
        if self.min_value is not None and value < self.min_value:
            raise ValidationError([f"{self.name} must be >= {self.min_value}."])
        if self.max_value is not None and value > self.max_value:
            raise ValidationError([f"{self.name} must be <= {self.max_value}."])
        if self.max_digits is not None or self.decimal_places is not None:
            _sign, digits, exponent = value.as_tuple()
            num_digits = len(digits)
            # Number of digits to the right of the decimal point
            decimals = -exponent if exponent < 0 else 0
            # Total integer digits
            whole_digits = num_digits - decimals

            if self.decimal_places is not None and decimals > self.decimal_places:
                raise ValidationError([f"{self.name} must have at most {self.decimal_places} decimal places."])
            if self.max_digits is not None:
                max_whole = self.max_digits - (self.decimal_places or 0)
                if whole_digits > max_whole:
                    raise ValidationError([f"{self.name} has too many digits (max {self.max_digits})."])

    def to_json(self, value: Any) -> Any:
        """Serialize Decimal to string for JSON storage."""
        if value is None:
            return None
        return str(value)

    def from_json(self, value: Any) -> Any:
        """Deserialize string back to Decimal."""
        if value is None:
            return self.default
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return self.default


# ---------------------------------------------------------------------------
# Metaclass and base schema
# ---------------------------------------------------------------------------


class EAVSchemaMeta(type):
    """Metaclass that collects EAVAttribute instances from class body.

    Sets each attribute's ``.name`` from its class variable name and stores
    all attributes in ``_eav_attributes``.  Supports inheritance: child
    schemas inherit parent attributes and can override them.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ) -> EAVSchemaMeta:
        # Collect inherited attributes from parents
        attrs: dict[str, EAVAttribute] = {}
        for base in bases:
            parent_attrs = getattr(base, "_eav_attributes", {})
            attrs.update(parent_attrs)

        # Collect from current class namespace
        attr_names = []
        for key, value in list(namespace.items()):
            if isinstance(value, EAVAttribute):
                value.name = key
                attrs[key] = value
                attr_names.append(key)

        # Remove attribute instances from namespace (prevent confusion)
        for key in attr_names:
            del namespace[key]

        namespace["_eav_attributes"] = attrs
        return super().__new__(mcs, name, bases, namespace)


class EAVSchema(metaclass=EAVSchemaMeta):
    """Base class for EAV schema definitions.

    Declare attributes as class variables using EAV attribute types.
    The metaclass collects them into ``_eav_attributes``.

    Example::

        class MyConfig(EAVSchema):
            enabled = EAVBoolean(default=False)
            name = EAVString(required=True)

        cleaned = MyConfig.validate({"enabled": True, "name": "test"})
    """

    _eav_attributes: dict[str, EAVAttribute]

    @classmethod
    def get_attributes(cls) -> dict[str, EAVAttribute]:
        """Return the schema's attribute definitions."""
        return dict(cls._eav_attributes)

    @classmethod
    def validate(cls, data: dict[str, Any] | None) -> dict[str, Any]:
        """Validate all attributes, coerce types, reject unknown keys.

        Returns the cleaned dict.  Raises ``ValidationError`` with
        ``message_dict`` mapping field names to error lists.
        """
        if data is None:
            data = {}

        if not isinstance(data, dict):
            raise ValidationError({"__all__": ["Config must be a dict."]})

        errors: dict[str, list[str]] = {}
        cleaned: dict[str, Any] = {}

        # Check for unknown keys
        known_keys = set(cls._eav_attributes)
        unknown = set(data) - known_keys
        if unknown:
            for key in sorted(unknown):
                errors[key] = [f"Unknown config key: {key}."]

        # Validate each declared attribute
        for attr_name, attr in cls._eav_attributes.items():
            value = data.get(attr_name)
            try:
                cleaned_value = attr.validate(value)
                if cleaned_value is not None:
                    cleaned[attr_name] = attr.to_json(cleaned_value)
            except ValidationError as exc:
                if hasattr(exc, "message_dict"):
                    for field, msgs in exc.message_dict.items():
                        errors.setdefault(field, []).extend(msgs)
                elif hasattr(exc, "messages"):
                    errors.setdefault(attr_name, []).extend(exc.messages)
                else:
                    errors.setdefault(attr_name, []).append(str(exc.message))

        if errors:
            raise ValidationError(errors)

        # Cross-field validation
        cls.validate_cross(cleaned)

        return cleaned

    @classmethod
    def validate_cross(cls, data: dict[str, Any]) -> None:
        """Override to add cross-field validation rules.

        Called after individual attribute validation succeeds.
        Raise ``ValidationError`` with ``message_dict`` on failure.
        """

    @classmethod
    def apply_defaults(cls, data: dict[str, Any] | None) -> dict[str, Any]:
        """Fill missing optional fields from defaults.

        Does NOT validate — use :meth:`validate` for full validation.
        """
        if data is None:
            data = {}

        result = dict(data)
        for attr_name, attr in cls._eav_attributes.items():
            if attr_name not in result and attr.default is not None:
                result[attr_name] = attr.to_json(attr.default)
        return result
