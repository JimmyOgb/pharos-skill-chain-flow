# Pharos Skill + Chain MCP Flow — Official Sources & Provenance

This document records the official sources, repository references, and live endpoints inspected and integrated for Pharos Task 12 (`skill-chain-mcp-flow`).

---

## 1. Official Web Endpoints

| Resource | Official URL | Purpose |
| :--- | :--- | :--- |
| **Pharos DevHub** | `https://www.pharos.xyz/devhub` | Official developer portal, tool discovery, and network settings. |
| **Pharos AI Platform** | `https://ai.pharos.xyz/` | Agent-native platform for Pharos tasks, skills, and MCP orchestration. |
| **Hosted Chain MCP Server** | `https://mcp.pharos.xyz/mcp` | Official hosted Model Context Protocol endpoint for Pharos. |
| **Pharos Pacific Mainnet RPC** | `https://rpc.pharos.xyz` | Default JSON-RPC endpoint serving Chain ID 1672. |
| **Pharos Pacific Explorer** | `https://www.pharosscan.xyz/` | Official block explorer for Pharos Mainnet. |
| **Pharos Atlantic Testnet RPC** | `https://atlantic.dplabs-internal.com` | Official testnet JSON-RPC endpoint serving Chain ID 688689. |
| **Pharos Atlantic Explorer** | `https://atlantic.pharosscan.xyz/` | Official block explorer for Pharos Atlantic Testnet. |

---

## 2. Official GitHub Repositories

| Repository | URL | Inspected Components |
| :--- | :--- | :--- |
| **Pharos Network MCP** | `https://github.com/PharosNetwork/pharos-mcp` | Protocol specifications, 14 tool definitions, SSE transport schema. |
| **Pharos SkillEngine** | `https://github.com/PharosNetwork/pharos-skill-engine` | `SKILL.md` specification standard, `assets/networks.json`, CLI guidelines. |
| **Pharos Examples** | `https://github.com/PharosNetwork/examples` | Code patterns for x402 micropayments, Foundry integrations, and smart contracts. |

---

## 3. Official SkillEngine Architecture Classification

Following source code and documentation inspection, the **Pharos SkillEngine** is classified as:

> **An Agent-Readable Skill Specification Standard**  
> SkillEngine is not a compiled proprietary runtime or black-box daemon. It is an agent-native architecture where skills are defined declaratively in `SKILL.md` with structured YAML frontmatter, execution pre-checks, capability tables, and reference documentation (`references/`). Agents and orchestrators consume these instructions to execute deterministic actions via standard developer tools (Python, Node.js, Foundry `cast`/`forge`).

---

## 4. Chain MCP Network Binding (Verified Fact)

- **Hosted Server Name:** `pharos-mcp-server`
- **Hosted Server Version:** `0.1.0`
- **Supported Protocol:** `2024-11-05`
- **Active Network:** **Pharos Pacific Mainnet (Chain ID 1672, Native Token: PROS)**
- **Atlantic Testnet Limitation:** The hosted endpoint `https://mcp.pharos.xyz/mcp` does not support Atlantic Testnet (`688689`). No network switching arguments exist in the tool schemas. Direct JSON-RPC to Atlantic (`https://atlantic.dplabs-internal.com`) may only be used for corroboration or diagnostic comparison, never as simulated MCP output.
