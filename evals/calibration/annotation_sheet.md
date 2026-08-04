# Calibration annotation sheet

Score each answer 1-5 for OVERALL quality (accuracy + completeness +
actionability), judging coverage of the required points — not length.
Record your scores in `human_labels.jsonl` (template alongside this
file; rename `human_labels.template.jsonl`, fill `human_score`).

## net-hub-spoke-001

**Q:** What network topology does the Cloud Adoption Framework recommend for Azure landing zones, and where do shared network services live?

**Required points:**
- hub-spoke topology is the recommendation
- shared services (firewall, gateways, DNS) are placed in the hub
- workloads are placed in spokes peered to the hub

**Answer:** The Cloud Adoption Framework recommends a hub‑spoke topology. Shared network services live in the hub virtual network (e.g., Azure Firewall, ExpressRoute/VPN gateways, DNS), while spokes host workloads and peer to the hub.

---

## net-peering-transitivity-002

**Q:** Two spoke virtual networks are each peered to the same hub. Can workloads in one spoke reach the other spoke directly through the hub, and what are the options if they need to communicate?

**Required points:**
- VNet peering is non-transitive
- traffic can be routed through a hub firewall/NVA with user-defined routes
- direct spoke-to-spoke peering or Virtual WAN are alternatives

**Answer:** No — peering is non‑transitive, so two spokes peered to the same hub cannot reach each other via the hub by default. To enable spoke‑to‑spoke communication you can:
- Route traffic through a network virtual appliance or Azure Firewall in the hub using user‑defined routes (so traffic is inspected/forwarded through the hub), 
- Create a direct peering between the two spokes, or
- Use Virtual WAN, whose virtual hub provides transitive routing.

---

## net-private-endpoints-003

**Q:** What is the difference between a service endpoint and a private endpoint for reaching Azure PaaS services, and which one does the Well-Architected security guidance favor?

**Required points:**
- service endpoints keep the service's public endpoint reachable, only sourced from the VNet
- private endpoints give the service a private IP inside the VNet
- private endpoints allow disabling public network access and are the recommended default

**Answer:** A private endpoint maps the PaaS service into your VNet via a private IP (Azure Private Link), allowing private-only access and the option to disable public network access. A service endpoint merely extends your VNet’s identity to the service over the Azure backbone, but the service is still reached at its public endpoint. The Well‑Architected/security guidance (and Azure security baselines for enterprise PaaS) favor using private endpoints, consistent with zero‑trust and identity‑first principles.

---

## net-er-vs-vpn-004

**Q:** When connecting on-premises datacenters to Azure, when should ExpressRoute be chosen over site-to-site VPN?

**Required points:**
- ExpressRoute is private connectivity with predictable latency and higher bandwidth
- VPN traverses the public internet and is cheaper/faster to establish
- VPN is commonly used as ExpressRoute failover

**Answer:** Choose ExpressRoute when you need a private, dedicated connection that does not traverse the public internet and that provides higher bandwidth, consistent latency and an availability SLA. Site-to-site VPN is quicker/cheaper and is frequently used for dev/test or as a failover for ExpressRoute, so use ExpressRoute when those higher performance, reliability and SLA guarantees are required.

---

## net-dns-plz-005

**Q:** How should private DNS be organized in an enterprise-scale landing zone so that private endpoints resolve correctly from both Azure and on-premises?

**Required points:**
- private DNS zones are centralized in the connectivity subscription and linked to VNets
- Azure Policy (DINE) automates private endpoint DNS registration
- on-premises resolution reaches Azure via DNS Private Resolver inbound endpoint (or forwarder VMs)

**Answer:** Keep the private-link zones central and shared, link them to the VNets, and forward them from on‑prem to Azure:

- Deploy the Private DNS zones for private link (for example privatelink.blob.core.windows.net) once in the connectivity subscription (not per subscription/workload).
- Link those zones to the hub and to the spoke VNets so private endpoints resolve from Azure workloads.
- Use DeployIfNotExists Azure Policy assignments so the required DNS records are created automatically when a private endpoint is provisioned.
- For hybrid name resolution, configure on‑premises DNS servers to conditionally forward the private-link zones to the inbound endpoint of an Azure DNS Private Resolver (or to legacy DNS forwarder VMs deployed in the hub).

