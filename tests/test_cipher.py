"""Cipher prototype tests — stdlib unittest, no dependencies.

Covers: task schema validation, memory store round-trip, sandbox exec
policy (blocks disallowed commands / escapes / secrets), evidence checks,
spawn-budget enforcement (depth, total, cycles, no escalation), loop
termination (bounded retries), and the ReAct JSON protocol parsing.

Run:  python -m unittest discover -s tests -v   (from the cipher/ directory)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import _extract_json, AgentError  # noqa: E402
from src.config import Config, load_config  # noqa: E402
from src.loop import Loop  # noqa: E402
from src.memory import MemoryStore  # noqa: E402
from src.roles import get_role, load_roles_index  # noqa: E402
from src.tasks import TaskError, validate_task  # noqa: E402
from src.tools import (  # noqa: E402
    ToolBelt,
    ToolDenied,
    ToolError,
    check_criterion,
)

REPO = Path(__file__).resolve().parent.parent


def _cfg(**kw):
    base = dict(api_key=None, dry_run=True)
    base.update(kw)
    return Config(**base)


def _belt(sandbox: Path, role="builder", tools=None, **kw):
    mem = MemoryStore(sandbox, "test-run")
    return ToolBelt(
        cfg=_cfg(), sandbox_root=sandbox, memory=mem, run_id="test-run",
        role=role, agent_id="root", depth=0,
        tools_allowed=tools or ["read_file", "write_file", "list_dir", "run_cmd",
                                "memory_append", "memory_read"],
        **kw,
    )


VALID_TASK = {
    "id": "t1",
    "goal": "do a thing",
    "success_criteria": [
        {"id": "c1", "description": "file exists", "type": "file_exists", "path": "a.txt"},
        {"id": "c2", "description": "cmd works", "type": "command",
         "cmd": ["python3", "-c", "print('hi')"], "expect_in_output": "hi"},
    ],
}


class TestTaskSchema(unittest.TestCase):
    def test_valid_task_passes(self):
        validate_task(VALID_TASK)

    def test_missing_goal_fails(self):
        bad = dict(VALID_TASK); del bad["goal"]
        with self.assertRaises(TaskError):
            validate_task(bad)

    def test_empty_criteria_fails(self):
        bad = dict(VALID_TASK, success_criteria=[])
        with self.assertRaises(TaskError):
            validate_task(bad)

    def test_unknown_criterion_type_fails(self):
        bad = json.loads(json.dumps(VALID_TASK))
        bad["success_criteria"][0]["type"] = "vibes"
        with self.assertRaises(TaskError):
            validate_task(bad)

    def test_file_exists_needs_path(self):
        bad = json.loads(json.dumps(VALID_TASK))
        del bad["success_criteria"][0]["path"]
        with self.assertRaises(TaskError):
            validate_task(bad)


class TestMemory(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            mem = MemoryStore(Path(td), "r1")
            fid = mem.append_finding("builder", {"claim": "built it", "evidence": "a.txt"})
            findings = mem.read_findings()
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["claim"], "built it")
            self.assertTrue(findings[0]["id"].startswith("root-"))
            self.assertEqual(fid, findings[0]["id"])

    def test_spawn_namespacing(self):
        with tempfile.TemporaryDirectory() as td:
            mem = MemoryStore(Path(td), "r1")
            mem.append_finding("coordinator", {"claim": "root claim"}, agent_id="root")
            mem.append_finding("specialist:x", {"claim": "child claim"}, agent_id="s01-abc")
            root_view = mem.read_findings(agent_id="root")
            child_view = mem.read_findings(agent_id="s01-abc")
            self.assertEqual(len(root_view), 1)   # root sees only root findings
            self.assertEqual(len(child_view), 2)  # child sees root + own

    def test_spawn_tree_record(self):
        with tempfile.TemporaryDirectory() as td:
            mem = MemoryStore(Path(td), "r1")
            mem.record_spawn({"spawn_id": "s01", "specialist": "test-writer", "status": "running"})
            mem.update_spawn("s01", status="completed")
            tree = mem.read_spawn_tree()
            self.assertEqual(tree[0]["status"], "completed")


class TestSandbox(unittest.TestCase):
    def test_write_and_read_inside_sandbox(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td))
            belt.call("write_file", {"path": "sub/a.txt", "content": "hello"})
            res = belt.call("read_file", {"path": "sub/a.txt"})
            self.assertIn("hello", res["content"])

    def test_path_escape_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td))
            with self.assertRaises(ToolDenied):
                belt.call("read_file", {"path": "../outside.txt"})
            with self.assertRaises(ToolDenied):
                belt.call("write_file", {"path": "/etc/evil", "content": "x"})

    def test_disallowed_command_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td))
            with self.assertRaises(ToolDenied):
                belt.call("run_cmd", {"argv": ["curl", "https://example.com"]})
            with self.assertRaises(ToolDenied):
                belt.call("run_cmd", {"argv": ["rm", "-rf", "/"]})

    def test_allowed_command_works(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td))
            res = belt.call("run_cmd", {"argv": ["python3", "-c", "print('ok')"]})
            self.assertIn("ok", res["stdout"])
            self.assertEqual(res["exit_code"], 0)

    def test_secret_like_arg_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td))
            with self.assertRaises(ToolDenied):
                belt.call("run_cmd", {"argv": ["grep", "api_key", "f.txt"]})

    def test_shell_metachars_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td))
            with self.assertRaises(ToolDenied):
                belt.call("run_cmd", {"argv": ["ls", ";", "evil"]})

    def test_tool_not_in_role_subset_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td), role="critic",
                         tools=["read_file", "memory_read"])
            with self.assertRaises(ToolDenied):
                belt.call("write_file", {"path": "x.txt", "content": "y"})

    def test_git_write_subcommand_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            belt = _belt(Path(td))
            with self.assertRaises(ToolDenied):
                belt.call("run_cmd", {"argv": ["git", "push"]})


class TestEvidence(unittest.TestCase):
    def test_file_exists(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td); (p / "a.txt").write_text("x")
            ok, _ = check_criterion({"type": "file_exists", "path": "a.txt"}, p)
            self.assertTrue(ok)
            ok, _ = check_criterion({"type": "file_exists", "path": "nope.txt"}, p)
            self.assertFalse(ok)

    def test_command_output_match(self):
        with tempfile.TemporaryDirectory() as td:
            ok, detail = check_criterion(
                {"type": "command", "cmd": ["python3", "-c", "print('Hello, Cipher!')"],
                 "expect_in_output": "Hello, Cipher!"}, Path(td))
            self.assertTrue(ok, detail)
            ok, _ = check_criterion(
                {"type": "command", "cmd": ["python3", "-c", "print('bye')"],
                 "expect_in_output": "Hello, Cipher!"}, Path(td))
            self.assertFalse(ok)


class TestRoles(unittest.TestCase):
    def test_all_roles_load(self):
        idx = load_roles_index()
        for r in ("coordinator", "research", "builder", "analyst", "critic", "verifier"):
            self.assertIn(r, idx["roles"])
            self.assertIn("response_contract", idx["roles"][r])

    def test_unknown_role_raises(self):
        with self.assertRaises(KeyError):
            get_role("hacker")


class TestReactProtocol(unittest.TestCase):
    def test_extract_plain_json(self):
        obj = _extract_json('{"type": "final", "result": {}}')
        self.assertEqual(obj["type"], "final")

    def test_extract_code_fence(self):
        obj = _extract_json('```json\n{"type": "tool_call", "tool": "read_file", "args": {}}\n```')
        self.assertEqual(obj["tool"], "read_file")

    def test_malformed_raises(self):
        with self.assertRaises(AgentError):
            _extract_json("hello there, no json at all")


class TestSpawnPolicy(unittest.TestCase):
    def _registry(self, **cfg_kw):
        cfg = _cfg(**cfg_kw)
        mem = MemoryStore(REPO, "spawn-test")
        from src.loop import SpawnRegistry
        logs = []
        return SpawnRegistry(cfg, mem, log=logs.append), mem

    def _parent_belt(self, cfg, mem, depth=0, tools=None):
        return ToolBelt(cfg=cfg, sandbox_root=REPO, memory=mem, run_id="spawn-test",
                        role="coordinator", agent_id="root", depth=depth,
                        tools_allowed=tools or ["spawn_subagent", "write_file",
                                                "read_file", "memory_append", "memory_read"],
                        spawn_handler=None, tool_budget=20)

    def test_depth_limit_enforced(self):
        reg, mem = self._registry(max_spawn_depth=0)
        belt = self._parent_belt(reg.cfg, mem)
        reg.handle = reg.handle  # bound
        # patch: registry.handle needs spawn_handler wired; call directly
        with self.assertRaises(ToolDenied):
            reg.handle({"specialist": "x", "goal": "g", "tools": []}, belt)

    def test_total_limit_enforced(self):
        reg, mem = self._registry(max_subagents_per_run=0)
        belt = self._parent_belt(reg.cfg, mem)
        with self.assertRaises(ToolDenied):
            reg.handle({"specialist": "x", "goal": "g", "tools": []}, belt)

    def test_no_permission_escalation(self):
        reg, mem = self._registry()
        belt = self._parent_belt(reg.cfg, mem)
        with self.assertRaises(ToolDenied):
            reg.handle({"specialist": "x", "goal": "g", "tools": ["write_file", "nukes"]}, belt)

    def test_cycle_detection(self):
        reg, mem = self._registry()
        # fake an ancestor chain: s01 (test-writer, goal g) parented by root
        mem.record_spawn({"spawn_id": "s01-aaa", "parent_id": "root",
                          "specialist": "test-writer", "goal": "g", "depth": 1})
        belt = self._parent_belt(reg.cfg, mem, depth=1)
        belt.agent_id = "s01-aaa"
        with self.assertRaises(ToolDenied):
            reg.handle({"specialist": "test-writer", "goal": "g", "tools": []}, belt)


class TestLoopTermination(unittest.TestCase):
    def test_always_fail_terminates(self):
        """A task that can never pass must end FAIL after bounded retries."""
        cfg = _cfg()
        task = {
            "id": "impossible",
            "goal": "impossible goal",
            "budget": {"max_retries": 1, "max_steps": 20},
            "success_criteria": [
                {"id": "never", "description": "never exists",
                 "type": "file_exists", "path": "nope/never.txt"},
            ],
        }
        loop = Loop(cfg, task, run_id="term-test")
        # point the loop at a temp sandbox so it can't touch the real repo
        import src.loop as loop_mod
        orig = loop_mod.REPO_ROOT
        with tempfile.TemporaryDirectory() as td:
            loop_mod.REPO_ROOT = Path(td)
            try:
                # rebuild loop pieces that captured REPO_ROOT
                loop2 = Loop(cfg, task, run_id="term-test-2")
                loop2.memory = MemoryStore(Path(td), "term-test-2")
                result = loop2.run()
            finally:
                loop_mod.REPO_ROOT = orig
        self.assertEqual(result.verdict, "FAIL")
        self.assertLessEqual(result.retries_used, 2)  # bounded: max_retries(1) + final
        self.assertLessEqual(result.steps, 20)
        loop._log_fh.close()

    def test_config_dry_run_when_no_key(self):
        os.environ.pop("CIPHER_API_KEY", None)
        os.environ.pop("CIPHER_DRY_RUN", None)
        cfg = load_config()
        self.assertTrue(cfg.dry_run)


if __name__ == "__main__":
    unittest.main()
