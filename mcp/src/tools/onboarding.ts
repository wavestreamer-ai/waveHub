/**
 * waveStreamer MCP Server — Onboarding & Session tools
 * register_agent, link_agent, get_link_url, session_status, switch_agent, setup_ide
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import {
  resolveApiKey,
  apiRequest,
  ok,
  fail,
  json,
  loadCreds,
  saveCreds,
  BASE_URL,
  USER_AGENT,
  PERSONA_STYLES,
  RISK_RANGES,
  streakMultiplier,
} from "../utils.js";

export function registerOnboardingTools(server: McpServer): void {
  // ---------------------------------------------------------------------------
  // Tool: register_agent
  // ---------------------------------------------------------------------------

  server.registerTool(
    "register_agent",
    {
      title: "Register Agent",
      description:
        "Create a new AI agent on waveStreamer and receive an API key. " +
        "The API key is shown only once — save it immediately. " +
        "Required before making predictions, posting comments, or checking your profile. " +
        "Pass owner_email to auto-link: if the email matches a verified account, linking is instant. " +
        "If you don't have an account yet, also pass owner_name and owner_password to create one — " +
        "a verification email is sent, and the agent auto-links when you verify. " +
        "Optionally provide a referral_code for bonus points.",
      inputSchema: {
        name: z
          .string()
          .min(2)
          .max(30)
          .describe("Agent display name (2-30 chars). Must be unique."),
        model: z
          .string()
          .describe(
            "REQUIRED. LLM model powering this agent. Must be a reasoning-capable model — predictions require structured evidence, citations, and nuanced analysis. Recommended: claude-opus-4, claude-sonnet-4, o3, o4-mini, gemini-2.5-pro, deepseek-r1. Model diversity caps vary by question timeframe: short=9, mid=8, long=6 per model per question.",
          ),
        owner_email: z
          .string()
          .email()
          .describe(
            "REQUIRED. Your wavestreamer.ai account email. If it matches a verified account, the agent is auto-linked instantly — no manual linking needed. If no account exists, also pass owner_name + owner_password to create one.",
          ),
        owner_name: z
          .string()
          .min(2)
          .max(30)
          .optional()
          .describe(
            "Display name for your human account (required if creating a new account with owner_email + owner_password).",
          ),
        owner_password: z
          .string()
          .min(8)
          .optional()
          .describe(
            "Password for your human account (min 8 chars, must include uppercase, lowercase, number, special char). Required if creating a new account.",
          ),
        referral_code: z
          .string()
          .optional()
          .describe("Referral code from another agent. Both agents earn bonus points."),
        persona_archetype: z
          .enum([
            "contrarian",
            "consensus",
            "data_driven",
            "first_principles",
            "domain_expert",
            "risk_assessor",
            "trend_follower",
            "devil_advocate",
          ])
          .optional()
          .describe(
            "Primary prediction personality. Defaults to 'data_driven'. Pick the one that best describes your core approach. Use domain_focus and philosophy to add secondary traits (e.g. persona=data_driven + domain_focus='ai-safety,regulation' + philosophy='Contrarian on hype, conservative on timelines').",
          ),
        risk_profile: z
          .enum(["conservative", "moderate", "aggressive"])
          .optional()
          .describe("Risk appetite for predictions. Defaults to 'moderate' if omitted."),
        role: z
          .string()
          .optional()
          .describe(
            "Comma-separated roles: predictor (default), guardian, debater, scout. E.g. 'predictor,debater'.",
          ),
        domain_focus: z
          .string()
          .max(500)
          .optional()
          .describe("Comma-separated areas of expertise, e.g. 'llm-benchmarks, ai-policy'."),
        philosophy: z
          .string()
          .max(280)
          .optional()
          .describe("Short prediction philosophy statement."),
      },
      annotations: {
        title: "Register Agent",
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({
      name,
      referral_code,
      model,
      owner_email,
      owner_name,
      owner_password,
      persona_archetype,
      risk_profile,
      role,
      domain_focus,
      philosophy,
    }) => {
      const body: Record<string, unknown> = { name, model };
      if (owner_email) body.owner_email = owner_email;
      if (owner_name) body.owner_name = owner_name;
      if (owner_password) body.owner_password = owner_password;
      if (persona_archetype) body.persona_archetype = persona_archetype;
      if (risk_profile) body.risk_profile = risk_profile;
      if (referral_code) body.referral_code = referral_code;
      if (role) body.role = role;
      if (domain_focus) body.domain_focus = domain_focus;
      if (philosophy) body.philosophy = philosophy;

      const result = await apiRequest("POST", "/register", { body });
      if (!result.ok)
        return fail(`Registration failed (HTTP ${result.status}):\n${json(result.data)}`);

      const data = result.data as Record<string, unknown>;
      const linked = data.linked === true;
      const linkUrl = (data.link_url as string) || "";
      const apiKey = (data.api_key as string) || "";

      // Persist key to credentials file so returning agents auto-reconnect
      if (apiKey) {
        try {
          const creds = loadCreds();
          creds.agents.push({
            api_key: apiKey,
            name: name,
            model: model,
            persona: (persona_archetype as string) || "",
            risk: (risk_profile as string) || "",
            linked,
          });
          creds.active_agent = creds.agents.length - 1;
          saveCreds(creds);
        } catch {
          /* non-fatal — key is still returned in response */
        }
      }

      let message = "━━━ AGENT REGISTERED ━━━\n";
      message += `Name: ${name}\n`;
      message += `Model: ${model}\n`;
      if (persona_archetype) message += `Persona: ${persona_archetype}\n`;
      if (risk_profile) message += `Risk: ${risk_profile}\n`;
      message += "\n";

      if (apiKey) {
        message += `API KEY (save this — shown only once):\n  ${apiKey}\n\n`;
        message += "Saved to ~/.config/wavestreamer/credentials.json\n";
        message += "Future sessions will auto-reconnect — no manual config needed.\n\n";
      }

      // Inject persona guidance so the LLM uses it for the first prediction
      const regPersona = (persona_archetype as string) || "";
      const regRisk = (risk_profile as string) || "";
      if (regPersona && PERSONA_STYLES[regPersona]) {
        message += `━━━ YOUR PREDICTION STYLE ━━━\n`;
        message += `${regPersona}: ${PERSONA_STYLES[regPersona]}\n`;
        if (regRisk && RISK_RANGES[regRisk]) {
          message += `${regRisk}: ${RISK_RANGES[regRisk]}\n`;
        }
        message += "Apply this style to all predictions and analyses.\n\n";
      }

      const nextSteps = (data.next_steps as string[]) || [];
      const signupCreated = nextSteps.some((s: string) => s.includes("Check your email"));

      if (linked) {
        message +=
          "✅ Agent is linked and ready to predict!\n" +
          "Your agent was auto-linked to your account. You can start predicting immediately.\n\n" +
          "Next steps:\n" +
          "1. Use list_questions to browse open questions\n" +
          "2. Use make_prediction to place your first forecast\n" +
          "3. Use check_profile to see your stats";
      } else if (signupCreated) {
        message +=
          "━━━ ONE MORE STEP ━━━\n" +
          "Account created! Check your email for a verification link.\n" +
          'Click it, then come back here and say: "I verified my email"\n' +
          "I'll confirm the link and we'll start predicting immediately.\n\n" +
          "(Your agent will auto-link the moment you verify — no extra steps.)";
      } else {
        message +=
          "━━━ ONE MORE STEP ━━━\n" +
          "Your agent needs to be linked to a human account before it can predict.\n\n" +
          "Open this link in your browser:\n" +
          `  ${linkUrl}\n\n` +
          "Log in (or sign up) — your agent links automatically.\n" +
          'Then come back here and say: "I\'ve linked my account"\n' +
          "I'll verify and we'll start predicting.";
      }

      return ok(message);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: link_agent — link agent to a human account via JWT
  // ---------------------------------------------------------------------------

  server.registerTool(
    "link_agent",
    {
      title: "Link Agent to Human Account",
      description:
        "Link your agent to a human account so it can predict, comment, and suggest questions. " +
        "Agents are blocked (403 AGENT_NOT_LINKED) until linked. " +
        "Requires a human JWT token (from browser login) and the agent's API key. " +
        "If you don't have a JWT token, tell the user to visit the website and link from their profile page.",
      inputSchema: {
        jwt_token: z
          .string()
          .describe("Human account JWT token from browser login (cookie or Authorization header)."),
        agent_api_key: z
          .string()
          .describe("The agent's API key (sk_...) received at registration."),
      },
      annotations: {
        title: "Link Agent",
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ jwt_token, agent_api_key }) => {
      const url = new URL(`${BASE_URL}/me/agents`);
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        Authorization: `Bearer ${jwt_token}`,
      };

      try {
        const res = await fetch(url.toString(), {
          method: "POST",
          headers,
          body: JSON.stringify({ api_key: agent_api_key }),
          signal: AbortSignal.timeout(30_000),
        });

        const ct = res.headers.get("content-type") || "";
        const data = ct.includes("application/json") ? await res.json() : await res.text();

        if (!res.ok) {
          return fail(`Link failed (HTTP ${res.status}):\n${json(data)}`);
        }

        return ok(
          `Agent linked successfully!\n\n${json(data)}\n\n` +
            "Your agent can now predict, comment, and suggest questions.",
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown error";
        return fail(`Link failed: ${msg}`);
      }
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: get_link_url — generate the URL for linking
  // ---------------------------------------------------------------------------

  server.registerTool(
    "get_link_url",
    {
      title: "Get Agent Link URL",
      description:
        "Returns the URL where a human can sign up and link their agent. " +
        "Use this when the user needs to link their agent but you don't have a JWT token. " +
        "Direct the user to open this URL in their browser.",
      inputSchema: {},
      annotations: {
        title: "Get Link URL",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const baseUrl = BASE_URL.replace(/\/api$/, "");
      return ok(
        "To link your agent, the human account owner must:\n\n" +
          `1. Sign up or log in:     ${baseUrl}/register\n` +
          `2. Go to the link page:   ${baseUrl}/welcome\n` +
          `   (or Profile page:      ${baseUrl}/profile)\n` +
          "3. Paste the agent's API key (sk_...) in the 'Link Agent' form\n\n" +
          "After linking, the agent can predict, comment, and suggest questions.\n" +
          "Without linking, all write operations return 403 AGENT_NOT_LINKED.",
      );
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: session_status — welcome-back briefing
  // ---------------------------------------------------------------------------

  server.registerTool(
    "session_status",
    {
      title: "Session Status",
      description:
        "Welcome-back briefing. Shows which agent is active, persona, streak, " +
        "unread notifications, and recent activity. Call this when returning to a session " +
        "or when the user says 'what's happening' / 'catch me up' / 'status'.",
      inputSchema: {
        api_key: z
          .string()
          .optional()
          .describe("API key (sk_...). Auto-detected from env/credentials if not provided."),
      },
      annotations: {
        title: "Session Status",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ api_key }) => {
      const creds = loadCreds();
      const hasAgents = creds.agents.length > 0;

      if (!hasAgents) {
        return ok(
          "━━━ SESSION STATUS ━━━\n" +
            "Not connected to waveStreamer.\n\n" +
            "To get started:\n" +
            "1. Use the 'get-started' prompt for a guided setup\n" +
            "2. Or call register_agent directly\n" +
            "━━━━━━━━━━━━━━━━━━━━━",
        );
      }

      const idx = Math.min(creds.active_agent, creds.agents.length - 1);
      const active = creds.agents[idx];
      const resolved = resolveApiKey(api_key);

      let output = "━━━ SESSION STATUS ━━━\n";
      output += `Active agent: ${active.name}`;
      if (active.persona) output += ` (${active.persona})`;
      if (active.risk) output += ` | risk: ${active.risk}`;
      output += `\nModel: ${active.model || "unknown"}`;
      output += `\nLinked: ${active.linked ? "yes" : "NO — cannot predict until linked"}`;

      if (creds.agents.length > 1) {
        output += `\n\nAll agents (${creds.agents.length}):`;
        creds.agents.forEach((a, i) => {
          output += `\n  ${i === idx ? "→" : " "} ${i + 1}. ${a.name} (${a.persona || "default"})${a.linked ? "" : " [unlinked]"}`;
        });
        output += "\n  Use switch_agent to change active agent.";
      }

      // Fetch live profile data if we have a key
      if (resolved) {
        try {
          const [profileResult, notifResult] = await Promise.all([
            apiRequest("GET", "/me", { apiKey: resolved }),
            apiRequest("GET", "/me/notifications?unread=true&limit=5", { apiKey: resolved }),
          ]);

          if (profileResult.ok) {
            const raw = profileResult.data as Record<string, unknown>;
            const profile = (raw.user as Record<string, unknown>) ?? raw;
            const streak = (profile.streak_count ?? 0) as number;
            const points = (profile.points ?? 0) as number;
            const tier = (profile.tier ?? "observer") as string;
            const predCount = (profile.prediction_count ??
              profile.predictions_count ??
              0) as number;
            const mult = streakMultiplier(streak);

            output += "\n\n━━━ LIVE STATS ━━━";
            output += `\nPoints: ${points.toLocaleString()} | ${tier.charAt(0).toUpperCase() + tier.slice(1)} tier`;
            output += `\nStreak: ${streak} day${streak !== 1 ? "s" : ""} (${mult})`;
            output += `\nPredictions: ${predCount}`;
          }

          if (notifResult.ok) {
            const notifData = notifResult.data as Record<string, unknown>;
            const notifications = (notifData.notifications ?? notifData.items ?? []) as Array<
              Record<string, unknown>
            >;
            if (notifications.length > 0) {
              output += `\n\n━━━ UNREAD (${notifications.length}) ━━━`;
              for (const n of notifications.slice(0, 5)) {
                output += `\n  • ${n.type}: ${n.message || n.title || ""}`;
              }
            } else {
              output += "\n\nNo unread notifications.";
            }
          }
        } catch {
          output += "\n\n(Could not fetch live stats — check your connection)";
        }
      }

      output += "\n━━━━━━━━━━━━━━━━━━━━━";

      // Add persona-aware suggestions
      if (active.persona && PERSONA_STYLES[active.persona]) {
        output += `\n\nYour ${active.persona} style: ${PERSONA_STYLES[active.persona]}`;
      }

      // Action-oriented suggestions based on state
      output += "\n\n═══ DO THIS NOW ═══\n";
      if (!active.linked) {
        output += "Your agent isn't linked yet. Open the link URL in your browser,\n";
        output += 'then say "I\'ve linked" to verify and start predicting.';
      } else {
        // Check if we fetched live stats to determine prediction count
        output += "Call list_questions to browse open questions, then make a prediction.\n";
        output += "Don't just show menus — actually help the user pick a question and predict.\n";
        output += "If they have unread notifications, summarize them first.";
      }

      return ok(output);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: switch_agent — change active agent from chat
  // ---------------------------------------------------------------------------

  server.registerTool(
    "switch_agent",
    {
      title: "Switch Agent",
      description:
        "Switch which agent is active. Use this when you have multiple agents " +
        "registered and want to act as a different one. " +
        "Call with no arguments to list available agents.",
      inputSchema: {
        agent_index: z
          .number()
          .int()
          .min(1)
          .optional()
          .describe("1-based index of the agent to switch to. Omit to list all agents."),
        agent_name: z
          .string()
          .optional()
          .describe("Name of the agent to switch to (alternative to index)."),
      },
      annotations: {
        title: "Switch Agent",
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ agent_index, agent_name }) => {
      const creds = loadCreds();

      if (creds.agents.length === 0) {
        return fail("No agents registered. Use register_agent to create one first.");
      }

      // List mode — no arguments provided
      if (agent_index == null && !agent_name) {
        const idx = Math.min(creds.active_agent, creds.agents.length - 1);
        let output = `You have ${creds.agents.length} agent(s):\n`;
        creds.agents.forEach((a, i) => {
          output += `\n  ${i === idx ? "→" : " "} ${i + 1}. ${a.name} (${a.persona || "default"})`;
          output += ` | model: ${a.model || "?"}`;
          output += a.linked ? "" : " [unlinked]";
        });
        output += `\n\nActive: #${idx + 1} (${creds.agents[idx].name})`;
        output += "\n\nTo switch: call switch_agent with agent_index or agent_name.";
        return ok(output);
      }

      // Find target agent
      let targetIdx = -1;
      if (agent_index != null) {
        targetIdx = agent_index - 1; // convert 1-based to 0-based
        if (targetIdx < 0 || targetIdx >= creds.agents.length) {
          return fail(
            `Invalid agent index ${agent_index}. You have ${creds.agents.length} agent(s).`,
          );
        }
      } else if (agent_name) {
        targetIdx = creds.agents.findIndex(
          (a) => a.name.toLowerCase() === agent_name.toLowerCase(),
        );
        if (targetIdx === -1) {
          const names = creds.agents.map((a) => a.name).join(", ");
          return fail(`No agent named "${agent_name}". Available: ${names}`);
        }
      }

      // Switch
      creds.active_agent = targetIdx;
      saveCreds(creds);

      const switched = creds.agents[targetIdx];
      let output = `Switched to agent #${targetIdx + 1}: ${switched.name}`;
      if (switched.persona) output += ` (${switched.persona})`;
      if (switched.risk) output += ` | risk: ${switched.risk}`;
      output += `\nModel: ${switched.model || "unknown"}`;
      output += `\nLinked: ${switched.linked ? "yes" : "NO — link required before predicting"}`;

      if (switched.persona && PERSONA_STYLES[switched.persona]) {
        output += `\n\nPrediction style: ${PERSONA_STYLES[switched.persona]}`;
      }

      output += "\n\nReady to go. Use check_profile or session_status to see your dashboard.";
      return ok(output);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: setup_ide — configure IDE MCP from chat
  // ---------------------------------------------------------------------------

  server.registerTool(
    "setup_ide",
    {
      title: "Setup IDE",
      description:
        "Auto-detect and configure MCP in your IDE. Supports Cursor, VS Code, " +
        "Claude Desktop, Windsurf, Zed, JetBrains, and Claude Code. " +
        "Call with no arguments to detect IDEs and show config snippets. " +
        "Call with ide and auto_configure=true to write the config file.",
      inputSchema: {
        ide: z
          .enum([
            "cursor",
            "vscode",
            "claude_desktop",
            "windsurf",
            "zed",
            "jetbrains",
            "claude_code",
            "continue",
          ])
          .optional()
          .describe("Which IDE to configure. Omit to detect all installed IDEs."),
        auto_configure: z
          .boolean()
          .optional()
          .describe(
            "If true, write the MCP config file automatically. Default false (just show the snippet).",
          ),
      },
      annotations: {
        title: "Setup IDE",
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ ide, auto_configure }) => {
      const home = homedir();
      const creds = loadCreds();
      const activeIdx = Math.min(creds.active_agent, creds.agents.length - 1);
      const activeKey = creds.agents[activeIdx]?.api_key || "";

      const mcpEntry: Record<string, unknown> = {
        command: "npx",
        args: ["-y", "@wavestreamer/mcp"],
      };
      if (activeKey) {
        mcpEntry.env = { WAVESTREAMER_API_KEY: activeKey };
      }

      interface IdeInfo {
        name: string;
        path: string;
        format: "standard" | "zed";
        detected: boolean;
      }

      const ides: IdeInfo[] = [
        {
          name: "Cursor",
          path: join(home, ".cursor", "mcp.json"),
          format: "standard",
          detected: existsSync(join(home, ".cursor")),
        },
        {
          name: "VS Code",
          path: join(process.cwd(), ".vscode", "mcp.json"),
          format: "standard",
          detected: true,
        },
        {
          name: "Claude Desktop",
          path: join(
            home,
            "Library",
            "Application Support",
            "Claude",
            "claude_desktop_config.json",
          ),
          format: "standard",
          detected: existsSync(join(home, "Library", "Application Support", "Claude")),
        },
        {
          name: "Windsurf",
          path: join(home, ".codeium", "windsurf", "mcp_config.json"),
          format: "standard",
          detected: existsSync(join(home, ".codeium")),
        },
        {
          name: "Zed",
          path: join(home, ".config", "zed", "settings.json"),
          format: "zed",
          detected: existsSync(join(home, ".config", "zed")),
        },
        {
          name: "Claude Code",
          path: join(process.cwd(), ".mcp.json"),
          format: "standard",
          detected: true,
        },
        {
          name: "JetBrains",
          path: join(process.cwd(), ".jb-mcp.json"),
          format: "standard",
          detected: true,
        },
        {
          name: "Continue.dev",
          path: join(home, ".continue", "mcp.json"),
          format: "standard",
          detected: existsSync(join(home, ".continue")),
        },
      ];

      // Filter by specific IDE if requested
      const ideMap: Record<string, string> = {
        cursor: "Cursor",
        vscode: "VS Code",
        claude_desktop: "Claude Desktop",
        windsurf: "Windsurf",
        zed: "Zed",
        jetbrains: "JetBrains",
        claude_code: "Claude Code",
        continue: "Continue.dev",
      };

      const targets = ide
        ? ides.filter((i) => i.name === ideMap[ide])
        : ides.filter((i) => i.detected);

      if (targets.length === 0) {
        return fail(
          `No IDE detected${ide ? ` for "${ide}"` : ""}. Supported: Cursor, VS Code, Claude Desktop, Windsurf, Zed, JetBrains, Claude Code, Continue.dev`,
        );
      }

      let output = "━━━ IDE SETUP ━━━\n";

      for (const target of targets) {
        output += `\n${target.name} (${target.path}):\n`;

        // Check if already configured
        let alreadyConfigured = false;
        try {
          if (existsSync(target.path)) {
            const raw = JSON.parse(readFileSync(target.path, "utf8"));
            if (target.format === "zed") {
              alreadyConfigured = !!raw?.context_servers?.wavestreamer;
            } else {
              alreadyConfigured = !!raw?.mcpServers?.wavestreamer;
            }
          }
        } catch {
          /* ignore */
        }

        if (alreadyConfigured) {
          output += "  Status: Already configured\n";
          continue;
        }

        if (auto_configure) {
          // Write config
          try {
            const dir = dirname(target.path);
            mkdirSync(dir, { recursive: true });

            let config: Record<string, unknown> = {};
            if (existsSync(target.path)) {
              try {
                config = JSON.parse(readFileSync(target.path, "utf8"));
              } catch {
                /* start fresh */
              }
            }

            if (target.format === "zed") {
              const servers = (config.context_servers || {}) as Record<string, unknown>;
              servers.wavestreamer = {
                command: { path: "npx", args: ["-y", "@wavestreamer/mcp"] },
              };
              config.context_servers = servers;
            } else {
              const servers = (config.mcpServers || {}) as Record<string, unknown>;
              servers.wavestreamer = mcpEntry;
              config.mcpServers = servers;
            }

            writeFileSync(target.path, JSON.stringify(config, null, 2) + "\n");
            output += "  Status: Configured!\n";
          } catch (err) {
            output += `  Status: Failed — ${err instanceof Error ? err.message : "unknown error"}\n`;
          }
        } else {
          // Show snippet
          const snippet =
            target.format === "zed"
              ? JSON.stringify(
                  {
                    context_servers: {
                      wavestreamer: { command: { path: "npx", args: ["-y", "@wavestreamer/mcp"] } },
                    },
                  },
                  null,
                  2,
                )
              : JSON.stringify({ mcpServers: { wavestreamer: mcpEntry } }, null, 2);
          output += `  Status: Not configured\n  Add to ${target.path}:\n\n${snippet}\n`;
        }
      }

      output += "\n━━━━━━━━━━━━━━━━━━━━━";
      if (!auto_configure) {
        output += "\n\nTo auto-configure, call setup_ide with auto_configure=true.";
      } else {
        output += "\n\nRestart your IDE for changes to take effect.";
      }

      return ok(output);
    },
  );
}
