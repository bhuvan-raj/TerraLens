# Contributing to TerraLens

First off — thank you for taking the time to contribute! TerraLens is a community-driven project and every contribution, big or small, makes a difference.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Priority Contributions](#priority-contributions)
- [Adding Cloud Resources](#adding-cloud-resources)
- [Code Style](#code-style)
- [Running Tests](#running-tests)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

---

## Ways to Contribute

You don't have to write code to contribute — there are many ways to help:

| Type | Examples |
|---|---|
| 🐛 **Bug reports** | Found something broken? Open an issue with steps to reproduce |
| 📖 **Documentation** | Fix typos, clarify confusing sections, improve the README |
| 🏗️ **Project structure** | Help reorganize the codebase, improve folder layout, add missing `__init__.py` files |
| 💻 **Source code** | Fix bugs, add features, refactor existing code |
| ☁️ **Cloud resources** | Add missing AWS, Azure, or GCP resources to the catalog |
| 🧪 **Tests** | Write new tests, improve coverage, add edge case handling |
| 🎨 **UI improvements** | Improve the Textual layout, fix alignment issues, enhance the visual design |
| 💡 **Feature ideas** | Open an issue to suggest new features or improvements |
| 🔍 **Code review** | Review open pull requests and leave feedback |

Every contribution matters — even fixing a single typo in the README is genuinely appreciated.

---

## Getting Started

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/Insight-Q.git
cd Insight-Q

# 3. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 4. Install in editable mode
pip install -e .
pip install -r requirements.txt

# 5. Create a feature branch
git checkout -b feature/your-feature-name

# 6. Make your changes, then run tests
pytest tests/ -v

# 7. Push and open a Pull Request
git push origin feature/your-feature-name
```

---

## Priority Contributions

### 🔥 #1 — Refactor `cli.py` into a Modular Package Structure

This is the **most impactful contribution** you can make right now.

Currently the entire application — all 2300+ lines — lives in a single file `src/insight_tf/cli.py`. This makes it hard to navigate, maintain, and extend. The goal is to split it into a clean modular package like this:

```
src/insight_tf/
├── __init__.py
├── __main__.py          # entry point
├── cli.py               # only contains main() entry point
├── config.py            # APP_CONFIG loader
├── state.py             # load_state(), format_value(), SAMPLE_STATE
├── catalog.py           # AWS_RESOURCE_CATALOG, ALL_AWS_RESOURCES
├── templates.py         # RESOURCE_TEMPLATES, _build_tf_block()
├── screens/
│   ├── __init__.py
│   ├── provider.py      # ProviderSelectScreen
│   ├── picker.py        # AWSResourcePickerScreen
│   ├── wizard.py        # AddResourceWizard
│   └── confirm.py       # ConfirmDestroyScreen
└── widgets/
    ├── __init__.py
    ├── overview.py      # StatCard, OverviewPage
    └── manage.py        # ResourceTree, AttributePanel, ManagePage
```

**Guidelines for this refactor:**
- Each file should be under 400 lines
- Use relative imports (`from ..catalog import ...`) inside the package
- Avoid circular imports — screens should import widgets inside methods, not at module level
- All existing functionality must work exactly the same after the refactor
- Tests must still pass after the split

If you plan to work on this, please open an issue first so we can coordinate and avoid duplicate efforts.

---

### 🌩️ #2 — Add Cloud Resources to the Catalog

The Add Resource wizard currently supports **334 AWS resources** across 20 categories. There is a lot of room to grow:

**Azure resources** — Add `azurerm_*` resources to `AWS_RESOURCE_CATALOG` (or a new `AZURE_RESOURCE_CATALOG`) across categories like:
- Compute (`azurerm_virtual_machine`, `azurerm_linux_virtual_machine`)
- Storage (`azurerm_storage_account`, `azurerm_storage_blob`)
- Networking (`azurerm_virtual_network`, `azurerm_subnet`)
- Database (`azurerm_mssql_server`, `azurerm_cosmosdb_account`)

**GCP resources** — Add `google_*` resources:
- Compute (`google_compute_instance`, `google_compute_disk`)
- Storage (`google_storage_bucket`)
- Networking (`google_compute_network`, `google_compute_subnetwork`)
- Database (`google_sql_database_instance`, `google_spanner_instance`)

**Additional AWS resources** — if you notice any missing `aws_*` resources, add them to the relevant category in `AWS_RESOURCE_CATALOG`.

**Adding a basic resource entry** (just catalog listing):
```python
# In AWS_RESOURCE_CATALOG, find the right category and add:
{"type": "aws_your_resource", "description": "Short description of what it does"},
```

**Adding a guided form** (fills fields interactively):
```python
RESOURCE_TEMPLATES["aws_your_resource"] = {
    "description": "Short description",
    "fields": [
        {"name": "resource_name", "label": "Resource name (TF identifier)",
         "placeholder": "my_resource", "required": True, "default": ""},
        {"name": "some_field",    "label": "Some field label",
         "placeholder": "example-value",  "required": True, "default": ""},
    ],
    "template": 'resource "aws_your_resource" "{resource_name}" {{\n  some_field = "{some_field}"\n}}\n',
}
```

Please keep resources in alphabetical order within their category.

---

## Code Style

- Follow existing code style — the project uses standard Python formatting
- Keep lines under 120 characters where possible
- Add a short docstring to any new class or function
- Use type hints for function signatures
- Do not introduce new dependencies without discussing in an issue first

---

## Running Tests

```bash
# Run the full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src/insight_tf --cov-report=term-missing

# Run a specific test file
pytest tests/test_catalog.py -v
```

All pull requests must pass the test suite before being merged. If you add a new feature, please add corresponding tests in the `tests/` directory.

---

## Submitting a Pull Request

1. Make sure your branch is up to date with `main`:
   ```bash
   git fetch origin
   git rebase origin/main
   ```
2. Run the full test suite and ensure everything passes
3. Write a clear PR title and description explaining what you changed and why
4. Reference any related issues with `Fixes #123` or `Closes #123`
5. Keep PRs focused — one feature or fix per PR makes review much easier

---

## Reporting Bugs

Open a [GitHub Issue](https://github.com/bhuvan-raj/Insight-Q/issues) and include:

- Your OS and Python version
- How you installed TerraLens (binary / pip / source)
- Steps to reproduce the bug
- The full error message or traceback
- Your `terraform version` output if the bug involves plan/apply/destroy

---

## Feature Requests

Open a [GitHub Issue](https://github.com/bhuvan-raj/Insight-Q/issues) with the `enhancement` label. Describe:

- What you want TerraLens to do
- Why it would be useful
- Any implementation ideas you have

---

## Questions?

If you're unsure about anything, open an issue and ask. No question is too small.

---

<div align="center">
  <sub>Thank you for helping make TerraLens better ❤️</sub>
</div>
