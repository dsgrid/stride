(query-project-database)=
# Query a Project's Database Directly

Each STRIDE project stores its data in a DuckDB database at `<project>/registry_data/data.duckdb`. You can query it with SQL, either from Python (no extra installation) or with the DuckDB command line interface (CLI).

## From Python

STRIDE already installs DuckDB's Python package. Open the project read-only and use its connection:

```python
from stride import Project

with Project.load("my_project", read_only=True) as project:
    print(project.con.sql("SHOW ALL TABLES"))
    df = project.con.sql("SELECT * FROM energy_projection LIMIT 10").df()
```

## From the DuckDB CLI

### Install the CLI

STRIDE does not install the DuckDB CLI. Follow the instructions at [duckdb.org/docs/installation](https://duckdb.org/docs/installation/). At the time of writing they are:

```{eval-rst}

.. tabs::

  .. code-tab:: bash Mac/Linux

     curl https://install.duckdb.org | bash

  .. code-tab:: powershell Windows PowerShell

     powershell -NoExit -ExecutionPolicy Bypass -Command "irm https://install.duckdb.org/install.ps1 | iex"
```

Use a CLI version at least as new as the DuckDB version STRIDE uses, which you can check with:

```console
$ python -c "import duckdb; print(duckdb.__version__)"
```

### Open the database read-only

```console
$ duckdb -readonly my_project/registry_data/data.duckdb
```

Always pass `-readonly`:
- Several programs can then read the database at the same time, for example the CLI and `stride view`.
- A newer CLI can't modify the file. A file written by a newer DuckDB may become unreadable by the DuckDB version that STRIDE uses.

Then run SQL at the prompt, for example:

```sql
SHOW ALL TABLES;
SELECT * FROM energy_projection LIMIT 10;
```

## What's in the database

| Schema | Contents |
|---|---|
| `main` | `energy_projection`, the final hourly results for all scenarios |
| One per scenario, e.g. `baseline` | The calculated tables (dbt models) for that scenario |
| `dsgrid_data` | The input datasets, e.g. `baseline__weather_bait__1_0_0` |

## Time zones

Timestamps are stored as absolute instants (`TIMESTAMP WITH TIME ZONE`). DuckDB displays them in the session's time zone:
- STRIDE's own connections use UTC.
- The CLI and other connections usually use your computer's time zone.

To see local standard time, convert explicitly, for example `timezone(time_zone, timestamp)`. See {ref}`time-conventions`.

## See also

- {ref}`export-results` to write tables to CSV or Parquet files
- {ref}`data-api-tutorial` for aggregated queries from Python