---

## net-firewall-placement-006

**Q:** Where should Azure Firewall be deployed in a hub-spoke landing zone and how is spoke traffic forced through it?

**Required points:**
- firewall lives in AzureFirewallSubnet in the hub
- UDRs with next hop = firewall private IP force spoke traffic through it
- default route 0.0.0.0/0 sends internet-bound traffic to the firewall

**Answer:** Place the Firewall in the hub virtual network, in the dedicated AzureFirewallSubnet.  
Spoke subnets are given user‑defined route tables that route 0.0.0.0/0 (and optionally RFC1918 ranges for east‑west inspection) to the firewall's private IP as the next hop, forcing spoke traffic through the hub firewall. Route tables can be deployed/maintained at scale via Azure Policy or Azure Virtual Network Manager.

---

## gov-mgmt-groups-007

**Q:** What are Azure management groups and why do landing zones rely on them for governance?

**Required points:**
- management groups form a hierarchy above subscriptions
- policy and RBAC assigned at a management group are inherited by children
- this enables at-scale guardrails across many subscriptions

**Answer:** Azure management groups are a scope level above subscriptions that let you organize subscriptions into a hierarchy. Anything applied to a management group—such as Azure Policy assignments and role-based access control (RBAC) assignments—automatically cascades down to all child subscriptions and their resources.

Landing zones rely on management groups for governance because they provide a scalable way to enforce guardrails and consistent controls across many subscriptions. By defining a management group hierarchy (for example: platform, landing zones, sandbox, decommissioned) and placing new subscriptions under the appropriate group via subscription vending, landing zones ensure policies, budgets, networking and role assignments are applied automatically to the right subscriptions.

---

## gov-policy-initiative-008

**Q:** What is the difference between an Azure Policy definition and an initiative, and why assign initiatives instead of individual policies?

**Required points:**
- a definition is one rule; an initiative is a group of definitions
- initiatives are assigned and tracked as a single unit
- compliance reporting maps to a broader goal like a standard or baseline

**Answer:** A policy definition is a single compliance rule and its effect. An initiative (policy set) is a collection of policy definitions grouped and treated as one compliance objective. You assign initiatives instead of individual policies when you want to deploy and track multiple related rules together (for example a built‑in initiative for ISO 27001 or the Microsoft cloud security benchmark) and apply them at scale (landing zones commonly assign initiatives at management group scope).

---

## gov-policy-effects-009

**Q:** Compare the Azure Policy effects Deny, Audit, and DeployIfNotExists, and explain when DeployIfNotExists needs a managed identity and remediation task.

**Required points:**
- Deny blocks at request time; Audit only records non-compliance
- DeployIfNotExists deploys missing companion configuration automatically
- DINE assignments require a managed identity with RBAC
- existing resources require a remediation task

**Answer:** - Deny: blocks the request — a non-compliant resource request is prevented from succeeding.

- Audit: does not block the request — it writes a warning in the activity log and marks the resource as non‑compliant.

- DeployIfNotExists: when the policy condition is met it runs a template deployment to create or configure the missing resource (examples: diagnostics settings, DNS records for private endpoints, monitoring agents). That deployment runs under the policy assignment's managed identity, so that identity must hold whatever role assignments are required to perform the deployment. Also note: already‑existing non‑compliant resources are not fixed automatically by DeployIfNotExists unless you create a remediation task to run the deployment against those existing resources.

---

## gov-subscription-vending-010

**Q:** What is 'subscription democratization' (subscription vending) in Azure landing zones and what problem does it solve?

**Required points:**
- subscriptions are the unit of scale/isolation given to workload teams
- provisioning is automated and standardized (subscription vending IaC)
- guardrails come from management group inheritance, so autonomy does not sacrifice governance

**Answer:** Subscription democratization (aka subscription vending) is the landing‑zone principle and automated process that treats subscriptions — not resource groups — as the primary unit of management, scale and isolation, giving workload teams their own subscriptions. 

Subscription vending standardizes and automates creating those subscriptions with infrastructure as code and places each new subscription under the correct management group so that policies, budgets, networking and role assignments are applied automatically. 

