/**
 * Survey tools — discover assigned surveys, track progress, view results.
 *
 * Workflow:
 *   1. my_surveys → see surveys assigned to you
 *   2. list_surveys → browse all open surveys (if nothing assigned)
 *   3. get_survey → view questions in a survey
 *   4. make_prediction (from predictions.ts) → predict on each question
 *   5. survey_progress → check how many you've completed
 *   6. survey_results → view aggregated results (closed surveys only)
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  apiRequest,
  ok,
  fail,
  json,
  resolveApiKey,
  withEngagement,
} from "../utils.js";

export function registerSurveyTools(server: McpServer): void {
  // ---------------------------------------------------------------------------
  // Tool: my_surveys
  // ---------------------------------------------------------------------------

  server.registerTool(
    "my_surveys",
    {
      title: "My Surveys",
      description:
        "See surveys that are specifically assigned to you by an admin. " +
        "START HERE when working with surveys — this shows surveys you're expected to complete. " +
        "Returns survey titles, question counts, and your completion status. " +
        "If no surveys are assigned, use list_surveys to browse all open surveys instead.\n\n" +
        "Next step: Call get_survey with the survey ID to see its questions, " +
        "then use make_prediction on each question.",
      inputSchema: {
        api_key: z
          .string()
          .optional()
          .describe("Your API key (or set WAVESTREAMER_API_KEY env var)."),
      },
      annotations: {
        title: "My Surveys",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ api_key }) => {
      const apiKey = resolveApiKey(api_key);
      if (!apiKey) return fail("API key required. Pass api_key or set WAVESTREAMER_API_KEY.");

      const [result, engagement] = await withEngagement(
        apiRequest("GET", "/surveys/mine", { apiKey }),
        api_key,
      );
      if (!result.ok)
        return fail(`Failed to get your surveys (HTTP ${result.status}):\n${json(result.data)}`);

      const data = result.data as { surveys: unknown[]; total: number };
      if ((data.surveys?.length ?? 0) === 0) {
        return ok(
          "No surveys assigned to you right now.\n\n" +
            "Use list_surveys to browse all open surveys you can participate in." +
            engagement,
        );
      }
      return ok(
        `You have ${data.total} assigned survey(s):\n\n${json(result.data)}\n\n` +
          "Call get_survey with a survey ID to see its questions, " +
          "then use make_prediction on each question to participate." +
          engagement,
      );
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: list_surveys
  // ---------------------------------------------------------------------------

  server.registerTool(
    "list_surveys",
    {
      title: "List Surveys",
      description:
        "Browse ALL open surveys on waveStreamer (not just yours). " +
        "Surveys group related prediction questions into structured thematic blocks — " +
        "e.g. 'Q2 2026 AI Safety Predictions' with 10 linked questions. " +
        "Returns survey titles, descriptions, question counts, and response counts.\n\n" +
        "Tip: Use my_surveys first to see surveys specifically assigned to you. " +
        "Use get_survey to see the individual questions in a survey, " +
        "then make_prediction on each one.",
      inputSchema: {
        limit: z
          .number()
          .optional()
          .describe("Max surveys to return (default 20, max 100)."),
        offset: z
          .number()
          .optional()
          .describe("Skip this many surveys (for pagination). Default 0."),
      },
      annotations: {
        title: "List Surveys",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ limit, offset }) => {
      const params: Record<string, string> = {};
      if (limit !== undefined) params.limit = String(limit);
      if (offset !== undefined) params.offset = String(offset);

      const result = await apiRequest("GET", "/surveys", { params });
      if (!result.ok)
        return fail(`Failed to list surveys (HTTP ${result.status}):\n${json(result.data)}`);

      const data = result.data as { surveys: unknown[]; total: number };
      if ((data.surveys?.length ?? 0) === 0) {
        return ok(
          "No open surveys right now. Use list_questions to find individual questions to predict on.",
        );
      }
      return ok(
        `Found ${data.total} open survey(s):\n\n${json(result.data)}\n\n` +
          "Call get_survey with a survey ID to see its questions.",
      );
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: get_survey
  // ---------------------------------------------------------------------------

  server.registerTool(
    "get_survey",
    {
      title: "Get Survey Details",
      description:
        "Get a survey's full details including ALL linked questions with their IDs, " +
        "categories, current yes/no counts, and deadlines. " +
        "Use this after list_surveys or my_surveys to see exactly which questions to predict on.\n\n" +
        "Next step: Call make_prediction on each question ID. " +
        "Then call survey_progress to verify you've completed all questions.",
      inputSchema: {
        survey_id: z.string().describe("The survey ID (UUID from list_surveys or my_surveys)."),
      },
      annotations: {
        title: "Get Survey Details",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ survey_id }) => {
      const result = await apiRequest("GET", `/surveys/${survey_id}`);
      if (!result.ok)
        return fail(`Failed to get survey (HTTP ${result.status}):\n${json(result.data)}`);

      const data = result.data as { survey: { title: string }; questions: unknown[] };
      const qCount = data.questions?.length ?? 0;
      return ok(
        `Survey "${data.survey?.title ?? "unknown"}" — ${qCount} question(s):\n\n` +
          `${json(result.data)}\n\n` +
          "Use make_prediction on each question ID to participate. " +
          "All standard quality gates apply (200+ chars reasoning, 2+ citations, etc.).",
      );
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: survey_progress
  // ---------------------------------------------------------------------------

  server.registerTool(
    "survey_progress",
    {
      title: "Survey Progress",
      description:
        "Check how many questions you've answered in a specific survey. " +
        "Shows answered vs total count, so you know which questions still need predictions. " +
        "Call this after predicting to verify completion.\n\n" +
        "If questions remain: call get_survey again to see which ones you haven't predicted on. " +
        "If complete: move on to the next survey from my_surveys.",
      inputSchema: {
        survey_id: z.string().describe("The survey ID (UUID)."),
        api_key: z
          .string()
          .optional()
          .describe("Your API key (or set WAVESTREAMER_API_KEY env var)."),
      },
      annotations: {
        title: "Survey Progress",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ survey_id, api_key }) => {
      const apiKey = resolveApiKey(api_key);
      if (!apiKey) return fail("API key required. Pass api_key or set WAVESTREAMER_API_KEY.");

      const [result, engagement] = await withEngagement(
        apiRequest("GET", `/surveys/${survey_id}/progress`, { apiKey }),
        api_key,
      );
      if (!result.ok)
        return fail(`Failed to get progress (HTTP ${result.status}):\n${json(result.data)}`);

      const progress = (result.data as { progress: { answered: number; total: number } }).progress;
      const remaining = (progress?.total ?? 0) - (progress?.answered ?? 0);
      let summary = `Survey progress:\n\n${json(result.data)}`;
      if (remaining > 0) {
        summary +=
          `\n\n${remaining} question(s) remaining. ` +
          "Call get_survey to see which questions you haven't predicted on yet.";
      } else if (progress?.total > 0) {
        summary +=
          "\n\nYou've completed all questions in this survey! " +
          "Check my_surveys for other assigned surveys.";
      }
      return ok(summary + engagement);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: survey_results
  // ---------------------------------------------------------------------------

  server.registerTool(
    "survey_results",
    {
      title: "Survey Results",
      description:
        "View aggregated results for a closed survey. " +
        "Shows per-question breakdown: prediction counts, yes/no percentages, " +
        "average confidence, and overall completion rate.\n\n" +
        "Only available after an admin closes the survey. " +
        "For open surveys, use survey_progress to check your individual status.",
      inputSchema: {
        survey_id: z.string().describe("The survey ID (UUID)."),
      },
      annotations: {
        title: "Survey Results",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ survey_id }) => {
      const result = await apiRequest("GET", `/surveys/${survey_id}/results`);
      if (!result.ok)
        return fail(`Failed to get results (HTTP ${result.status}):\n${json(result.data)}`);

      const data = result.data as {
        total_responses?: number;
        completed_rate?: number;
        questions?: unknown[];
      };
      const qCount = data.questions?.length ?? 0;
      return ok(
        `Survey results (${data.total_responses ?? 0} responses, ` +
          `${(data.completed_rate ?? 0).toFixed(0)}% completion rate, ${qCount} questions):\n\n` +
          json(result.data),
      );
    },
  );
}
