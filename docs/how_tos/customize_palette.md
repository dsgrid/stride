(customize-palette)=
# Customize the Color Palette

Create consistent colors for visualizations.

## View Available Palettes

```{eval-rst}

.. code-block:: console

   $ stride palette list
```

## Preview a Palette

```{eval-rst}

.. code-block:: console

   $ stride palette view my_project
```

## Create a Custom Palette

Initialize a palette configuration file:

```{eval-rst}

.. code-block:: console

   $ stride palette init my_project
```

This creates a JSON file you can edit to assign colors to scenarios, geographies, or other dimensions.

## Set the Default Palette

```{eval-rst}

.. code-block:: console

   $ stride palette set-default my_project custom_palette
```

## Reset to Default

```{eval-rst}

.. code-block:: console

   $ stride palette get-default my_project
```