It solves the problem of ad hoc, inconsistent provisioning and governance by enabling scalable isolation for teams while ensuring guardrails (Azure Policy and RBAC) are consistently inherited via the management group hierarchy.

---

## gov-tags-011

**Q:** What are resource tags used for in Azure governance and what is a recommended minimal tagging strategy?

**Required points:**
- tags drive cost allocation, ownership and automation
- a minimal set covers owner, cost center/project, environment
- Azure Policy can enforce or inherit required tags

**Answer:** Resource tags are metadata name–value pairs applied to Azure resources, resource groups and subscriptions. In governance they’re commonly used for things like cost chargeback and showback, identifying owners, driving automation (for example shutdown schedules) and marking data classification.

The recommended minimal tagging strategy (per CAF) is to define a required minimal tag set — typically workload or project, owner, environment and cost center — and enforce it with Azure Policy (for example using deny, append or modify effects), with tag inheritance from resource groups.

---

## gov-deployment-stacks-012

**Q:** Azure Blueprints was deprecated. What replaces its capabilities for deploying and protecting landing zone artifacts, and what does deployment stacks add over plain template deployments?

**Required points:**
- Blueprints is deprecated in favor of template specs and deployment stacks
- deployment stacks manage a set of deployed resources as one unit with unified lifecycle
- denySettings protect stack-managed resources from out-of-band modification or deletion

**Answer:** The guidance is to migrate to template specs and deployment stacks (they replace Blueprints’ deployment/protection capabilities). 

Deployment stacks go beyond a plain template deployment by becoming an Azure resource that manages the deployed resources as an atomic unit: updates reconcile the set of resources, deleting the stack can either delete or detach the managed resources, and denySettings (denyDelete or denyWriteAndDelete) prevent out‑of‑band changes—providing governance protection similar to blueprint resource locks.

---

## id-ca-mfa-013

**Q:** What is Entra ID Conditional Access and how does it relate to enforcing MFA in an enterprise environment?

**Required points:**
- Conditional Access evaluates signals and enforces controls at sign-in
- MFA is enforced via CA policies, not legacy per-user MFA
- policies can combine conditions like device compliance, location and risk

**Answer:** Entra ID Conditional Access are if‑then policies that evaluate signals (for example user/group membership, IP location, device state, application and real‑time risk) to make access decisions: allow, require multifactor authentication (MFA), require a compliant device, or block access. 

Microsoft recommends using Conditional Access as the mechanism to require MFA in an enterprise—replacing legacy per‑user MFA settings—because it can require MFA conditionally based on those signals. 

As a related operational note, organizations should create two or more cloud‑only emergency access accounts that have permanent Global Administrator assignments, are excluded from Conditional Access (so a misconfigured policy cannot lock out admins), do not rely on federated identity providers or a single user’s MFA device, and use phishing‑resistant methods (for example FIDO2 keys) with alerts on any sign‑in.

---

## id-pim-014

**Q:** What is Privileged Identity Management (PIM) and why do landing zone identity baselines require it for roles like Owner or Global Administrator?

**Required points:**
- PIM gives just-in-time, time-limited role activation instead of permanent assignments
- activation can require approval, MFA and justification, and is audited
- reduces standing privileged access and blast radius for high-privilege roles

**Answer:** Privileged Identity Management (PIM) is a Microsoft Entra feature that provides just‑in‑time privileged access: instead of permanent (standing) role assignments, users are made eligible and must activate a role for a limited time. Activations can require MFA, an approval, and a business justification; all activations and assignments are audited and can trigger access reviews.

Landing zone identity baselines require PIM for highly privileged roles (for example Global Administrator and subscription Owner) so those powerful roles are not persistently assigned and are subject to time‑limited activation, optional MFA/approval/justification, auditing, and periodic review—controls that reduce risk for critical directory and subscription privileges.

---

## id-mi-vs-sp-015

**Q:** When should a workload use a managed identity instead of a service principal with a client secret, and what is the key operational benefit?

**Required points:**
- managed identities are the default for Azure-hosted workloads calling Azure services
- no credential to store or rotate — the platform handles it
- for external systems (e.g. GitHub Actions) prefer workload identity federation over secrets

