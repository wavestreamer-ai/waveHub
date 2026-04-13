import { describe, it, expect, vi } from "vitest";

// Mock fetch globally before importing anything
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock fs.readFileSync for version loading
vi.mock("node:fs", () => ({
  readFileSync: () => JSON.stringify({ version: "0.0.0-test" }),
  existsSync: () => false,
  mkdirSync: () => {},
  writeFileSync: () => {},
}));

// Mock stdio transport to prevent actual stdin/stdout binding
vi.mock("@modelcontextprotocol/sdk/server/stdio.js", () => {
  class MockTransport {
    start() {}
    close() {}
  }
  return { StdioServerTransport: MockTransport };
});

// Capture tool registrations from the server
const toolRegistry = new Map<
  string,
  { title?: string; description: string; inputSchema: Record<string, unknown> }
>();

vi.mock("@modelcontextprotocol/sdk/server/mcp.js", () => {
  class MockMcpServer {
    constructor() {}
    registerTool(
      name: string,
      opts: { title?: string; description: string; inputSchema: Record<string, unknown> },
    ) {
      toolRegistry.set(name, opts);
    }
    registerResource() {}
    registerPrompt() {}
    resource() {}
    prompt() {}
    connect() {}
  }
  class MockResourceTemplate {
    template: string;
    constructor(template: string) {
      this.template = template;
    }
  }
  return { McpServer: MockMcpServer, ResourceTemplate: MockResourceTemplate };
});

// Now import the server module — this triggers all registerTool calls
await import("../index.js");

describe("MCP Tool Registration", () => {
  it("registers all expected tools", () => {
    expect(toolRegistry.size).toBeGreaterThanOrEqual(64);
  });

  const expectedTools = [
    // Onboarding (8)
    "register_agent",
    "create_agent",
    "configure_llm",
    "link_agent",
    "get_link_url",
    "session_status",
    "switch_agent",
    "setup_ide",
    // Predictions (6)
    "view_taxonomy",
    "list_questions",
    "prediction_preflight",
    "make_prediction",
    "preview_prediction",
    "get_predict_context",
    // Profile & Account (8)
    "check_profile",
    "update_profile",
    "my_transactions",
    "my_fleet",
    "my_feed",
    "my_notifications",
    "view_question",
    "view_agent",
    // Social & Engagement (9)
    "view_leaderboard",
    "post_comment",
    "suggest_question",
    "submit_referral_share",
    "dispute",
    "webhook",
    "vote",
    "follow",
    "watchlist",
    // Guardian & Challenges (7)
    "validate_prediction",
    "flag_hallucination",
    "guardian_queue",
    "apply_for_guardian",
    "create_challenge",
    "respond_challenge",
    "view_debates",
    // Knowledge Graph & Advanced (11)
    "search_kg_entities",
    "get_entity_graph",
    "similar_predictions",
    "view_drift_events",
    "my_citation_issues",
    "view_rag_context",
    "start_agent_runtime",
    "pause_agent_runtime",
    "trigger_agent_run",
    "agent_runtime_status",
    "update_agent_config",
    // Personas (4)
    "list_templates",
    "list_personas",
    "create_persona",
    "delete_persona",
    // Surveys (5)
    "my_surveys",
    "list_surveys",
    "get_survey",
    "survey_progress",
    "survey_results",
    // Organizations (6)
    "my_orgs",
    "org_surveys",
    "org_questions",
    "org_consensus",
    "org_members",
    "org_survey_results",
  ];

  it.each(expectedTools)("registers tool: %s", (toolName) => {
    expect(toolRegistry.has(toolName)).toBe(true);
  });

  it("all tools have descriptions", () => {
    for (const [name, tool] of toolRegistry) {
      expect(tool.description, `${name} should have a description`).toBeTruthy();
      expect(tool.description.length, `${name} description should be non-trivial`).toBeGreaterThan(
        10,
      );
    }
  });

  it("register_agent requires name and model parameters", () => {
    const tool = toolRegistry.get("register_agent");
    expect(tool).toBeDefined();
    const schema = tool!.inputSchema as Record<string, unknown>;
    expect(schema).toHaveProperty("name");
    expect(schema).toHaveProperty("model");
  });

  it("make_prediction requires key parameters", () => {
    const tool = toolRegistry.get("make_prediction");
    expect(tool).toBeDefined();
    const schema = tool!.inputSchema as Record<string, unknown>;
    expect(schema).toHaveProperty("question_id");
    expect(schema).toHaveProperty("prediction");
    expect(schema).toHaveProperty("confidence");
    expect(schema).toHaveProperty("reasoning");
  });
});
