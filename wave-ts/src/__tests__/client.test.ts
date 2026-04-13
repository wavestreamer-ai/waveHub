import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock fs for version reading
vi.mock("node:fs", () => ({
  readFileSync: () => JSON.stringify({ version: "0.0.0-test" }),
}));

import { WaveStreamerClient } from "../client.js";

function mockJsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("WaveStreamerClient", () => {
  describe("constructor", () => {
    it("throws if no API key provided", () => {
      expect(() => new WaveStreamerClient("")).toThrow("API key is required");
    });

    it("creates client with valid API key", () => {
      const client = new WaveStreamerClient("sk_test_123");
      expect(client).toBeDefined();
    });

    it("uses default base URL", () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(mockJsonResponse({ questions: [] }));
      client.listQuestions();
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("https://wavestreamer.ai/api/questions"),
        expect.any(Object),
      );
    });

    it("accepts custom base URL", () => {
      const client = new WaveStreamerClient("sk_test_123", {
        baseUrl: "http://localhost:8888/api",
      });
      mockFetch.mockReturnValue(mockJsonResponse({ questions: [] }));
      client.listQuestions();
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("http://localhost:8888/api/questions"),
        expect.any(Object),
      );
    });
  });

  describe("listQuestions", () => {
    it("returns questions array", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      const mockQuestions = [
        { id: "q1", title: "Will GPT-5 launch?" },
        { id: "q2", title: "Will AGI arrive by 2030?" },
      ];
      mockFetch.mockReturnValue(mockJsonResponse({ questions: mockQuestions }));

      const questions = await client.listQuestions();
      expect(questions).toHaveLength(2);
      expect(questions[0].id).toBe("q1");
    });

    it("passes status filter", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(mockJsonResponse({ questions: [] }));

      await client.listQuestions({ status: "open" });
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain("status=open");
    });

    it("passes category filter", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(mockJsonResponse({ questions: [] }));

      await client.listQuestions({ category: "ai-models" });
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain("category=ai-models");
    });
  });

  describe("getProfile", () => {
    it("returns user profile", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(
        mockJsonResponse({ user: { id: "u1", name: "TestBot", points: 5000 } }),
      );

      const user = await client.getProfile();
      expect(user.name).toBe("TestBot");
      expect(user.points).toBe(5000);
    });

    it("sends API key header", async () => {
      const client = new WaveStreamerClient("sk_test_key");
      mockFetch.mockReturnValue(
        mockJsonResponse({ user: { id: "u1", name: "Bot" } }),
      );

      await client.getProfile();
      const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>;
      expect(headers["x-api-key"]).toBe("sk_test_key");
    });
  });

  describe("register", () => {
    it("registers agent and returns agent data", async () => {
      const client = new WaveStreamerClient("sk_placeholder");
      mockFetch.mockReturnValue(
        mockJsonResponse({
          agent: { id: "a1", name: "NewBot", model: "gpt-4o" },
          api_key: "sk_new_key",
        }),
      );

      const result = await client.register("NewBot", "gpt-4o");
      expect(result.name).toBe("NewBot");
    });
  });

  describe("predict", () => {
    it("sends prediction with required fields", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(
        mockJsonResponse({
          prediction: { id: "p1", question_id: "q1", confidence: 75 },
        }),
      );

      const prediction = await client.predict(
        "q1",
        "true",
        75,
        "Detailed reasoning...",
        ["https://source1.com/article", "https://source2.com/article"],
      );
      expect(prediction.id).toBe("p1");

      const body = JSON.parse(mockFetch.mock.calls[0][1].body as string);
      expect(body.prediction).toBe("true");
      expect(body.confidence).toBe(75);
      expect(body.reasoning).toBe("Detailed reasoning...");
      expect(body.evidence_urls).toHaveLength(2);
    });
  });

  describe("getLeaderboard", () => {
    it("returns leaderboard entries", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(
        mockJsonResponse({
          entries: [
            { rank: 1, agent_id: "a1", name: "TopBot", points: 10000 },
            { rank: 2, agent_id: "a2", name: "RunnerUp", points: 8000 },
          ],
        }),
      );

      const entries = await client.getLeaderboard();
      expect(entries).toHaveLength(2);
      expect(entries[0].rank).toBe(1);
    });
  });

  describe("error handling", () => {
    it("throws on non-200 response", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(
        mockJsonResponse({ error: "Not found" }, 404),
      );

      await expect(client.getProfile()).rejects.toThrow();
    });
  });

  describe("surveys", () => {
    it("lists surveys", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(
        mockJsonResponse({
          surveys: [{ id: "s1", title: "AI Survey", status: "open" }],
        }),
      );

      const surveys = await client.listSurveys();
      expect(surveys).toHaveLength(1);
      expect(surveys[0].title).toBe("AI Survey");
    });

    it("gets survey by id", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(
        mockJsonResponse({
          survey: { id: "s1", title: "AI Survey" },
          questions: [{ id: "q1", title: "Question 1" }],
        }),
      );

      const result = await client.getSurvey("s1");
      expect(result.survey.id).toBe("s1");
      expect(result.questions).toHaveLength(1);
    });
  });

  describe("request mechanics", () => {
    it("sets user-agent header", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(mockJsonResponse({ user: { id: "u1" } }));

      await client.getProfile();
      const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>;
      expect(headers["User-Agent"]).toContain("@wavestreamer-ai/sdk/");
    });

    it("sets content-type header", async () => {
      const client = new WaveStreamerClient("sk_test_123");
      mockFetch.mockReturnValue(mockJsonResponse({ user: { id: "u1" } }));

      await client.getProfile();
      const headers = mockFetch.mock.calls[0][1].headers as Record<string, string>;
      expect(headers["Content-Type"]).toBe("application/json");
    });
  });
});
