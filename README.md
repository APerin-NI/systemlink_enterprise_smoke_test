# SystemLink REST API Smoke Test

A lightweight CLI script that verifies connectivity and basic health of a SystemLink Enterprise server by running read-only checks and create → query → delete lifecycle tests across key services.

All artifacts created during CRUD tests are automatically deleted before the script exits — the server is left clean regardless of the outcome.

---

## Requirements

- Python 3.10+
- [`slcli`](https://github.com/ni/slcli) installed and at least one profile configured
- `requests` Python package (`pip install requests`)

---

## Setup

Configure an `slcli` profile for each server you want to test:

```bash
slcli login --profile my-server --url https://systemlink.example.com/ --api-key <YOUR_API_KEY>
```

List all configured profiles:

```bash
slcli config list
```

---

## Usage

### 1. Activate a profile

```bash
slcli config use <profile_name>
```

Example:

```bash
slcli config use my-server
```

### 2. Run the smoke test

```bash
python smoke_test.py [--workspace <NAME_OR_ID>] [--output <FILE>]
```

#### Options

| Option | Description |
|---|---|
| `--workspace NAME_OR_ID` | Run CRUD tests against a specific workspace (by name or ID). If omitted, the first workspace returned by the server is used. |
| `--output FILE` | Write results to a file. Use a `.json` extension for machine-readable JSON output; any other extension produces plain text. |
| `--profile NAME` | Informational only — activate the profile first with `slcli config use`. |

---

## Examples

**Run against the default workspace:**

```bash
python smoke_test.py
```

**Run against a specific workspace by name:**

```bash
python smoke_test.py --workspace MY_WORKSPACE
```

**Run against a specific workspace by ID:**

```bash
python smoke_test.py --workspace xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**Save results to a plain text file:**

```bash
python smoke_test.py --workspace MY_WORKSPACE --output results.txt
```

**Save results as JSON:**

```bash
python smoke_test.py --workspace MY_WORKSPACE --output results.json
```

**Switch profile and run:**

```bash
slcli config use my-other-server
python smoke_test.py --workspace Default
```

---

## Sample output

```
SystemLink Smoke Test — profile: my-server
Server    : https://systemlink.example.com
Workspace : MY_WORKSPACE  (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
────────────────────────────────────────────────────────────────────────
  ────────────────────────────────────────────────────────────────────
  READ-ONLY CHECKS
  [PASS]   Auth · current user                         HTTP 200
  [PASS]   Users · query                               HTTP 200
  [PASS]   Workspaces · list                           HTTP 200
  [PASS]   Tags · list                                 HTTP 200
  [PASS]   Assets · query                              HTTP 200
  [PASS]   TestMonitor · query results                 HTTP 200
  [PASS]   TestMonitor · query products                HTTP 200
  [PASS]   Files · service info                        HTTP 200
  [PASS]   Dataframe · query tables                    HTTP 200
  [PASS]   WorkItems · query                           HTTP 200
  [PASS]   Specs · service info                        HTTP 200
  [PASS]   Notebooks · query                           HTTP 200
  [PASS]   Feeds · list                                HTTP 200
  ────────────────────────────────────────────────────────────────────
  CRUD LIFECYCLE TESTS  (create → query → delete)
  [PASS]   Assets · create                             HTTP 200
  [PASS]   Assets · query by serial                    HTTP 200
  [PASS]   Assets · delete                             HTTP 200
  [PASS]   Tags · create                               HTTP 201
  [PASS]   Tags · query by path                        HTTP 200
  [PASS]   Tags · delete                               HTTP 200
  [PASS]   Products · create                           HTTP 201
  [PASS]   Products · query by name                    HTTP 200
  [PASS]   Products · delete                           HTTP 204
  [PASS]   Results · create                            HTTP 201
  [PASS]   Results · query by program                  HTTP 200
  [PASS]   Results · delete                            HTTP 204
  [PASS]   WorkItems · create                          HTTP 201
  [PASS]   WorkItems · query by name                   HTTP 200
  [PASS]   WorkItems · delete                          HTTP 204
  [PASS]   Dataframe · create table                    HTTP 201
  [PASS]   Dataframe · get table                       HTTP 200
  [PASS]   Dataframe · delete table                    HTTP 204
  [PASS]   Systems · create virtual                    HTTP 201
  [PASS]   Systems · summary                           HTTP 200
  [PASS]   Systems · delete virtual                    HTTP 200
────────────────────────────────────────────────────────────────────────
  34/34 passed  ✓ all passed
Results written to: results.json
```

---

## What is tested

### Read-only checks

| Service | Test |
|---|---|
| Auth | `GET /niauth/v1/user` — verifies the API key is valid |
| Users | `POST /niuser/v1/users/query` |
| Workspaces | `GET /niuser/v1/workspaces` |
| Tags | `GET /nitag/v2/tags` |
| Assets | `POST /niapm/v1/query-assets` |
| Test Monitor | `POST /nitestmonitor/v2/query-results` and `query-products` |
| Files | `GET /nifile/v1` — service capabilities |
| Dataframe | `POST /nidataframe/v1/query-tables` |
| Work Items | `POST /niworkitem/v1/query-workitems` |
| Specifications | `GET /nispec/v1` — service capabilities |
| Notebooks | `POST /ninotebook/v1/notebook/query` |
| Feeds | `GET /nifeed/v1/feeds` |

### CRUD lifecycle tests

Each test creates a resource, queries it, then deletes it. If create fails, delete is skipped automatically.

| Service | Resource created |
|---|---|
| Assets | Asset with `serialNumber = "SMOKE-0001"` |
| Tags | Tag at path `smoke.test.tag` (type `DOUBLE`) |
| Products | Product `SMOKE-PART-001 / smoke-test-product` |
| Test Results | Result for program `smoke-test-program` (status `PASSED`) |
| Work Items | Work item `smoke-test-workitem` (type `testplan`) |
| Dataframe | Table `smoke-test-table` with index + voltage columns |
| Systems | Virtual system `smoke-test-system` (created via `POST /nisysmgmt/v1/virtual`) |

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All tests passed |
| `1` | One or more tests failed |
