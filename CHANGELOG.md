# Changelog
All notable changes to TerraLens are documented here.

---

## [0.1.4] - 2026-03-14

### Added
- **Infrastructure Blueprints** — new `🏗️ Build from Blueprint` mode accessible from the `➕ Add Resource` button
- 8 built-in blueprints that generate complete, production-ready Terraform configurations with fully interconnected resources:
  - 🌐 **Public Web Server** — VPC, public subnet, IGW, route table, security group (HTTP/SSH), EC2
  - 🔒 **Public + Private with NAT** — VPC, public + private subnets, IGW, EIP, NAT Gateway, bastion EC2, private app EC2
  - ⚖️ **Load Balanced Web Application** — VPC, 4 subnets, NAT, ALB, target group, launch template, Auto Scaling Group
  - 🏛️ **Three-Tier Architecture** — VPC, 6 subnets (public/app/db), NAT, ALB, 2× EC2 app servers, RDS multi-AZ
  - ☁️ **Static Website Hosting** — S3, CloudFront, OAI, ACM certificate, Route53 zone + A/CNAME records
  - ⚡ **Serverless API** — IAM role, Lambda, API Gateway v2, DynamoDB, S3 assets bucket
  - ☸️ **EKS Kubernetes Cluster** — VPC, 4 subnets with K8s tags, NAT, cluster + node IAM roles, EKS cluster, managed node group
  - 🔑 **Lambda + IAM Role** — IAM execution role, basic policy attachment, Lambda function
- All blueprint HCL uses Terraform resource references (no hardcoded IDs) so the generated config is immediately valid
- 3-step blueprint wizard: pick blueprint → configure fields (pre-filled defaults) → preview HCL → write file or write & apply

### Refactored
- Split monolithic `cli.py` (~2300 lines) into three focused modules:
  - `state.py` — app config loader, sample state, `load_state()`, `format_value()`
  - `catalog.py` — AWS resource catalog (334 resources), HCL templates, provider list, helper functions
  - `blueprints.py` — all 8 blueprint definitions and HCL renderer
  - `cli.py` — UI only, all Textual screens, widgets, `InsightTF` app, entry point
- Simplified `installer.py` — removed Python dependency installation steps, now handles Infracost setup only

---

## [0.1.3] - 2026-02-28

### Fixed
- Removed duplicate `main()` function at the top of `cli.py` that was shadowing the correct one at the bottom of the file
- Eliminated stale `from insight_tf.app import InsightTFApp` import that referenced a non-existent module
- Resolved `NameError: name 'InsightTFApp' is not defined` crash on binary startup — the CLI and binary now correctly launch the full `InsightTF` app with state file support

---

## [0.1.2] - 2026-02-27

### Fixed
- Fixed `ParserError: Missing expression after unary operator '--'` on Windows builds caused by PowerShell not supporting `\` line continuation
- Added `shell: bash` to the Build Binary step in the GitHub Actions workflow so both Ubuntu and Windows runners use the same shell
- Resolved Windows binary build failures — `insight-tf-windows-latest.exe` now builds and runs correctly

---

## [0.1.1] - 2026-02-27

### Fixed
- Fixed `ModuleNotFoundError: No module named 'rich._unicode_data.unicode17-0-0'` crash on startup
- Added `--collect-submodules rich` and `--collect-submodules textual` to PyInstaller build flags to ensure all lazy-loaded submodules are bundled into the binary
- Added `--hidden-import rich._unicode_data` to force inclusion of unicode data files that `rich` loads at runtime — resolves crashes on Arch Linux and other non-Ubuntu distributions

---

## [0.1.0] - 2026-02-26

### Added
- Initial public release of TerraLens (formerly Insight-TF)
- **Overview tab** — displays Terraform version, state serial, total resource count, provider count, and a full resource summary table
- **Manage tab** — interactive resource tree grouped by type with full attribute inspector
- **Plan** — streams real `terraform plan` output line-by-line into the terminal
- **Apply Now** — runs `terraform apply -auto-approve` and auto-reloads state on success
- **Cost Estimate** — Infracost-powered breakdown with per-resource monthly costs and totals
- **Drift Detection** — runs `terraform plan -refresh-only -detailed-exitcode` and reports drifted resources with status
- **Add Resource wizard** — 3-step flow: select provider → browse 334 AWS resources across 20 categories → configure fields and preview generated HCL
- **Destroy** — targeted destroy with confirmation modal before execution
- **State Reload** — press `r` at any time to reload state from disk without restarting
- Pre-built binaries available for Linux (Ubuntu/Arch/Fedora) and Windows
- Published to PyPI as `insight-tf`

---
