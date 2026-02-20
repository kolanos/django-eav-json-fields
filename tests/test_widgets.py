"""Unit tests for custom Django admin widgets."""

from django.http import QueryDict

from eav_fields.eav import EAVBoolean, EAVDecimal, EAVInteger, EAVSchema, EAVString
from eav_fields.widgets import EAVWidget


class _TestSchema(EAVSchema):
    name = EAVString(help_text="The name")
    enabled = EAVBoolean(default=False, required=False, help_text="Is it on?")
    count = EAVInteger(required=False)
    rate = EAVDecimal(required=False)


class _SchemaX(EAVSchema):
    mode = EAVString(choices=["fast", "slow"])


class _SchemaY(EAVSchema):
    limit = EAVInteger(min_value=0)


class TestEAVWidgetRender:
    def test_renders_text_input_for_string(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        html = widget.render("config", {"name": "hello"})
        assert 'data-eav-type="string"' in html
        assert 'data-eav-field="name"' in html
        assert 'value="hello"' in html

    def test_renders_checkbox_for_bool(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        html = widget.render("config", {"enabled": True})
        assert 'type="checkbox"' in html
        assert 'data-eav-type="bool"' in html
        assert "checked" in html

    def test_renders_number_input_for_integer(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        html = widget.render("config", {"name": "test", "count": 5})
        assert 'data-eav-type="int"' in html
        assert 'step="1"' in html

    def test_renders_number_input_for_decimal(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        html = widget.render("config", {"name": "test", "rate": "0.065"})
        assert 'data-eav-type="decimal"' in html
        assert 'step="any"' in html

    def test_renders_select_for_choices(self) -> None:
        widget = EAVWidget(schema=_SchemaX)
        html = widget.render("config", {"mode": "fast"})
        assert "<select" in html
        assert "fast" in html
        assert "slow" in html

    def test_renders_hidden_textarea(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        html = widget.render("config", {"name": "test"})
        assert 'style="display:none"' in html
        assert "<textarea" in html

    def test_renders_help_text(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        html = widget.render("config", {"name": "test"})
        assert "The name" in html

    def test_fallback_textarea_when_no_schema(self) -> None:
        widget = EAVWidget()
        html = widget.render("config", {"key": "val"})
        assert "<textarea" in html
        assert 'style="display:none"' not in html


class TestEAVWidgetPolymorphic:
    def test_renders_all_fieldsets(self) -> None:
        widget = EAVWidget(
            schema_map={"x": _SchemaX, "y": _SchemaY},
            schema_key_field="config_type",
        )
        html = widget.render("config", {})
        assert 'data-schema-key="x"' in html
        assert 'data-schema-key="y"' in html

    def test_includes_show_hide_js(self) -> None:
        widget = EAVWidget(
            schema_map={"x": _SchemaX, "y": _SchemaY},
            schema_key_field="config_type",
        )
        html = widget.render("config", {})
        assert "updateFieldsets" in html
        assert "id_config_type" in html


class TestEAVWidgetValueFromDatadict:
    def test_reconstructs_from_textarea_json(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        data = QueryDict(mutable=True)
        data["config"] = '{"name": "test", "enabled": true}'
        result = widget.value_from_datadict(data, {}, "config")
        assert result == {"name": "test", "enabled": True}

    def test_empty_textarea_returns_empty_dict(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        data = QueryDict(mutable=True)
        result = widget.value_from_datadict(data, {}, "config")
        assert result == {}

    def test_invalid_json_returns_empty_dict(self) -> None:
        widget = EAVWidget(schema=_TestSchema)
        data = QueryDict(mutable=True)
        data["config"] = "not json"
        result = widget.value_from_datadict(data, {}, "config")
        assert result == {}
