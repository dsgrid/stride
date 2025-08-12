{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set scenario = var('scenario', none) -%}
    
    {%- if scenario -%}
        {{ scenario | trim }}
    {%- elif custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
