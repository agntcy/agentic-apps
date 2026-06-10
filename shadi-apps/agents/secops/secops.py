import argparse
import os

from skills import fetch_security_alerts, generate_security_report, remediate_vulnerabilities, approve_queued_prs


def parse_args():
    parser = argparse.ArgumentParser(description="Run the SHADI SecOps agent")
    parser.add_argument(
        "--provider",
        choices=["google", "azure", "anthropic"],
        help="Override the LLM provider from SHADI (google, azure, anthropic)",
    )
    parser.add_argument(
        "--labels",
        default="security,cve,vulnerability",
        help="Comma-separated GitHub issue labels",
    )
    parser.add_argument(
        "--report-name",
        default="secops_security_report.md",
        help="Report filename in the workspace directory",
    )
    parser.add_argument(
        "--remediate",
        action="store_true",
        help="Attempt to patch critical vulnerabilities and open PRs",
    )
    parser.add_argument(
        "--repos",
        default=None,
        help="Comma-separated list of repos (owner/name) to scan/remediate (subset of allowlist)",
    )
    parser.add_argument(
        "--approve-prs",
        action="store_true",
        help="Create PRs from pending remediation approvals",
    )
    return parser.parse_args()


def run_secops_agent():
    print("== SHADI SecOps Autonomous Agent ==")
    args = parse_args()
    human_github = os.getenv("SHADI_HUMAN_GITHUB", "").strip() or None

    if args.approve_prs:
        result = approve_queued_prs()
        print("Status: approved")
        print("Result:", result)
        return

    fetch_result = fetch_security_alerts(labels=args.labels, repos=args.repos)
    print("Dependabot alerts:", fetch_result.get("dependabot_alerts"))
    print("Labeled issues:", fetch_result.get("labeled_issues"))
    print("Repos:", ", ".join(fetch_result.get("repos", [])))

    report_result = generate_security_report(
        report_name=args.report_name,
        provider=args.provider,
        human_github_handle=human_github,
    )
    print("Status:", report_result.get("status"))
    print("Report:", report_result.get("report_path"))
    if report_result.get("memory"):
        print("Memory:", report_result.get("memory"))

    if args.remediate:
        rem_result = remediate_vulnerabilities(human_github_handle=human_github, repos=args.repos)
        print("Remediation:", rem_result.get("remediation"))


if __name__ == "__main__":
    run_secops_agent()
