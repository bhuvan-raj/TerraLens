# TerraLens

> A terminal-based Terraform dashboard built with [Textual](https://textual.textualize.io/) — manage your infrastructure without leaving the command line.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Textual](https://img.shields.io/badge/Textual-0.47%2B-purple)
![Terraform](https://img.shields.io/badge/Terraform-1.0%2B-7B42BC?logo=terraform&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

---

## What is Insight-TF?

Insight-TF turns your Terraform workflow into a fully interactive TUI — browse state, inspect resources, plan, apply, detect drift, estimate costs, and scaffold new resources, all from a single terminal window.



https://github.com/user-attachments/assets/e22c8bd5-7eec-4d4a-98da-b0d26253b847



---

## Installation

Choose the method that suits you best.

## Note - To avail Infracost features, You have to install Infracost and supporting dependencies before the Application Installation

```
git clone https://github.com/bhuvan-raj/TerraLens.git

cd TerraLens

cd src/insight_tf

python installer.py #this script automatically installs and configures necessary dependecies for the application to run smoothly
```

## Install via pip

TerraLens is published on [PyPI](https://pypi.org/project/TerraLens/):

### Create Python Virtual Environment if necessary
```
python -m venv venv
source venv/bin/activate
```

### Install necessary dependency

```
pip install textual
```

### Install the Application
```bash
pip install TerraLens

or

pipx install TerraLens #Global installation
```

Then run it from your Terraform project directory:

```bash
cd ~/my-terraform-project
terralens

# Or pass the state file path explicitly
terralens /path/to/terraform.tfstate
```

## Download a Binary

Pre-built binaries are available for **Linux** and **Windows** on the [Releases page](https://github.com/bhuvan-raj/TerraLens/releases).

**Linux:**
```bash
# Download the latest binary
curl -L https://github.com/bhuvan-raj/TerraLens/releases/download/v0.1.3/insight-tf-linux -o terralens

# Make it executable
chmod +x terralens

# Move the executable to destination terraform project directory
mv terralens /my-terraform-project

# Run it from your Terraform project directory
cd ~/my-terraform-project

./terralens
```

**Windows:**
```powershell
# Download insight-tf-windows.exe from the Releases page
curl -L https://github.com/bhuvan-raj/TerraLens/releases/download/v0.1.3/insight-tf-windows.exe

# Move the nsight-tf-windows.exe to your terraform project directory

# then run:
.\insight-tf-windows.exe
```

> No Python, no pip, no dependencies — everything is bundled inside the binary.

---



---

### Option 3 — Install from Source

```bash
# 1. Clone the repository
git clone https://github.com/bhuvan-raj/TerraLens.git
cd TerraLens

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

cd src/insight_tf

python cli.py
```

---
> **No state file?** The app loads built-in sample AWS data so you can explore the UI immediately.


## Features

| Feature | Description |
|---|---|
| **📊 Overview** | Terraform version, state serial, total resources, provider count, full resource table |
| **🌲 Resource Tree** | Resources grouped by type — click any leaf to inspect all attributes |
| **🔍 Plan** | Streams real `terraform plan` output line-by-line |
| **⚡ Apply Now** | Runs `terraform apply -auto-approve` and reloads state on success |
| **💰 Cost Estimate** | Real Infracost pricing breakdown by resource with monthly totals |
| **🔄 Drift Detection** | `terraform plan -refresh-only -detailed-exitcode` with parsed summary |
| **➕ Add Resource** | 3-step wizard: provider → 334 AWS resources across 20 categories → HCL preview |
| **🗑️ Destroy** | Targeted destroy with confirmation modal before execution |
| **🔁 State Reload** | Press `r` to reload state from disk at any time |

---

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Required for modern typing syntax |
| Terraform | 1.0+ | Must be in `PATH` for Plan / Apply / Destroy / Drift |
| Infracost | any | Auto-installed by `setup.py` for Cost Estimate |
| OS | Linux / macOS / Windows | Tested on Ubuntu 22.04+, macOS 13+ |


---

## Installation Details

### Manual dependency install

```bash
pip install textual>=0.47.0 rich>=13.0.0
```

### Infracost manual install

```bash
# macOS
brew install infracost

# Linux
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh

# Authenticate (free — no credit card required)
infracost auth login
```

### Using a remote state backend

```bash
# Terraform Cloud / any backend
terraform state pull > terraform.tfstate
python insight_tf.py

# AWS S3 backend
aws s3 cp s3://your-bucket/env/prod/terraform.tfstate ./terraform.tfstate
python insight_tf.py
```

---

## Usage Guide

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `1` | Switch to Overview tab |
| `2` | Switch to Manage tab |
| `r` | Reload state from disk |
| `q` | Quit |
| `Esc` | Close any open modal or wizard |

### Overview Tab

Displays a high-level snapshot of your infrastructure:

- **Terraform version** — read directly from the state file
- **State serial** — increments on every apply; useful for auditing
- **Total resources** — count of all managed resources
- **Provider count** — number of unique providers in use
- **Resource table** — type, name, provider, and instance count for every resource

### Manage Tab

#### Resource Tree

The left panel shows all managed resources grouped by type. Click any resource leaf to load its full attribute map in the right panel, including nested maps and lists rendered as structured text.

#### Action Buttons

**➕ Add Resource**
Opens a 3-step wizard:
1. **Select provider** — AWS supported; Azure, GCP, Oracle, Docker, Kubernetes coming soon
2. **Browse resources** — 334 AWS resources across 20 categories with live search and category sidebar
3. **Configure & preview** — fill in fields, review the generated HCL, then choose:
   - **💾 Write File** — saves the `.tf` file and runs `terraform plan` to validate
   - **🚀 Write & Apply** — saves the file, plans, then immediately applies

**🔍 Plan**
Streams the full output of `terraform plan -no-color` into the output panel in real time.

**💰 Cost Estimate**
Runs `infracost breakdown --path . --format json` and renders a formatted cost table:

```
  Resource                                            Monthly
  ────────────────────────────────────────────────────────────
  aws_db_instance.main (db.t3.medium)               $  63.22
  aws_instance.web (t3.micro)                       $   8.47
  aws_s3_bucket.assets                          usage-based
  ────────────────────────────────────────────────────────────
  TOTAL MONTHLY ESTIMATE                            $  71.69
```

**🔄 Detect Drift**
Runs `terraform plan -refresh-only -detailed-exitcode` and reports:
- ✅ **No drift** — infrastructure matches state exactly
- ⚠️ **Drift found** — lists each drifted resource with its status (changed / deleted outside Terraform / created outside Terraform)
- ❌ **Error** — shows full stderr output for debugging

**🗑️ Destroy Selected**
Select a resource leaf in the tree, click Destroy. A confirmation modal displays the full resource address (`type.name`) before executing `terraform destroy -target=<addr> -auto-approve`.

**⚡ Apply Now**
Runs `terraform apply -auto-approve -no-color` from the project directory. Streams all output in real time and automatically reloads the resource tree on success.

---

## AWS Resource Catalog

The Add Resource wizard includes **334 AWS resources** across **20 categories**:

| Category | Highlights |
|---|---|
| Compute | EC2, Auto Scaling, AMIs, EBS, EIP, placement groups, key pairs |
| Containers | ECS clusters/services/tasks, ECR repositories, EKS clusters/node groups/Fargate |
| Serverless | Lambda functions, aliases, layers, function URLs, event source mappings |
| Storage | S3 (all 13 sub-resources), EFS, FSx (Lustre/Windows/ONTAP), Glacier |
| Database | RDS, Aurora, DynamoDB, ElastiCache, Redshift, Neptune, DocumentDB, MemoryDB, OpenSearch |
| Networking | VPC, subnets, NAT/Internet gateways, Transit Gateway, Direct Connect, flow logs |
| Load Balancing | ALB, NLB, Classic ELB, target groups, listeners, routing rules |
| DNS & CDN | Route 53 (zones/records/health checks/resolver), CloudFront, Global Accelerator |
| IAM & Security | IAM users/groups/roles/policies, KMS, Secrets Manager, SSM, ACM, WAFv2, GuardDuty, Cognito |
| Messaging & Queuing | SQS, SNS, Amazon MQ, Kinesis, MSK Kafka, EventBridge, Pipes |
| Monitoring & Logging | CloudWatch (alarms/dashboards/logs/metrics), X-Ray, CloudTrail, AWS Config |
| API & Integration | API Gateway v1/v2, AppSync GraphQL, Step Functions |
| DevOps & CI/CD | CodeBuild, CodeCommit, CodeDeploy, CodePipeline, CodeArtifact, CloudFormation |
| Machine Learning | SageMaker, Bedrock, Rekognition, Lex v2, Comprehend |
| Data & Analytics | Glue, Athena, EMR, Lake Formation, QuickSight |
| IoT | IoT Core (things/certificates/rules), IoT Events, IoT Analytics |
| Application Services | Elastic Beanstalk, Lightsail, Amplify, App Runner, Batch |
| Cost & Billing | Budgets, Cost Explorer categories, Cost & Usage Reports |
| Migration | DMS replication, DataSync, Migration Hub |
| Management | Organizations, RAM sharing, Resource Groups, SSM maintenance, Service Quotas |

Resources with full guided forms (labelled fields, defaults, placeholders):

`aws_s3_bucket` · `aws_instance` · `aws_vpc` · `aws_subnet` · `aws_security_group` · `aws_db_instance` · `aws_iam_role` · `aws_lambda_function`

All other resources generate a scaffold HCL block with a direct link to the Terraform registry documentation for that resource type.


---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and test: `textual run --dev insight_tf.py`
4. Open a pull request with a clear description of what you changed

For new AWS resources, add entries to `AWS_RESOURCE_CATALOG`. For new guided forms, also add to `RESOURCE_TEMPLATES`. Please keep both in alphabetical order within their category.

---

## License

MIT — see [LICENSE](./LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ using <a href="https://textual.textualize.io/">Textual</a> and <a href="https://www.terraform.io/">Terraform</a></sub>
</div>
