{% macro table_ref(default_table, var_name=none) %}
  {% if var_name %}
    {{ ref(var(var_name, default_table)) }}
  {% else %}
    {{ ref(var(default_table + '_override', default_table)) }}
  {% endif %}
{% endmacro %}