**Answer:** Use a managed identity when the workload runs on an Azure resource (VM, App Service, Function, etc.) rather than using a service principal with a client secret. The key operational benefit is that the identity is automatically managed by Entra ID so the app can obtain tokens without any credentials to store or rotate—no secrets, certificates, or keys need to be managed by the team.

---

## id-rbac-scope-016

**Q:** At which scopes can Azure RBAC roles be assigned, and what is the guidance on choosing the assignment scope?

**Required points:**
- four scopes: management group, subscription, resource group, resource
- assignments inherit down the hierarchy
- use the narrowest scope and least privilege

**Answer:** Azure RBAC roles can be assigned at these scopes: management group, subscription, resource group or a single resource. Assignments apply to the chosen scope and are inherited by all child scopes (e.g., management group → subscriptions → resource groups → resources).

Guidance on choosing scope: grant the least privilege needed at the narrowest workable scope, prefer assigning roles to groups rather than individual users, and use built-in roles unless a custom role is genuinely required. Management groups can be used to apply RBAC (and policy) at scale above subscriptions, with those assignments cascading down to contained subscriptions and their resources.

---

## id-break-glass-017

**Q:** What are emergency access ('break-glass') accounts in Entra ID and how should they be configured so a Conditional Access mistake cannot lock the organization out?

**Required points:**
- cloud-only accounts with standing Global Administrator access for emergencies
- excluded from Conditional Access (and not dependent on federation or user MFA methods)
- credentials are phishing-resistant and stored securely; sign-ins are alerted on

**Answer:** Emergency access (break‑glass) accounts are dedicated cloud‑only Entra ID accounts (onmicrosoft.com) that retain permanent Global Administrator assignments so they can be used to recover access if normal admin access is blocked.

How to configure them so a Conditional Access mistake cannot lock you out:
- Create two or more such accounts (not just one).
- Make them cloud‑only (onmicrosoft.com) so they do not depend on federated identity providers.
- Assign them permanent Global Administrator role membership.
- Exclude these accounts from Conditional Access policies so a misconfigured policy cannot block them.
- Do not depend on a single user’s MFA device; use phishing‑resistant authentication (Microsoft recommends FIDO2 security keys) kept in secure locations.
- Alert on any sign‑in or use of these accounts.

---

## sec-defense-depth-018

**Q:** How does the Well-Architected Framework describe defense in depth for an Azure workload?

**Required points:**
- multiple independent layers: identity, network, application, data, monitoring
- identity is treated as the primary security perimeter
- assume-breach mindset — each layer assumes previous layers can fail

**Answer:** It says to layer controls across identity and access management, network security, application security, data protection and security operations so that failure of any single control won’t expose the workload. It also emphasizes identity as the primary perimeter and following zero‑trust principles: verify explicitly, use least privilege, and assume breach.

---

## sec-key-vault-019

**Q:** What belongs in Azure Key Vault and what access model should applications use to read secrets from it?

**Required points:**
- secrets, keys and certificates are stored in Key Vault, never in code/config
- apps authenticate with managed identities, authorized via Azure RBAC
- network restriction (private endpoint/firewall) hardens access

**Answer:** Store secrets, encryption keys and certificates in Azure Key Vault (not secrets in app settings, code or pipelines). Applications should retrieve secrets at runtime by authenticating with a managed identity and be authorized using Azure RBAC (recommended over vault access policies).

---

## sec-defender-cspm-020

**Q:** What is the difference between the CSPM and workload protection capabilities of Microsoft Defender for Cloud?

**Required points:**
- CSPM assesses configuration/posture: secure score, recommendations
- Defender workload plans provide runtime threat detection and alerts
- free foundational CSPM vs paid Defender CSPM and per-resource Defender plans

**Answer:** Per the context: CSPM (cloud security posture management) is about continuously assessing your environment, giving a secure score and hardening recommendations based on the Microsoft cloud security benchmark. The foundational CSPM features are included free; the paid Defender CSPM plan adds attack‑path analysis and governance. By contrast, the workload protection capability consists of separate Defender plans for specific resources (Servers, App Service, Storage, SQL, Containers, Key Vault) that detect and alert on runtime threats to those workloads.

---
