"""Custom Django admin widgets for EAV fields."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from django import forms
from django.utils.safestring import SafeString, mark_safe

if TYPE_CHECKING:
    from .eav import EAVSchema


def _resolve_schema_class(ref: type[EAVSchema] | str) -> type[EAVSchema]:
    """Resolve a schema class from either a direct reference or dotted path."""
    if isinstance(ref, str):
        import importlib

        module_path, _, class_name = ref.rpartition(".")
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    return ref


class EAVWidget(forms.Widget):
    """Widget that renders EAV config as individual form fields.

    For static schemas, renders a single fieldset with typed HTML inputs.
    For polymorphic schemas, renders all fieldsets with JS show/hide
    based on the key field's ``<select>`` change event.

    Falls back to a ``<textarea>`` for JSON editing when no schema applies.
    """

    template_name = "django/forms/widgets/textarea.html"

    def __init__(
        self,
        *,
        schema: type[EAVSchema] | str | None = None,
        schema_map: Mapping[str, type[EAVSchema] | str] | None = None,
        schema_key_field: str | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(attrs=attrs)
        self.schema = schema
        self.schema_map = schema_map
        self.schema_key_field = schema_key_field

    def _get_schemas(self) -> dict[str, type[EAVSchema]]:
        """Return a mapping of key -> resolved schema class."""
        if self.schema is not None:
            resolved = _resolve_schema_class(self.schema)
            return {"__static__": resolved}

        if self.schema_map is not None:
            return {k: _resolve_schema_class(v) for k, v in self.schema_map.items()}

        return {}

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> SafeString:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                value = {}
        if not isinstance(value, dict):
            value = {}

        schemas = self._get_schemas()
        if not schemas:
            # Fallback to raw JSON textarea
            json_str = json.dumps(value, indent=2, default=str)
            return mark_safe(f'<textarea name="{name}" id="id_{name}" rows="10" cols="40">{json_str}</textarea>')

        final_attrs = self.build_attrs(attrs or {})
        widget_id = final_attrs.get("id", f"id_{name}")
        json_str = json.dumps(value, indent=2, default=str)

        html_parts: list[str] = []

        # Hidden textarea holding actual JSON (submitted with form)
        html_parts.append(f'<textarea name="{name}" id="{widget_id}" style="display:none">{json_str}</textarea>')

        is_polymorphic = "__static__" not in schemas

        for schema_key, schema_cls in schemas.items():
            fieldset_id = f"{widget_id}_fieldset_{schema_key}"
            legend = schema_key if is_polymorphic else "Configuration"

            html_parts.append(f'<fieldset id="{fieldset_id}" class="eav-fieldset" data-schema-key="{schema_key}">')
            html_parts.append(f"<legend>{legend}</legend>")

            from .eav import EAVBoolean, EAVDecimal, EAVFloat, EAVInteger, EAVString

            for attr_name, attr in schema_cls.get_attributes().items():
                field_id = f"{widget_id}_{schema_key}_{attr_name}"
                current_value = value.get(attr_name, "")
                label = attr_name.replace("_", " ").title()
                help_html = f'<br><small class="help">{attr.help_text}</small>' if attr.help_text else ""
                required_marker = " *" if attr.required else ""

                html_parts.append('<div class="eav-field" style="margin:4px 0">')
                html_parts.append(f'<label for="{field_id}">{label}{required_marker}:</label> ')

                if isinstance(attr, EAVBoolean):
                    checked = " checked" if current_value else ""
                    html_parts.append(
                        f'<input type="checkbox" id="{field_id}" '
                        f'name="{field_id}" data-eav-field="{attr_name}" '
                        f'data-eav-type="bool"{checked}>'
                    )
                elif isinstance(attr, EAVString) and attr.choices:
                    html_parts.append(
                        f'<select id="{field_id}" name="{field_id}" '
                        f'data-eav-field="{attr_name}" data-eav-type="string">'
                    )
                    if not attr.required:
                        html_parts.append('<option value="">---------</option>')
                    for choice in attr.choices:
                        selected = " selected" if current_value == choice else ""
                        html_parts.append(f'<option value="{choice}"{selected}>{choice}</option>')
                    html_parts.append("</select>")
                elif isinstance(attr, (EAVDecimal, EAVFloat)):
                    step = "any"
                    display_val = current_value if current_value != "" else ""
                    html_parts.append(
                        f'<input type="number" id="{field_id}" '
                        f'name="{field_id}" step="{step}" '
                        f'value="{display_val}" '
                        f'data-eav-field="{attr_name}" '
                        f'data-eav-type="{"decimal" if isinstance(attr, EAVDecimal) else "float"}">'
                    )
                elif isinstance(attr, EAVInteger):
                    display_val = current_value if current_value != "" else ""
                    html_parts.append(
                        f'<input type="number" id="{field_id}" '
                        f'name="{field_id}" step="1" '
                        f'value="{display_val}" '
                        f'data-eav-field="{attr_name}" '
                        f'data-eav-type="int">'
                    )
                else:
                    display_val = current_value if current_value != "" else ""
                    max_length = ""
                    if isinstance(attr, EAVString) and attr.max_length:
                        max_length = f' maxlength="{attr.max_length}"'
                    html_parts.append(
                        f'<input type="text" id="{field_id}" '
                        f'name="{field_id}"{max_length} '
                        f'value="{display_val}" '
                        f'data-eav-field="{attr_name}" '
                        f'data-eav-type="string">'
                    )

                html_parts.append(help_html)
                html_parts.append("</div>")

            html_parts.append("</fieldset>")

        # Inline JS: sync individual fields back to hidden textarea on submit,
        # and handle show/hide for polymorphic schemas.
        html_parts.append(f"""
