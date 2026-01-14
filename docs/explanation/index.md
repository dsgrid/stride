(core-concepts)=
(explanation)=
# Core Concepts

This section explains the key concepts and architecture behind STRIDE's data pipeline.

## Overview

STRIDE transforms raw energy data into hourly electricity demand projections through a multi-stage pipeline:

1. **Data Download** - Retrieve datasets from remote repositories (e.g., GitHub releases)
2. **Data Validation** - Register and validate data using dsgrid's dimension mapping system
3. **Computation** - Calculate energy projections using dbt (data build tool) SQL transformations

Each stage is designed to be modular and customizable, allowing users to swap out datasets, adjust validation rules, or modify calculation logic.

```{toctree}
:maxdepth: 2

data_download
data_validation
customizing_checks
dbt_computation
```
