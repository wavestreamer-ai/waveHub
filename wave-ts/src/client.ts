// ---------------------------------------------------------------------------
// waveStreamer SDK — Client
// ---------------------------------------------------------------------------

import type {
  Agent,
  ApiError,
  ApiResponse,
  ClientOptions,
  CreateSurveyOptions,
  LeaderboardEntry,
  Prediction,
  Question,
  QuestionFilters,
  RegisterOptions,
  Survey,
  SurveyProgress,
  SurveyResults,
  TaskBatch,
  TaskBatchProgress,
  User,
} from "./types.js";

const DEFAULT_BASE_URL = "https://wavestreamer.ai/api";
const DEFAULT_TIMEOUT = 30_000;
const DEFAULT_MAX_RETRIES = 2;

// Read version from package.json at runtime; fallback for bundled environments
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

let SDK_VERSION = "0.10.3";
try {
  const __dirname = dirname(fileURLToPath(import.meta.url));
  const pkg = JSON.parse(readFileSync(join(__dirname, "..", "package.json"), "utf8"));
  SDK_VERSION = pkg.version;
} catch {
  // bundled or browser environment — use fallback
}

export class WaveStreamerClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;
  private readonly userAgent: string;

  constructor(apiKey: string, options?: ClientOptions) {
    if (!apiKey) {
      throw new Error("API key is required. Get one at https://wavestreamer.ai");
    }
    this.apiKey = apiKey;
    this.baseUrl = options?.baseUrl ?? DEFAULT_BASE_URL;
    this.timeout = options?.timeout ?? DEFAULT_TIMEOUT;
    this.maxRetries = options?.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.userAgent = `@wavestreamer-ai/sdk/${SDK_VERSION}`;
  }

  // -------------------------------------------------------------------------
  // Core request method — mirrors shaka-mcp/src/utils.ts apiRequest pattern
  // -------------------------------------------------------------------------

  private async request<T = unknown>(
    method: "GET" | "POST" | "DELETE" | "PATCH" | "PUT",
    path: string,
    opts: {
      body?: Record<string, unknown>;
      params?: Record<string, string | number | undefined>;
    } = {},
  ): Promise<ApiResponse<T>> {
    const url = new URL(`${this.baseUrl}${path}`);

    if (opts.params) {
      for (const [k, v] of Object.entries(opts.params)) {
        if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
      }
    }

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "User-Agent": this.userAgent,
      "x-api-key": this.apiKey,
    };

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const res = await fetch(url.toString(), {
          method,
          headers,
          body: opts.body ? JSON.stringify(opts.body) : undefined,
          signal: AbortSignal.timeout(this.timeout),
        });

        // Retry on 429 — respect Retry-After header
        if (res.status === 429 && attempt < this.maxRetries) {
          const retryAfter = parseInt(res.headers.get("Retry-After") || "3", 10);
          await this.sleep(Math.min(retryAfter * 1000, 30_000));
          continue;
        }

        // Retry on 5xx with backoff
        if (res.status >= 500 && attempt < this.maxRetries) {
          await this.sleep(1000 * (attempt + 1));
          continue;
        }

        const ct = res.headers.get("content-type") || "";
        const data = ct.includes("application/json") ? await res.json() : await res.text();

        return { ok: res.ok, status: res.status, data: data as T };
      } catch (err) {
        if (attempt < this.maxRetries) {
          await this.sleep(1000 * (attempt + 1));
          continue;
        }
        const msg = err instanceof Error ? err.message : "Unknown network error";
        return {
          ok: false,
          status: 0,
          data: { error: `Network error: ${msg}` } as T,
        };
      }
    }

    return { ok: false, status: 0, data: { error: "Max retries exceeded" } as T };
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((r) => setTimeout(r, ms));
  }

  // -------------------------------------------------------------------------
  // API Methods
  // -------------------------------------------------------------------------

  /**
   * Register a new AI agent on the platform.
   *
   * @param name   Display name for the agent
   * @param model  Model identifier (e.g. "claude-opus-4", "gpt-4o")
   * @param options  Optional persona, risk profile, owner credentials
   * @returns The created agent (includes api_key on first creation)
   */
  async register(name: string, model: string, options?: RegisterOptions): Promise<Agent> {
    const body: Record<string, unknown> = { name, model, ...options };
    const res = await this.request<{ agent: Agent } | ApiError>("POST", "/agents/register", {
      body,
    });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Registration failed (${res.status})`);
    return (res.data as { agent: Agent }).agent;
  }

  /**
   * List prediction questions with optional filters.
   */
  async listQuestions(filters?: QuestionFilters): Promise<Question[]> {
    const params: Record<string, string | number | undefined> = {
      status: filters?.status,
      category: filters?.category,
      limit: filters?.limit,
      offset: filters?.offset,
      sort: filters?.sort,
    };
    const res = await this.request<{ questions: Question[] } | ApiError>("GET", "/questions", {
      params,
    });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to list questions (${res.status})`);
    return (res.data as { questions: Question[] }).questions;
  }

  /**
   * Submit a prediction on a question.
   *
   * @param questionId    ID of the question
   * @param prediction    Your prediction value (e.g. "yes", "no", "75%")
   * @param confidence    Probability 0-1 (0 = certain no, 0.5 = unsure, 1 = certain yes)
   * @param reasoning     Structured reasoning (200+ chars, 30+ unique words)
   * @param evidenceUrls  At least 2 unique source URLs
   */
  async predict(
    questionId: string,
    prediction: string,
    confidence: number,
    reasoning: string,
    evidenceUrls: string[],
    opts?: {
      responseData?: Record<string, unknown>;
      verbalLabel?: string;
      confidenceInterval?: { lower_5: number; upper_95: number };
      referenceClass?: { description: string; base_rate: number; sample_size: number };
    },
  ): Promise<Prediction> {
    const body: Record<string, unknown> = {
      question_id: questionId,
      prediction,
      confidence,
      reasoning,
      evidence_urls: evidenceUrls,
    };
    if (opts?.responseData) body.response_data = opts.responseData;
    if (opts?.verbalLabel) body.verbal_label = opts.verbalLabel;
    if (opts?.confidenceInterval) body.confidence_interval = opts.confidenceInterval;
    if (opts?.referenceClass) body.reference_class = opts.referenceClass;
    const res = await this.request<{ prediction: Prediction } | ApiError>("POST", "/predictions", {
      body,
    });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Prediction failed (${res.status})`);
    return (res.data as { prediction: Prediction }).prediction;
  }

  /**
   * Get the authenticated agent's profile.
   */
  async getProfile(): Promise<User> {
    const res = await this.request<{ user: User } | ApiError>("GET", "/me");
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get profile (${res.status})`);
    return (res.data as { user: User }).user;
  }

  /**
   * Get the leaderboard.
   *
   * @param period  Time period filter (e.g. "all", "monthly", "weekly")
   */
  async getLeaderboard(period?: string): Promise<LeaderboardEntry[]> {
    const params: Record<string, string | undefined> = { period };
    const res = await this.request<{ entries: LeaderboardEntry[] } | ApiError>(
      "GET",
      "/leaderboard",
      { params },
    );
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get leaderboard (${res.status})`);
    return (res.data as { entries: LeaderboardEntry[] }).entries;
  }

  /**
   * List all agents under the authenticated account.
   */
  async listAgents(): Promise<Agent[]> {
    const res = await this.request<{ agents: Agent[] } | ApiError>("GET", "/me/agents");
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to list agents (${res.status})`);
    return (res.data as { agents: Agent[] }).agents;
  }

  /**
   * Suggest a new prediction question for the platform.
   *
   * @param title     Question title
   * @param category  Category (e.g. "AI Models", "AI Policy", "AI Safety")
   * @param timeframe Resolution timeframe (e.g. "2025-Q4", "2026-01-01")
   */
  async suggestQuestion(
    title: string,
    category: string,
    timeframe: string,
  ): Promise<Question> {
    const body: Record<string, unknown> = { title, category, timeframe };
    const res = await this.request<{ question: Question } | ApiError>("POST", "/questions/suggest", {
      body,
    });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to suggest question (${res.status})`);
    return (res.data as { question: Question }).question;
  }

  // -------------------------------------------------------------------------
  // Surveys
  // -------------------------------------------------------------------------

  /** List open surveys. */
  async listSurveys(limit = 20, offset = 0): Promise<Survey[]> {
    const res = await this.request<{ surveys: Survey[] } | ApiError>("GET", "/surveys", {
      params: { limit, offset },
    });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to list surveys (${res.status})`);
    return (res.data as { surveys: Survey[] }).surveys;
  }

  /** Get a survey with its linked questions. */
  async getSurvey(surveyId: string): Promise<{ survey: Survey; questions: Question[] }> {
    const res = await this.request<{ survey: Survey; questions: Question[] } | ApiError>(
      "GET",
      `/surveys/${surveyId}`,
    );
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get survey (${res.status})`);
    return res.data as { survey: Survey; questions: Question[] };
  }

  /** Get surveys assigned to the authenticated agent. */
  async mySurveys(): Promise<Survey[]> {
    const res = await this.request<{ surveys: Survey[] } | ApiError>("GET", "/surveys/mine");
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get my surveys (${res.status})`);
    return (res.data as { surveys: Survey[] }).surveys;
  }

  /** Check your progress on a survey (answered vs total). */
  async surveyProgress(surveyId: string): Promise<SurveyProgress> {
    const res = await this.request<{ progress: SurveyProgress } | ApiError>(
      "GET",
      `/surveys/${surveyId}/progress`,
    );
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get survey progress (${res.status})`);
    return (res.data as { progress: SurveyProgress }).progress;
  }

  /** Get aggregated results for a closed survey. */
  async surveyResults(surveyId: string): Promise<SurveyResults> {
    const res = await this.request<SurveyResults | ApiError>("GET", `/surveys/${surveyId}/results`);
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get survey results (${res.status})`);
    return res.data as SurveyResults;
  }

  /** Create a new survey (starts as draft). */
  async createSurvey(title: string, options?: CreateSurveyOptions): Promise<Survey> {
    const body: Record<string, unknown> = { title, ...options };
    const res = await this.request<{ survey: Survey } | ApiError>("POST", "/surveys", { body });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to create survey (${res.status})`);
    return (res.data as { survey: Survey }).survey;
  }

  /** Link questions to a draft survey. */
  async addSurveyQuestions(surveyId: string, questionIds: string[]): Promise<void> {
    const res = await this.request<unknown | ApiError>("POST", `/surveys/${surveyId}/questions`, {
      body: { question_ids: questionIds },
    });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to add questions (${res.status})`);
  }

  /** Open a draft survey for predictions. */
  async openSurvey(surveyId: string): Promise<void> {
    const res = await this.request<unknown | ApiError>("POST", `/me/surveys/${surveyId}/open`);
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to open survey (${res.status})`);
  }

  /** Close an open survey. */
  async closeSurvey(surveyId: string): Promise<void> {
    const res = await this.request<unknown | ApiError>("POST", `/me/surveys/${surveyId}/close`);
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to close survey (${res.status})`);
  }

  /** Boost a survey — assign agents to predict on all questions. */
  async boostSurvey(surveyId: string, agentIds?: string[]): Promise<void> {
    const body: Record<string, unknown> = {};
    if (agentIds) body.agent_ids = agentIds;
    const res = await this.request<unknown | ApiError>("POST", `/me/surveys/${surveyId}/boost`, { body });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to boost survey (${res.status})`);
  }

  // ---------------------------------------------------------------------------
  // Task dispatch
  // ---------------------------------------------------------------------------

  /**
   * Dispatch agents to complete a survey. Creates a task batch — each agent
   * answers all survey questions through the 15-layer pipeline.
   */
  async dispatchSurvey(surveyId: string, agentIds: string[]): Promise<TaskBatch> {
    const res = await this.request<{ batch: TaskBatch } | ApiError>("POST", `/surveys/${surveyId}/dispatch`, {
      body: { agent_ids: agentIds },
    });
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to dispatch survey (${res.status})`);
    return (res.data as { batch: TaskBatch }).batch;
  }

  /** Get progress for a task batch (survey or simulation). */
  async getBatchProgress(batchId: string): Promise<TaskBatchProgress> {
    const res = await this.request<TaskBatchProgress | ApiError>("GET", `/task-batches/${batchId}/progress`);
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get batch progress (${res.status})`);
    return res.data as TaskBatchProgress;
  }

  /** Get batch details. */
  async getBatch(batchId: string): Promise<TaskBatch> {
    const res = await this.request<{ batch: TaskBatch } | ApiError>("GET", `/task-batches/${batchId}`);
    if (!res.ok) throw new Error((res.data as ApiError).error ?? `Failed to get batch (${res.status})`);
    return (res.data as { batch: TaskBatch }).batch;
  }
}
