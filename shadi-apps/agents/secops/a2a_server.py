import argparse
import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path

from skills import (
    create_secops_session,
    load_secops_config,
    require_shadi_secret_value,
    fetch_security_alerts,
    generate_security_report,
    remediate_vulnerabilities,
    approve_queued_prs,
    get_latest_report,
    get_allowlist,
    get_agent_status,
)
from telemetry import tracer


def require_slima2a_packages():
    try:
        import slimrpc
        from a2a.server.agent_execution import AgentExecutor, RequestContext
        from a2a.server.events import EventQueue
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.types import AgentCapabilities, AgentCard, AgentSkill
        from a2a.types import TaskArtifactUpdateEvent, TaskState, TaskStatus, TaskStatusUpdateEvent
        from a2a.utils import new_text_artifact
        from slima2a.handler import SRPCHandler
        from slima2a.types.a2a_pb2_slimrpc import add_A2AServiceServicer_to_server
    except ImportError as exc:
        raise RuntimeError(
            "Missing SLIM A2A dependencies. Install: uv pip install slima2a slimrpc a2a"
        ) from exc

    return {
        "slimrpc": slimrpc,
        "AgentExecutor": AgentExecutor,
        "RequestContext": RequestContext,
        "EventQueue": EventQueue,
        "DefaultRequestHandler": DefaultRequestHandler,
        "InMemoryTaskStore": InMemoryTaskStore,
        "AgentCapabilities": AgentCapabilities,
        "AgentCard": AgentCard,
        "AgentSkill": AgentSkill,
        "TaskArtifactUpdateEvent": TaskArtifactUpdateEvent,
        "TaskState": TaskState,
        "TaskStatus": TaskStatus,
        "TaskStatusUpdateEvent": TaskStatusUpdateEvent,
        "new_text_artifact": new_text_artifact,
        "SRPCHandler": SRPCHandler,
        "add_A2AServiceServicer_to_server": add_A2AServiceServicer_to_server,
    }


def parse_command(raw):
    if not raw:
        return {"command": "scan"}
    raw = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"command": raw.lower()}


async def emit_text(event_queue, context, text, types):
    message = types["TaskArtifactUpdateEvent"](
        context_id=context.context_id,
        task_id=context.task_id,
        artifact=types["new_text_artifact"](name="secops_update", text=text),
    )
    await event_queue.enqueue_event(message)


async def emit_status(event_queue, context, state, types, final=False):
    status = types["TaskStatusUpdateEvent"](
        context_id=context.context_id,
        task_id=context.task_id,
        status=types["TaskStatus"](state=state),
        final=final,
    )
    await event_queue.enqueue_event(status)


async def run_scan(command):
    provider = command.get("provider")
    labels = command.get("labels", "security,cve,vulnerability")
    if isinstance(labels, list):
        labels = ",".join(labels)
    report_name = command.get("report_name", "secops_security_report.md")
    provider = command.get("provider")
    repos = command.get("repos")
    if isinstance(repos, list):
        repos = ",".join(repos)
    human_github = command.get("human_github") or os.getenv("SHADI_HUMAN_GITHUB", "").strip() or None
    result = await asyncio.to_thread(fetch_security_alerts, labels=labels, repos=repos)
    if result.get("status") != "ok":
        return result
    return await asyncio.to_thread(
        generate_security_report,
        report_name=report_name,
        provider=provider,
        human_github_handle=human_github,
    )


async def run_remediate(command):
    labels = command.get("labels", "security,cve,vulnerability")
    if isinstance(labels, list):
        labels = ",".join(labels)
    report_name = command.get("report_name", "secops_security_report.md")
    provider = command.get("provider")
    create_prs = bool(command.get("create_prs", False))
    repos = command.get("repos")
    if isinstance(repos, list):
        repos = ",".join(repos)
    human_github = command.get("human_github") or os.getenv("SHADI_HUMAN_GITHUB", "").strip() or None
    result = await asyncio.to_thread(fetch_security_alerts, labels=labels, repos=repos)
    if result.get("status") != "ok":
        return result
    report_result = await asyncio.to_thread(
        generate_security_report,
        report_name=report_name,
        provider=provider,
        human_github_handle=human_github,
    )
    rem_result = await asyncio.to_thread(
        remediate_vulnerabilities,
        human_github_handle=human_github,
        create_prs=create_prs,
        repos=repos,
    )
    report_result["remediation"] = rem_result.get("remediation")
    return report_result


