# Debug stride source code
This tutorial is for users and developers that want to debug the stride source code with the
Python debugger. It includes instructions for a UI-based workflow with `VSCode` native debugging
with `pdb`.

The tutorial assumes that you have cloned the stride repository with git, are in the root
directory of the repository, and have activated your virtual environment.

## Debugging with VSCode
The stride repository includes a `VSCode` debug configuration to debug the (1) UI and (2) project
creation process. For setup instructions, please refer to
[VSCode instructions](https://code.visualstudio.com/docs/python/debugging).

1. Select the `Run and Debug` button on the left side of the `VSCode` application. The MacOS keyboard shortcut
is `Shift-Cmd-D`. The Windows shortcut is `Shift-Ctrl-D`.

2. The `debug` menu will appear at the top of the screen. Next to a green triangle button (for run)
is a drop-down where you can select a configuration. Choose `Debug create project`.

3. Navigate to the source file `src/stride/project.py` and search for `def create`.

4. Set a breakpoint at the first line of the create method.


```{eval-rst}
.. warning:: Executing the rest of this procedure will overwrite the project at `./test_project`
```
5. Press the green triangle button to run. `VSCode` will stop execution at that line. You can use the
`VSCode` tools to debug the code.

## Debugging with pdb in a terminal
`pdb` is the standard debugger provided by the Python standard library. Please refer to its
[instructions](https://docs.python.org/3/library/pdb.html) for complete information.

Running the stride CLI through `pdb` requires the location of the stride executable. This
varies based on your operating system and shell.

```{eval-rst}

.. tabs::

  .. code-tab:: console UNIX
 
     $ which stride

  .. code-tab:: console Windows-PowerShell

     $ Get-Command stride

  .. code-tab:: console Windows-Command-Shell

     $ where stride
```

The result will be something like:
```
/Users/dthom/repos/stride/.venv/bin/stride
```

Running a CLI command then becomes something like this:

```{eval-rst}
.. code-block:: console

    $ python -m pdb /Users/dthom/repos/stride/.venv/bin/stride projects create --help
```
You will see output like this:
```
> /Users/dthom/repos/stride/.venv/bin/stride(3)<module>()
-> import re
(Pdb)
```
Press `c` and `enter` and then the program will run to completion.

This can be simplified with text substitution in your shell. Here are examples for various shells.

```{eval-rst}
.. tabs::

  .. code-tab:: console UNIX
 
     $ python -m pdb $(which stride) projects create --help

  .. code-tab:: console Windows-PowerShell

     $ python -m pdb (Get-Command stride).Path projects create --help

  .. code-tab:: console Windows-Command-Shell

     $ for /f "tokens=*" %i in ('where stride') do python -m pdb "%i" projects create --help
```

### Debug any exception that occurs at runtime
This is useful to debug unhandled exceptions in the code (bugs). When executed this way, Python
will automatically enter the debugger (`pdb`) when the exception is raised. Then you can inspect
local variables, move up and down the stack, and run your own code.

```{eval-rst}
.. tabs::

  .. code-tab:: console UNIX
 
     $ python -m pdb $(which stride) projects create tests/data/project_input.json5

  .. code-tab:: console Windows-PowerShell

     $ (Get-Command stride).Path projects create tests/data/project_input.json5

  .. code-tab:: console Windows-Command-Shell

     $ for /f "tokens=*" %i in ('where stride') do python projects create tests/data/project_input.json5
```

### Set a breakpoint at a specific line number
Let's suppose that you want to debug the projection creation process. You want to
set a breakpoint at the `Project.create` method entry point.

You can set the breakpoint in the following ways:

- Add a call to `breakpoint()` at your desired line of code in the source file. Run the CLI command
  in the normal way.
- Instruct `pdb` to stop at specific function or line number.

These instructions describe the `pdb` procedure.

Run the command above to create a project.

You will be at this `pdb` prompt:
```
> /Users/dthom/repos/stride/.venv/bin/stride(3)<module>()
-> import re
(Pdb)
```

Import stride, and set a breakpoint at the create method, and then continue execution.
Python will stop at the breakpoint.
```
(Pdb) import stride
(Pdb) b stride.project.Project.create
```
```
Breakpoint 1 at /Users/dthom/repos/stride/src/stride/project.py:57
```

```
(Pdb) c
```

```
> /Users/dthom/repos/stride/src/stride/project.py(77)create()
-> config = ProjectConfig.from_file(config_file)
```
Enter `l` and/or `ll` to see the current context. Press `n` to execute a line of code.
Press `s` to step into a function. Print a variable like this:
```
(Pdb) p config
ProjectConfig(project_id='test_project', creator='tester', description='This is a test project.', country='country_1', start_year=2025, end_year=2055, step_year=5, weather_year=2018, scenarios=[Scenario(name='baseline', energy_intensity=None, gdp=None, hdi=None, load_shapes=None, population=None), Scenario(name='alternate_gdp', energy_intensity=None, gdp=PosixPath('tests/data/alternate_gdp.csv'), hdi=None, load_shapes=None, population=None)], calculated_table_overrides=[])
```

`Pydantic` objects like this can can be hard to read. Use the `rich` library to get a better view.
```
(Pdb) from rich import print
(Pdb) print(config)
```
```
ProjectConfig(
    project_id='test_project',
    creator='tester',
    description='This is a test project.',
    country='country_1',
    start_year=2025,
    end_year=2055,
    step_year=5,
    weather_year=2018,
    scenarios=[
        Scenario(name='baseline', energy_intensity=None, gdp=None, hdi=None, load_shapes=None, population=None),
        Scenario(
            name='alternate_gdp',
            energy_intensity=None,
            gdp=PosixPath('tests/data/alternate_gdp.csv'),
            hdi=None,
            load_shapes=None,
            population=None
        )
    ],
    calculated_table_overrides=[]
)
```
