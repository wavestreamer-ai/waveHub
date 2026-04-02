import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";

// ---------------------------------------------------------------------------
// Test URL
// ---------------------------------------------------------------------------
const TEST_API_URL = "http://test-api.local/api";
process.env.WAVESTREAMER_API_URL = TEST_API_URL;

// ---------------------------------------------------------------------------
// Mock fetch globally — intercepts all apiRequest() calls
// ---------------------------------------------------------------------------
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// ---------------------------------------------------------------------------
// Mock fs.readFileSync for version loading
// ---------------------------------------------------------------------------
vi.mock("node:fs", () => ({
  readFileSync: () => JSON.stringify({ version: "0.0.0-test" }),
  existsSync: () => false,
  mkdirSync: () => {},
  writeFileSync: () => {},
}));

// ---------------------------------------------------------------------------
// Mock stdio transport
// ---------------------------------------------------------------------------
vi.mock("@modelcontextprotocol/sdk/server/stdio.js", () => {
  class MockTransport {
    start() {}
    close() {}
  }
  return { StdioServerTransport: MockTransport };
});

// ---------------------------------------------------------------------------
// Mock MCP SDK — capture both config AND handler for each tool
// ---------------------------------------------------------------------------
interface ToolRegistration {
  config: { title?: string; description: string; inputSchema: Record<string, unknown> };
  handler: (
    args: Record<string, unknown>,
  ) => Promise<{ content: { type: string; text: string }[]; isError?: boolean }>;
}

const toolRegistry = new Map<string, ToolRegistration>();

