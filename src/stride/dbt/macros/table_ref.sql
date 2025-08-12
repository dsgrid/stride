{% macro table_ref(default_table) %}
  {{ ref(var(default_table + '_override', default_table)) }}
{% endmacro %}
