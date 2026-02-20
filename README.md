# django-eav-json-fields

Schema-validated JSONFields for Django using an EAV-style DSL.

Define expected keys, types, and constraints on JSON dict values stored in Django `JSONField`s. Storage remains plain JSONB in PostgreSQL -- the EAV layer adds validation, type coercion, and admin widgets.

## Requirements

- Python 3.10+
- Django 4.2+

## Installation

```bash
pip install django-eav-json-fields
```

No `INSTALLED_APPS` entry is needed.

## Quick Start

### Define a schema

```python
from eav_fields import EAVSchema, EAVBoolean, EAVString, EAVDecimal, EAVInteger

class ServiceConfig(EAVSchema):
    enabled = EAVBoolean(default=True, help_text="Enable this service")
    label = EAVString(max_length=100, help_text="Display name")
    price = EAVDecimal(required=False, max_digits=10, decimal_places=2)
    max_retries = EAVInteger(min_value=0, max_value=10, default=3, required=False)
```

### Use EAVField on a model

```python
from django.db import models
from eav_fields import EAVField

class Service(models.Model):
    name = models.CharField(max_length=100)
    config = EAVField(schema=ServiceConfig)
```

The field validates during `full_clean()` that the JSON dict conforms to the schema. Unknown keys are rejected, types are coerced, and constraints are enforced.

### Polymorphic schemas

Select a schema based on another field's value:

```python
class Product(models.Model):
    product_type = models.CharField(max_length=20, choices=[("a", "Type A"), ("b", "Type B")])
    config = EAVField(
        schema_map={"a": SchemaA, "b": SchemaB},
        schema_key_field="product_type",
    )
```

## EAV Attribute Types

| Type | Python Type | JSON Storage | Constraints |
|------|-------------|-------------|-------------|
| `EAVString` | `str` | string | `max_length`, `choices` |
| `EAVBoolean` | `bool` | boolean | -- |
| `EAVInteger` | `int` | number | `min_value`, `max_value`, `choices` |
| `EAVFloat` | `float` | number | `min_value`, `max_value`, `choices` |
| `EAVDecimal` | `Decimal` | string | `max_digits`, `decimal_places`, `min_value`, `max_value`, `choices` |

All attributes support: `required` (default `True`), `default`, `help_text`, `choices`.

## Cross-field Validation

Override `validate_cross` for rules spanning multiple attributes:

```python
from django.core.exceptions import ValidationError
from eav_fields import EAVSchema, EAVInteger

class MyConfig(EAVSchema):
    min_val = EAVInteger()
    max_val = EAVInteger()

    @classmethod
    def validate_cross(cls, data):
        if data.get("min_val", 0) >= data.get("max_val", 0):
            raise ValidationError({"max_val": ["max_val must be greater than min_val."]})
```

## Schema Inheritance

Child schemas inherit parent attributes and can override them:

```python
class BaseConfig(EAVSchema):
    name = EAVString()

class ExtendedConfig(BaseConfig):
    count = EAVInteger()  # inherits 'name' from parent
```

## Admin Widget

`EAVField` automatically provides an `EAVWidget` in the Django admin that renders typed HTML inputs for each schema attribute, with show/hide support for polymorphic schemas.

## Migration Support

Schema references are serialized as dotted import paths in migrations. Both class references and string paths are accepted:

```python
# Both are equivalent:
config = EAVField(schema=MySchema)
config = EAVField(schema="myapp.schemas.MySchema")
```

## License

MIT