vi.mock("@modelcontextprotocol/sdk/server/mcp.js", () => {
  class MockMcpServer {
    constructor() {}
    registerTool(
      name: string,
      config: ToolRegistration["config"],
      handler: ToolRegistration["handler"],
    ) {
      toolRegistry.set(name, { config, handler });
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

// ---------------------------------------------------------------------------
// Import the server module — triggers all registerTool calls
// ---------------------------------------------------------------------------
await import("../index.js");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a mock Response that apiRequest() can consume. */
function mockResponse(status: number, body: unknown, ok?: boolean): Response {
  const isOk = ok ?? (status >= 200 && status < 300);
  return {
    ok: isOk,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

/** Get a registered handler or throw. */
function getHandler(name: string) {
  const reg = toolRegistry.get(name);
  if (!reg) throw new Error(`Tool "${name}" not registered`);
  return reg.handler;
}

/** Assert the response is a success (no isError). */
function expectOk(result: { content: { type: string; text: string }[]; isError?: boolean }) {
  expect(result.isError).toBeFalsy();
  expect(result.content).toHaveLength(1);
  expect(result.content[0].type).toBe("text");
}

/** Assert the response is an error. */
function expectFail(result: { content: { type: string; text: string }[]; isError?: boolean }) {
  expect(result.isError).toBe(true);
  expect(result.content).toHaveLength(1);
  expect(result.content[0].type).toBe("text");
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  mockFetch.mockReset();
});

describe("Tool Execution: register_agent", () => {
  const handler = getHandler("register_agent");

  it("sends POST /register with name and model in body", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(201, {
        user: { id: "u1", name: "TestBot", api_key: "sk_test_123" },
      }),
    );

    const result = await handler({ name: "TestBot", model: "gpt-4o" });

    expectOk(result);
    expect(result.content[0].text).toContain("AGENT REGISTERED");
    expect(result.content[0].text).toContain("TestBot");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${TEST_API_URL}/register`);
    expect(opts.method).toBe("POST");

    const body = JSON.parse(opts.body);
    expect(body.name).toBe("TestBot");
    expect(body.model).toBe("gpt-4o");
  });

  it("includes optional fields when provided", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(201, { user: { id: "u2", name: "Bot2", api_key: "sk_test_456" } }),
    );

    await handler({
      name: "Bot2",
      model: "claude-sonnet-4",
      persona_archetype: "contrarian",
      risk_profile: "aggressive",
      referral_code: "REF123",
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.persona_archetype).toBe("contrarian");
    expect(body.risk_profile).toBe("aggressive");
    expect(body.referral_code).toBe("REF123");
  });

  it("returns error on 409 conflict", async () => {
    mockFetch.mockResolvedValue(mockResponse(409, { error: "Name already taken" }));

    const result = await handler({ name: "Duplicate", model: "gpt-4o" });

    expectFail(result);
    expect(result.content[0].text).toContain("409");
    expect(result.content[0].text).toContain("Name already taken");
  });
});

describe("Tool Execution: make_prediction", () => {
  const handler = getHandler("make_prediction");

  it("sends POST /questions/{id}/predict with correct body and auth", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(201, { prediction: { id: "p1", prediction: true, confidence: 85 } }),
    );

    const result = await handler({
      api_key: "sk_test_key",
      question_id: "q-uuid-123",
      prediction: true,
      confidence: 85,
      reasoning: "EVIDENCE: test evidence. ANALYSIS: test analysis.",
      resolution_protocol: {
        criterion: "Test criterion",
        source_of_truth: "Official source",
        deadline: "2026-12-31T00:00:00Z",
        resolver: "platform",
        edge_cases: "None expected",
      },
    });

    expectOk(result);
    expect(result.content[0].text).toContain("Prediction placed!");

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${TEST_API_URL}/questions/q-uuid-123/predict`);
    expect(opts.method).toBe("POST");
    expect(opts.headers["x-api-key"]).toBe("sk_test_key");

    const body = JSON.parse(opts.body);
    expect(body.prediction).toBe(true);
    expect(body.confidence).toBe(85);
    expect(body.reasoning).toContain("EVIDENCE");
    expect(body.resolution_protocol.criterion).toBe("Test criterion");
  });

  it("supports probability mode", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(201, { prediction: { id: "p2" } }));

    await handler({
      api_key: "sk_test",
      question_id: "q1",
      probability: 72,
      reasoning: "Probability-based analysis here.",
      resolution_protocol: {
        criterion: "c",
        source_of_truth: "s",
        deadline: "d",
        resolver: "platform",
        edge_cases: "e",
      },
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.probability).toBe(72);
    expect(body.prediction).toBeUndefined();
  });

  it("returns AGENT_NOT_LINKED error on 403", async () => {
    mockFetch.mockResolvedValue(
      mockResponse(403, { error: "Agent not linked", code: "AGENT_NOT_LINKED" }),
    );

    const result = await handler({
      api_key: "sk_unlinked",
      question_id: "q1",
      prediction: true,
      confidence: 50,
      reasoning: "Test reasoning content here.",
      resolution_protocol: {
        criterion: "c",
        source_of_truth: "s",
        deadline: "d",
        resolver: "platform",
        edge_cases: "e",
      },
    });

    expectFail(result);
    expect(result.content[0].text).toContain("not linked");
    expect(result.content[0].text).toContain("welcome");
  });

  it("returns validation error when no prediction mode provided", async () => {
    const result = await handler({
      api_key: "sk_test",
      question_id: "q1",
      reasoning: "Some reasoning here.",
      resolution_protocol: {
        criterion: "c",
        source_of_truth: "s",
        deadline: "d",
        resolver: "platform",
        edge_cases: "e",
      },
    });

    expectFail(result);
    expect(result.content[0].text).toContain("Provide one of");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("Tool Execution: check_profile", () => {
  const handler = getHandler("check_profile");

  it("sends GET /me with api_key header", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, {
        user: {
          id: "u1",
          name: "TestBot",
          points: 1500,
          tier: "Analyst",
          owner_id: "human-1",
          type: "agent",
        },
      }),
    );

    const result = await handler({ api_key: "sk_profile_key" });

    expectOk(result);
    expect(result.content[0].text).toContain("DASHBOARD");
    expect(result.content[0].text).toContain("1,500");

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${TEST_API_URL}/me`);
    expect(opts.method).toBe("GET");
    expect(opts.headers["x-api-key"]).toBe("sk_profile_key");
  });

  it("warns about unlinked agent", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, {
        user: {
          id: "u2",
          name: "UnlinkedBot",
          owner_id: null,
          type: "agent",
        },
      }),
    );

    const result = await handler({ api_key: "sk_unlinked" });

    expectOk(result);
    expect(result.content[0].text).toContain("NOT linked");
    expect(result.content[0].text).toContain("cannot predict");
  });

  it("returns error on 401 unauthorized", async () => {
    mockFetch.mockResolvedValue(mockResponse(401, { error: "Invalid API key" }));

    const result = await handler({ api_key: "sk_bad" });

    expectFail(result);
    expect(result.content[0].text).toContain("401");
  });
});

describe("Tool Execution: list_questions", () => {
  const handler = getHandler("list_questions");

  it("sends GET /questions with status and category params", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, {
        questions: [
          { id: "q1", title: "Will GPT-5 launch by 2026?", status: "open", category: "technology" },
          { id: "q2", title: "AI regulation in EU?", status: "open", category: "society" },
        ],
      }),
    );

    const result = await handler({ status: "open", category: "technology" });

    expectOk(result);
    expect(result.content[0].text).toContain("2 question(s)");

    const [url] = mockFetch.mock.calls[0];
    const parsed = new URL(url);
    expect(parsed.pathname).toBe("/api/questions");
    expect(parsed.searchParams.get("status")).toBe("open");
    expect(parsed.searchParams.get("category")).toBe("technology");
  });

  it("returns friendly message when no questions match", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { questions: [] }));

    const result = await handler({ status: "resolved", category: "society" });

    expectOk(result);
    expect(result.content[0].text).toContain("No questions match");
  });

  it("sends no query params when none provided", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { questions: [{ id: "q1" }] }));

    await handler({});

    const [url] = mockFetch.mock.calls[0];
    const parsed = new URL(url);
    expect(parsed.search).toBe("");
  });
});

describe("Tool Execution: view_leaderboard", () => {
  const handler = getHandler("view_leaderboard");

  it("sends GET /leaderboard with no auth", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, {
        leaderboard: [
          { rank: 1, name: "AlphaPredict", points: 5200 },
          { rank: 2, name: "BetaBot", points: 4800 },
        ],
      }),
    );

    const result = await handler({});

    expectOk(result);
    expect(result.content[0].text).toContain("Leaderboard");
    expect(result.content[0].text).toContain("AlphaPredict");

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${TEST_API_URL}/leaderboard`);
    expect(opts.method).toBe("GET");
    expect(opts.headers["x-api-key"]).toBeUndefined();
  });

  it("returns error on server failure", async () => {
    // Simulate 3 retries all failing with 500
    mockFetch.mockResolvedValue(mockResponse(500, { error: "Internal server error" }));

    const result = await handler({});

    expectFail(result);
    expect(result.content[0].text).toContain("500");
  });
});

describe("Tool Execution: post_comment", () => {
  const handler = getHandler("post_comment");

  it("sends POST /questions/{id}/comments with content body", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(201, { comment: { id: "c1", content: "Great analysis!" } }),
    );

    const result = await handler({
      api_key: "sk_commenter",
      question_id: "q-abc-123",
      content: "Great analysis! I agree with the evidence presented.",
    });

    expectOk(result);
    expect(result.content[0].text).toContain("Comment posted!");

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe(`${TEST_API_URL}/questions/q-abc-123/comments`);
    expect(opts.method).toBe("POST");
    expect(opts.headers["x-api-key"]).toBe("sk_commenter");

    const body = JSON.parse(opts.body);
    expect(body.content).toBe("Great analysis! I agree with the evidence presented.");
  });

  it("returns error on 401 unauthorized", async () => {
    mockFetch.mockResolvedValue(mockResponse(401, { error: "Unauthorized" }));

    const result = await handler({
      api_key: "sk_invalid",
      question_id: "q1",
      content: "Should fail.",
    });

    expectFail(result);
    expect(result.content[0].text).toContain("401");
  });
});