async def run_approve_prs():
    return await asyncio.to_thread(approve_queued_prs)


async def run_get_report(command):
    report_name = command.get("report_name", "secops_security_report.md")
    return await asyncio.to_thread(get_latest_report, report_name)


async def run_status():
    return await asyncio.to_thread(get_agent_status)


async def run_allowlist():
    return await asyncio.to_thread(get_allowlist)


def build_agent_card(types):
    skill = types["AgentSkill"](
        id="secops",
        name="secops",
        description="SecOps agent with scan/remediate/approve/report/status commands.",
        tags=["secops", "security", "remediation"],
        examples=["help", "scan", "remediate", "approve_prs", "report", "status"],
    )
    return types["AgentCard"](
        name="secops_agent",
        description="SecOps autonomous remediation agent",
        url="http://localhost:10001/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=types["AgentCapabilities"](streaming=True),
        skills=[skill],
    )


def resolve_slim_config():
    config_path, config = load_secops_config()
    secops_config = config.get("secops", {})
    store, session = create_secops_session()
    secret_key = secops_config.get("slim_shared_secret_key", "secops/slim_shared_secret")
    shared_secret = require_shadi_secret_value(
        store,
        session,
        secret_key,
        "SLIM shared secret",
    )
    tls_insecure = bool(secops_config.get("slim_tls_insecure", True))
    tls_cert = os.getenv("SLIM_TLS_CERT", "").strip()
    tls_key = os.getenv("SLIM_TLS_KEY", "").strip()
    tls_ca = os.getenv("SLIM_TLS_CA", "").strip()
    if not tls_insecure and (not tls_cert or not tls_key or not tls_ca):
        raise RuntimeError("SLIM mTLS requires SLIM_TLS_CERT, SLIM_TLS_KEY, and SLIM_TLS_CA")
    return {
        "identity": secops_config.get("slim_identity", "agntcy/secops/agent"),
        "endpoint": secops_config.get("slim_endpoint", "http://localhost:47357"),
        "shared_secret": shared_secret,
        "insecure": tls_insecure,
        "tls_cert": tls_cert,
        "tls_key": tls_key,
        "tls_ca": tls_ca,
    }


