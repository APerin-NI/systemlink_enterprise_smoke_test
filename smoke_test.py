"""
SystemLink REST API Smoke Test
Tests key services for connectivity and correct HTTP responses.
Read-only checks run first, then create → query → delete lifecycle tests.
All artifacts created during CRUD tests are deleted before the script exits.

Usage:
    python smoke_test.py [--workspace <name_or_id>] [--profile <name>]

Options:
    --workspace NAME_OR_ID  Workspace name or ID to target for CRUD tests.
                            Defaults to the first workspace on the server.
    --output FILE           Write the test results to a file.
                            Use a .json extension for JSON output,
                            any other extension (or .txt) for plain text.
    --profile NAME          Informational only. Activate the profile first
                            with: slcli config use <profile>

Credentials are loaded from the active slcli profile.
"""

import sys
import argparse
import json
import datetime
import requests
from dataclasses import dataclass, field
from typing import Optional

from slcli.profiles import get_active_profile, get_active_profile_name


PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclass
class TestResult:
    name: str
    status: str  # PASS | FAIL | SKIP
    http_status: Optional[int] = None
    detail: str = ""


class SmokeTest:
    def __init__(self, workspace: Optional[str] = None, output: Optional[str] = None):
        profile = get_active_profile()
        self.profile_name = get_active_profile_name()
        self.base_url = profile.server.rstrip("/")
        self.api_key = profile.api_key
        if not self.api_key:
            raise ValueError(f"No API key found in profile '{self.profile_name}'")
        self.headers = {
            "x-ni-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        self.results: list[TestResult] = []
        self._last_response: Optional[requests.Response] = None
        self._output: Optional[str] = output
        self._started_at: str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ws = self._resolve_workspace(workspace)
        self._workspace_id: Optional[str] = ws[0] if ws else None
        self._workspace_name: Optional[str] = ws[1] if ws else None

    def _resolve_workspace(self, name_or_id: Optional[str] = None) -> Optional[tuple]:
        try:
            resp = requests.get(
                f"{self.base_url}/niuser/v1/workspaces",
                headers=self.headers, timeout=15,
            )
            workspaces = resp.json().get("workspaces", [])
            if not workspaces:
                return None
            if name_or_id:
                match = next(
                    (w for w in workspaces
                     if w.get("name") == name_or_id or w.get("id") == name_or_id),
                    None,
                )
                if match is None:
                    raise ValueError(
                        f"Workspace '{name_or_id}' not found. "
                        f"Available: {[w['name'] for w in workspaces]}"
                    )
                return match["id"], match.get("name", match["id"])
            # default: first workspace
            return workspaces[0]["id"], workspaces[0].get("name", workspaces[0]["id"])
        except ValueError:
            raise
        except Exception:
            return None

    # ------------------------------------------------------------------ helpers

    def _record(self, name: str, resp: Optional[requests.Response], expected: int) -> bool:
        self._last_response = resp
        if resp is None:
            result = TestResult(name, FAIL, detail="No response")
        else:
            passed = resp.status_code == expected
            result = TestResult(
                name,
                PASS if passed else FAIL,
                http_status=resp.status_code,
                detail="" if passed else resp.text[:120],
            )
        self.results.append(result)
        self._print_result(result)
        return result.status == PASS

    def _print_result(self, r: TestResult) -> None:
        badge = f"[{r.status}]"
        http  = f"HTTP {r.http_status}" if r.http_status else ""
        extra = f"  {r.detail}" if r.detail else ""
        print(f"  {badge:<7}  {r.name:<42}  {http}{extra}", flush=True)

    def get(self, name: str, path: str, expected: int = 200) -> bool:
        url = f"{self.base_url}{path}"
        print(f"  ...      {name:<42}", end="\r", flush=True)
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            return self._record(name, resp, expected)
        except Exception as exc:
            result = TestResult(name, FAIL, detail=str(exc))
            self.results.append(result)
            self._print_result(result)
            return False

    def post(self, name: str, path: str, body: dict, expected: int = 200) -> bool:
        url = f"{self.base_url}{path}"
        print(f"  ...      {name:<42}", end="\r", flush=True)
        try:
            resp = requests.post(url, headers=self.headers, json=body, timeout=15)
            return self._record(name, resp, expected)
        except Exception as exc:
            result = TestResult(name, FAIL, detail=str(exc))
            self.results.append(result)
            self._print_result(result)
            return False

    def delete(self, name: str, path: str, expected: int = 204, params: Optional[dict] = None) -> bool:
        url = f"{self.base_url}{path}"
        print(f"  ...      {name:<42}", end="\r", flush=True)
        try:
            resp = requests.delete(url, headers=self.headers, params=params, timeout=15)
            return self._record(name, resp, expected)
        except Exception as exc:
            result = TestResult(name, FAIL, detail=str(exc))
            self.results.append(result)
            self._print_result(result)
            return False

    def put(self, name: str, path: str, body: dict, expected: int = 200) -> bool:
        url = f"{self.base_url}{path}"
        print(f"  ...      {name:<42}", end="\r", flush=True)
        try:
            resp = requests.put(url, headers=self.headers, json=body, timeout=15)
            return self._record(name, resp, expected)
        except Exception as exc:
            result = TestResult(name, FAIL, detail=str(exc))
            self.results.append(result)
            self._print_result(result)
            return False

    def _section(self, title: str) -> None:
        print(f"  {'─'*68}", flush=True)
        print(f"  {title}", flush=True)

    # ---------------------------------------------------------------- test suite

    def run(self) -> None:
        print()
        print(f"SystemLink Smoke Test — profile: {self.profile_name}")
        print(f"Server    : {self.base_url}")
        ws_label = f"{self._workspace_name}  ({self._workspace_id})" if self._workspace_name else "(unknown)"
        print(f"Workspace : {ws_label}")
        print("─" * 72)

        self._section("READ-ONLY CHECKS")

        # ── Auth ──────────────────────────────────────────────────────────────
        self.get("Auth · current user",             "/niauth/v1/user")

        # ── Users & Workspaces ────────────────────────────────────────────────
        self.post("Users · query",                  "/niuser/v1/users/query",           {})
        self.get("Workspaces · list",               "/niuser/v1/workspaces")

        # ── Tags ──────────────────────────────────────────────────────────────
        self.get("Tags · list",                     "/nitag/v2/tags?take=1")

        # ── Asset Management ──────────────────────────────────────────────────
        self.post("Assets · query",                 "/niapm/v1/query-assets",           {})

        # ── Test Monitor ──────────────────────────────────────────────────────
        self.post("TestMonitor · query results",    "/nitestmonitor/v2/query-results",  {})
        self.post("TestMonitor · query products",   "/nitestmonitor/v2/query-products", {})

        # ── Files ─────────────────────────────────────────────────────────────
        self.get("Files · service info",             "/nifile/v1")

        # ── Dataframes ────────────────────────────────────────────────────────
        self.post("Dataframe · query tables",       "/nidataframe/v1/query-tables",     {})

        # ── Work Items ────────────────────────────────────────────────────────
        self.post("WorkItems · query",              "/niworkitem/v1/query-workitems",   {})

        # ── Specifications ────────────────────────────────────────────────────
        self.get("Specs · service info",             "/nispec/v1")

        # ── Notebooks ─────────────────────────────────────────────────────────
        self.post("Notebooks · query",              "/ninotebook/v1/notebook/query",    {})

        # ── Feeds ─────────────────────────────────────────────────────────────
        self.get("Feeds · list",                    "/nifeed/v1/feeds")

        # ── Dynamic Form Fields ───────────────────────────────────────────────
        self.get("DynamicFormFields · list fields", "/nidynamicformfields/v1/fields")

        # ── Comments ──────────────────────────────────────────────────────────
        self.get("Comments · service info",         "/nicomments/v1")

        self._section("CRUD LIFECYCLE TESTS  (create → query → delete)")
        self._crud_assets()
        self._crud_tags()
        self._crud_products()
        self._crud_results()
        self._crud_workitems()
        self._crud_dataframe()
        self._crud_systems()

    # --------------------------------------------------------- CRUD: Systems

    def _crud_systems(self) -> None:
        body = {"alias": "smoke-test-system", "workspace": self._workspace_id}
        ok = self.post("Systems · create virtual", "/nisysmgmt/v1/virtual", body, expected=201)
        system_id = None
        if ok:
            try:
                system_id = self._last_resp_json().get("minionId")
            except Exception:
                pass
        self.get("Systems · summary", "/nisysmgmt/v1/get-systems-summary")
        if system_id:
            self.post("Systems · delete virtual",
                      "/nisysmgmt/v1/remove-systems",
                      {"tgt": [system_id], "force": True})
        else:
            self._skip("Systems · delete virtual", "no id from create")

    # --------------------------------------------------------- CRUD: Assets

    def _crud_assets(self) -> None:
        body = {"assets": [{
            "name": "smoke-test-asset",
            "busType": "USB",
            "modelName": "SmokeTestModel",
            "vendorName": "SmokeTestVendor",
            "serialNumber": "SMOKE-0001",
            "location": {},
        }]}
        ok = self.post("Assets · create", "/niapm/v1/assets", body)
        asset_id = None
        if ok:
            try:
                asset_id = self._last_resp_json().get("assets", [{}])[0].get("id")
            except Exception:
                pass
        self.post("Assets · query by serial",
                  "/niapm/v1/query-assets",
                  {"filter": 'SerialNumber = "SMOKE-0001"'})
        ids = [asset_id] if asset_id else []
        if ids:
            self.post("Assets · delete", "/niapm/v1/delete-assets", {"ids": ids})
        else:
            self._skip("Assets · delete", "no id from create")

    # --------------------------------------------------------- CRUD: Tags

    def _crud_tags(self) -> None:
        path = "smoke.test.tag"
        body = {"path": path, "type": "DOUBLE", "workspace": self._workspace_id}
        self.put("Tags · create", f"/nitag/v2/tags/{path}", body, expected=201)
        self.get("Tags · query by path", f"/nitag/v2/tags/{self._workspace_id}/{path}")
        ws_param = {"workspace": self._workspace_id} if self._workspace_id else None
        self.delete("Tags · delete", f"/nitag/v2/tags/{path}", expected=200, params=ws_param)

    # --------------------------------------------------------- CRUD: Products

    def _crud_products(self) -> None:
        body = {"products": [{"partNumber": "SMOKE-PART-001", "name": "smoke-test-product",
                              "workspace": self._workspace_id}]}
        ok = self.post("Products · create", "/nitestmonitor/v2/products", body, expected=201)
        product_id = None
        if ok:
            try:
                product_id = self._last_resp_json().get("products", [{}])[0].get("id")
            except Exception:
                pass
        self.post("Products · query by name",
                  "/nitestmonitor/v2/query-products",
                  {"filter": 'name = "smoke-test-product"'})
        ids = [product_id] if product_id else []
        if ids:
            self.post("Products · delete", "/nitestmonitor/v2/delete-products", {"ids": ids}, expected=204)
        else:
            self._skip("Products · delete", "no id from create")

    # --------------------------------------------------------- CRUD: Results

    def _crud_results(self) -> None:
        body = {"results": [{
            "programName": "smoke-test-program",
            "status": {"statusType": "PASSED"},
            "operator": "smoke-test",
            "workspace": self._workspace_id,
        }]}
        ok = self.post("Results · create", "/nitestmonitor/v2/results", body, expected=201)
        result_id = None
        if ok:
            try:
                result_id = self._last_resp_json().get("results", [{}])[0].get("id")
            except Exception:
                pass
        self.post("Results · query by program",
                  "/nitestmonitor/v2/query-results",
                  {"filter": 'programName = "smoke-test-program"'})
        ids = [result_id] if result_id else []
        if ids:
            self.post("Results · delete", "/nitestmonitor/v2/delete-results", {"ids": ids}, expected=204)
        else:
            self._skip("Results · delete", "no id from create")

    # --------------------------------------------------------- CRUD: Work Items

    def _crud_workitems(self) -> None:
        body = {"workItems": [{
            "name": "smoke-test-workitem",
            "type": "testplan",
            "state": "NEW",
            "partNumber": "SMOKE-PART-001",
            "workspace": self._workspace_id,
        }]}
        ok = self.post("WorkItems · create", "/niworkitem/v1/workitems", body, expected=201)
        workitem_id = None
        if ok:
            try:
                workitem_id = self._last_resp_json().get("createdWorkItems", [{}])[0].get("id")
            except Exception:
                pass
        self.post("WorkItems · query by name",
                  "/niworkitem/v1/query-workitems",
                  {"name": "smoke-test-workitem"})
        ids = [workitem_id] if workitem_id else []
        if ids:
            self.post("WorkItems · delete", "/niworkitem/v1/delete-workitems", {"ids": ids}, expected=204)
        else:
            self._skip("WorkItems · delete", "no id from create")

    # --------------------------------------------------------- CRUD: Dataframe

    def _crud_dataframe(self) -> None:
        body = {
            "name": "smoke-test-table",
            "workspace": self._workspace_id,
            "columns": [
                {"name": "index",   "dataType": "INT32",   "columnType": "INDEX"},
                {"name": "voltage", "dataType": "FLOAT64", "columnType": "NORMAL"},
            ],
        }
        ok = self.post("Dataframe · create table", "/nidataframe/v1/tables", body, expected=201)
        table_id = None
        if ok:
            try:
                table_id = self._last_resp_json().get("id")
            except Exception:
                pass
        if table_id:
            self.get("Dataframe · get table", f"/nidataframe/v1/tables/{table_id}")
            self.post("Dataframe · delete table",
                      "/nidataframe/v1/delete-tables", {"ids": [table_id]}, expected=204)
        else:
            self._skip("Dataframe · get table",    "no id from create")
            self._skip("Dataframe · delete table",  "no id from create")

    # ---------------------------------------------------- internal helpers

    def _last_resp_json(self) -> dict:
        """Return the JSON body of the most recently recorded response."""
        return self._last_response.json() if self._last_response is not None else {}

    def _skip(self, name: str, reason: str) -> None:
        result = TestResult(name, SKIP, detail=reason)
        self.results.append(result)
        self._print_result(result)

    # ------------------------------------------------------------------ report

    def report(self) -> bool:
        n_pass = sum(1 for r in self.results if r.status == PASS)
        n_fail = sum(1 for r in self.results if r.status == FAIL)
        total  = len(self.results)

        print("─" * 72)
        print(f"  {n_pass}/{total} passed", end="")
        if n_fail:
            print(f"  |  {n_fail} FAILED")
        else:
            print("  ✓ all passed")
        print()

        if self._output:
            self._write_output(n_pass, n_fail, total)

        return n_fail == 0

    def _write_output(self, n_pass: int, n_fail: int, total: int) -> None:
        finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if self._output.endswith(".json"):
            data = {
                "profile": self.profile_name,
                "server": self.base_url,
                "workspace": self._workspace_name,
                "workspaceId": self._workspace_id,
                "startedAt": self._started_at,
                "finishedAt": finished_at,
                "passed": n_pass,
                "failed": n_fail,
                "total": total,
                "tests": [
                    {
                        "name": r.name,
                        "status": r.status,
                        "httpStatus": r.http_status,
                        "detail": r.detail,
                    }
                    for r in self.results
                ],
            }
            with open(self._output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            ws_label = f"{self._workspace_name}  ({self._workspace_id})" if self._workspace_name else "(unknown)"
            lines = [
                f"SystemLink Smoke Test — profile: {self.profile_name}",
                f"Server    : {self.base_url}",
                f"Workspace : {ws_label}",
                f"Started   : {self._started_at}",
                f"Finished  : {finished_at}",
                "─" * 72,
            ]
            for r in self.results:
                badge = f"[{r.status}]"
                http  = f"HTTP {r.http_status}" if r.http_status else ""
                extra = f"  {r.detail}" if r.detail else ""
                lines.append(f"  {badge:<7}  {r.name:<42}  {http}{extra}")
            lines.append("─" * 72)
            summary = f"  {n_pass}/{total} passed"
            summary += "  ✓ all passed" if n_fail == 0 else f"  |  {n_fail} FAILED"
            lines.append(summary)
            with open(self._output, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        print(f"Results written to: {self._output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SystemLink REST API smoke test")
    parser.add_argument(
        "--profile", metavar="NAME",
        help="slcli profile to use (default: currently active profile)",
    )
    parser.add_argument(
        "--workspace", metavar="NAME_OR_ID",
        help="Workspace name or ID to target (default: first workspace on the server)",
    )
    parser.add_argument(
        "--output", metavar="FILE",
        help="Write results to a file (.json for JSON output, otherwise plain text)",
    )
    args = parser.parse_args()

    # Profile switching is handled outside this script via `slcli config use`
    if args.profile:
        print(f"Note: --profile flag is informational only. "
              f"Activate the profile first with: slcli config use {args.profile}")

    suite = SmokeTest(workspace=args.workspace, output=args.output)
    suite.run()
    return 0 if suite.report() else 1


if __name__ == "__main__":
    sys.exit(main())
