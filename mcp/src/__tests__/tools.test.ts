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
    expect(toolRegistry.size).toBeGreaterThanOrEqual(30);
  });

  const expectedTools = [
    "register_agent",
    "link_agent",
    "get_link_url",
    "view_taxonomy",
    "list_questions",
    "make_prediction",
    "check_profile",
    "view_leaderboard",
    "post_comment",
    "suggest_question",
    "submit_referral_share",
    "dispute",
    "webhook",
    "vote",
    "follow",
    "update_profile",
    "view_question",
    "view_agent",
    "watchlist",
    "my_transactions",
    "my_fleet",
    "validate_prediction",
    "flag_hallucination",
    "guardian_queue",
    "apply_for_guardian",
    "create_challenge",
    "respond_challenge",
    "view_debates",
    "my_feed",
    "my_notifications",
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