describe("Tool Execution: watchlist", () => {
  const handler = getHandler("watchlist");

  it("sends GET /me/watchlist with auth when action is list", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, {
        questions: [
          { id: "q1", title: "AI milestone Q4" },
          { id: "q2", title: "Regulation update" },
        ],
      }),
    );

    const result = await handler({ api_key: "sk_watcher", action: "list" });

    expectOk(result);
    expect(result.content[0].text).toContain("watchlist");

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/me/watchlist");
    expect(opts.headers["x-api-key"]).toBe("sk_watcher");
  });

  it("returns error on 401", async () => {
    mockFetch.mockResolvedValue(mockResponse(401, { error: "Invalid API key" }));

    const result = await handler({ api_key: "sk_bad", action: "list" });

    expectFail(result);
    expect(result.content[0].text).toContain("401");
  });
});

describe("Tool Execution: my_feed", () => {
  const handler = getHandler("my_feed");

  it("sends GET /me/feed with filter params", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, {
        items: [{ type: "prediction", agent: "Bot1" }],
        next_cursor: "2026-03-10T00:00:00Z",
      }),
    );

    const result = await handler({
      api_key: "sk_feed_user",
      type: "prediction",
      source: "followed",
      limit: 10,
    });

    expectOk(result);
    expect(result.content[0].text).toContain("activity feed");

    const [url, opts] = mockFetch.mock.calls[0];
    // my_feed builds the query string itself and appends to the path
    expect(url).toContain("/me/feed");
    expect(url).toContain("type=prediction");
    expect(url).toContain("source=followed");
    expect(url).toContain("limit=10");
    expect(opts.headers["x-api-key"]).toBe("sk_feed_user");
  });

  it("sends no query params when filters omitted", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { items: [] }));

    await handler({ api_key: "sk_feed_user" });

    const [url] = mockFetch.mock.calls[0];
    // The path should end with /me/feed without extra query params
    // (apiRequest may still get the base URL — we just check no filter params)
    expect(url).toContain("/me/feed");
    expect(url).not.toContain("type=");
    expect(url).not.toContain("source=");
  });

  it("returns error on 401", async () => {
    mockFetch.mockResolvedValue(mockResponse(401, { error: "Unauthorized" }));

    const result = await handler({ api_key: "sk_expired" });

    expectFail(result);
    expect(result.content[0].text).toContain("401");
  });
});

describe("Tool Execution: my_notifications", () => {
  const handler = getHandler("my_notifications");

  it("sends GET /me/notifications with auth", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(200, {
        notifications: [
          { id: "n1", type: "question_resolved", message: "GPT-5 question resolved" },
          { id: "n2", type: "comment_reply", message: "Bot2 replied to your comment" },
        ],
      }),
    );

    const result = await handler({ api_key: "sk_notif_user" });

    expectOk(result);
    expect(result.content[0].text).toContain("notifications");

    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toContain("/me/notifications");
    expect(opts.headers["x-api-key"]).toBe("sk_notif_user");
  });

  it("passes limit as query param", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { notifications: [] }));

    await handler({ api_key: "sk_notif_user", limit: 5 });

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("limit=5");
  });

  it("returns error on 401", async () => {
    mockFetch.mockResolvedValue(mockResponse(401, { error: "Unauthorized" }));

    const result = await handler({ api_key: "sk_bad" });

    expectFail(result);
    expect(result.content[0].text).toContain("401");
  });
});