<script>
(function() {{
    var textarea = document.getElementById('{widget_id}');
    var form = textarea.closest('form');
    if (!form) return;

    function collectFields() {{
        var data = {{}};
        var visible = document.querySelectorAll(
            '#' + '{widget_id}'.replace(/\\./g, '\\\\.') +
            '_fieldset___static__ [data-eav-field], ' +
            '.eav-fieldset:not([style*="display: none"]):not([style*="display:none"]) [data-eav-field]'
        );
        for (var i = 0; i < visible.length; i++) {{
            var el = visible[i];
            var key = el.getAttribute('data-eav-field');
            var type = el.getAttribute('data-eav-type');
            if (type === 'bool') {{
                data[key] = el.checked;
            }} else if (type === 'int') {{
                if (el.value !== '') data[key] = parseInt(el.value, 10);
            }} else if (type === 'float') {{
                if (el.value !== '') data[key] = parseFloat(el.value);
            }} else if (type === 'decimal') {{
                if (el.value !== '') data[key] = el.value;
            }} else {{
                if (el.value !== '') data[key] = el.value;
            }}
        }}
        textarea.value = JSON.stringify(data);
    }}

    form.addEventListener('submit', collectFields);
""")

        if is_polymorphic and self.schema_key_field:
            html_parts.append(f"""
    // Show/hide fieldsets based on key field
    var keyField = document.getElementById('id_{self.schema_key_field}');
    if (keyField) {{
        function updateFieldsets() {{
            var val = keyField.value;
            var fieldsets = document.querySelectorAll('.eav-fieldset');
            for (var i = 0; i < fieldsets.length; i++) {{
                var fs = fieldsets[i];
                var sk = fs.getAttribute('data-schema-key');
                fs.style.display = (sk === val) ? '' : 'none';
            }}
        }}
        keyField.addEventListener('change', updateFieldsets);
        updateFieldsets();
    }}
""")

        html_parts.append("})();\n</script>")

        return mark_safe("\n".join(html_parts))

    def value_from_datadict(
        self,
        data: Mapping[str, Any],
        files: Any,
        name: str,
    ) -> Any:
        """Reconstruct dict from POST data.

        The hidden textarea holds the JSON (synced by JS on submit).
        Falls back to parsing individual EAV fields if the textarea is empty.
        """
        raw = data.get(name)
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass
        return {}