def create_executor(types):
    AgentExecutor = types["AgentExecutor"]

    class SecopsExecutor(AgentExecutor):
        async def execute(self, context, event_queue):
            print(f"[SecopsExecutor.execute] user_input={context.get_user_input()!r}", flush=True)
            command = parse_command(context.get_user_input())
            command_name = command.get("command", "unknown")
            with tracer.start_as_current_span("secops.command") as span:
                span.set_attribute("secops.command", command_name)
                span.set_attribute("task.id", str(context.task_id))
                span.add_event("command.received", {"command": command_name})
                await emit_status(event_queue, context, types["TaskState"].working, types)
                await emit_text(event_queue, context, f"Command: {command}", types)
                try:
                    if command.get("command") in ("scan", "run_scan"):
                        result = await run_scan(command)
                    elif command.get("command") in ("remediate", "run_remediate"):
                        result = await run_remediate(command)
                    elif command.get("command") in ("approve_prs", "approve"):
                        result = await run_approve_prs()
                    elif command.get("command") in ("report", "get_report"):
                        result = await run_get_report(command)
                    elif command.get("command") in ("status", "info"):
                        result = await run_status()
                    elif command.get("command") in ("allowlist", "repos"):
                        result = await run_allowlist()
                    elif command.get("command") in ("help", "commands"):
                        result = {
                            "commands": {
                                "scan": {
                                    "description": "Collect Dependabot alerts and security issues.",
                                    "payload": {
                                        "command": "scan",
                                        "labels": "security,cve,vulnerability",
                                        "provider": "(optional: override LLM provider)",
                                        "report_name": "secops_security_report.md",
                                    },
                                },
                                "remediate": {
                                    "description": "Run remediation planning. Set create_prs=true and human_github=<handle> to open PRs via gh CLI.",
                                    "payload": {
                                        "command": "remediate",
                                        "labels": "security,cve,vulnerability",
                                        "provider": "(optional: override LLM provider)",
                                        "report_name": "secops_security_report.md",
                                        "create_prs": False,
                                        "human_github": "(optional: GitHub handle for fork/PR ownership, or set SHADI_HUMAN_GITHUB)",
                                    },
                                },
                                "approve_prs": {
                                    "description": "Approve and finalize pending remediation PRs.",
                                    "payload": {"command": "approve_prs"},
                                },
                                "report": {
                                    "description": "Return the latest report content.",
                                    "payload": {
                                        "command": "report",
                                        "report_name": "secops_security_report.md",
                                    },
                                },
                                "status": {
                                    "description": "Show SLIM + workspace configuration and allowlist.",
                                    "payload": {"command": "status"},
                                },
                                "allowlist": {
                                    "description": "List allowlisted repositories.",
                                    "payload": {"command": "allowlist"},
                                },
                            },
                            "notes": "Payloads can be plain text commands or JSON objects.",
                        }
                    else:
                        result = {"status": "unknown_command", "command": command}
                    span.add_event("command.completed", {"command": command_name, "status": "success"})
                    await emit_text(event_queue, context, json.dumps(result, indent=2), types)
                    await emit_status(event_queue, context, types["TaskState"].completed, types, final=True)
                except Exception as exc:
                    span.record_exception(exc)
                    if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                        err_msg = f"{exc}\nstderr: {exc.stderr.strip()}"
                    else:
                        err_msg = str(exc)
                    span.add_event("command.failed", {"command": command_name, "error": err_msg})
                    await emit_text(event_queue, context, f"error: {err_msg}", types)
                    await emit_status(event_queue, context, types["TaskState"].failed, types, final=True)

        async def cancel(self, context, event_queue):
            await emit_text(event_queue, context, "cancel not supported", types)
            await emit_status(event_queue, context, types["TaskState"].failed, types, final=True)

    return SecopsExecutor()


async def main():
    logging.getLogger("a2a.utils.telemetry").setLevel(logging.ERROR)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    types = require_slima2a_packages()
    slimrpc = types["slimrpc"]

    slim_config = resolve_slim_config()
    agent_card = build_agent_card(types)

    request_handler = types["DefaultRequestHandler"](
        agent_executor=create_executor(types),
        task_store=types["InMemoryTaskStore"](),
    )

    servicer = types["SRPCHandler"](agent_card, request_handler)
    tls_config = {
        "insecure": bool(slim_config["insecure"]),
    }
    if not slim_config["insecure"]:
        tls_config["source"] = {
            "type": "file",
            "cert": slim_config["tls_cert"],
            "key": slim_config["tls_key"],
        }
        tls_config["ca_source"] = {
            "type": "file",
            "path": slim_config["tls_ca"],
        }

    server = await slimrpc.Server.from_slim_app_config(
        slim_app_config=slimrpc.SLIMAppConfig(
            identity=slim_config["identity"],
            slim_client_config={
                "endpoint": slim_config["endpoint"],
                "tls": tls_config,
            },
            shared_secret=slim_config["shared_secret"],
        )
    )
    types["add_A2AServiceServicer_to_server"](servicer, server)
    print(f"SecOps A2A server ready (agent_id={slim_config['identity']}, endpoint={slim_config['endpoint']})", flush=True)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
