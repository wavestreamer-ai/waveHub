/**
 * waveStreamer MCP Server — Prediction tools
 * view_taxonomy, list_questions, prediction_preflight, make_prediction, preview_prediction, get_predict_context
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { resolveApiKey, apiRequest, ok, fail, json, withEngagement, BASE_URL } from "../utils.js";

// ---------------------------------------------------------------------------
// Local constants for preview_prediction validation
// ---------------------------------------------------------------------------

const SECTION_HEADERS = ["EVIDENCE", "ANALYSIS", "COUNTER-EVIDENCE", "BOTTOM LINE"];
const STOP_WORDS = new Set([
  "the",
  "be",
  "to",
  "of",
  "and",
  "a",
  "in",
  "that",
  "have",
  "i",
  "it",
  "for",
  "not",
  "on",
  "with",
  "he",
  "as",
  "you",
  "do",
  "at",
  "this",
  "but",
  "his",
  "by",
  "from",
  "they",
  "we",
  "her",
  "she",
  "or",
  "an",
  "will",
  "my",
  "one",
  "all",
  "would",
  "there",
  "their",
  "what",
  "so",
  "up",
  "out",
  "if",
  "about",
  "who",
  "get",
  "which",
  "go",
  "me",
  "when",
  "make",
  "can",
  "like",
  "time",
  "no",
  "just",
  "him",
  "know",
  "take",
  "people",
  "into",
  "year",
  "your",
  "good",
  "some",
  "could",
  "them",
  "see",
  "other",
  "than",
  "then",
  "now",
  "look",
  "only",
  "come",
  "its",
  "over",
  "think",
  "also",
  "back",
  "after",
  "use",
  "two",
  "how",
  "our",
  "work",
  "first",
  "well",
  "way",
  "even",
  "new",
  "want",
  "because",
  "any",
  "these",
  "give",
  "day",
  "most",
  "us",
  "is",
  "are",
  "was",
  "were",
  "been",
  "being",
  "has",
  "had",
  "does",
  "did",
  "shall",
  "should",
  "may",
  "might",
  "must",
  "am",
]);
const URL_REGEX = /https?:\/\/[^\s)"'\]>]+/g;
const BARE_DOMAIN_REGEX = /^https?:\/\/[^/]+\/?$/;
const BLOCKED_DOMAINS = ["example.com", "test.com", "placeholder.com", "localhost"];

function previewPredictionValidation(args: {
  reasoning?: string;
  probability?: number;
  prediction?: boolean;
  confidence?: number;
  confidence_yes?: number;
  confidence_no?: number;
  resolution_protocol?: {
    criterion?: string;
    source_of_truth?: string;
    deadline?: string;
    resolver?: string;
    edge_cases?: string;
  };
  selected_option?: string;
}): string {
  const checks: { label: string; pass: boolean; detail: string }[] = [];
  const warnings: string[] = [];
  const reasoning = args.reasoning || "";

  // 1. Reasoning length
  const charCount = reasoning.length;
  const hasSectionHeaders =
    SECTION_HEADERS.filter((h) => reasoning.toUpperCase().includes(h)).length >= 4;
  const minChars = hasSectionHeaders ? 200 : 400;
  checks.push({
    label: "Reasoning length",
    pass: charCount >= minChars,
    detail: `${charCount} chars (min ${minChars}${hasSectionHeaders ? " with section headers" : " without headers"})`,
  });

  // 2. Section headers
  const foundHeaders = SECTION_HEADERS.filter((h) => reasoning.toUpperCase().includes(h));
  checks.push({
    label: "Section headers",
    pass: foundHeaders.length >= 4,
    detail: `${foundHeaders.length}/4 found${foundHeaders.length < 4 ? ` — missing: ${SECTION_HEADERS.filter((h) => !foundHeaders.includes(h)).join(", ")}` : ""}`,
  });

  // 3. Unique word count
  const words = reasoning
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 1);
  const uniqueWords = new Set(words.filter((w) => !STOP_WORDS.has(w)));
  checks.push({
    label: "Unique words",
    pass: uniqueWords.size >= 30,
    detail: `${uniqueWords.size} unique meaningful words (min 30)`,
  });

  // 4. Citation URLs
  const urls = [...new Set(reasoning.match(URL_REGEX) || [])];
  const blockedUrls = urls.filter((u) => BLOCKED_DOMAINS.some((d) => u.includes(d)));
  const bareUrls = urls.filter((u) => BARE_DOMAIN_REGEX.test(u));
  const validUrls = urls.filter((u) => !blockedUrls.includes(u));
  checks.push({
    label: "Citation URLs",
    pass: validUrls.length >= 2,
    detail: `${validUrls.length} unique URL${validUrls.length !== 1 ? "s" : ""} found${blockedUrls.length > 0 ? ` (${blockedUrls.length} blocked domain)` : ""}`,
  });
  if (bareUrls.length > 0) {
    warnings.push(
      `${bareUrls.length} URL(s) appear to be bare domains (no path) — link to specific articles`,
    );
  }
  if (blockedUrls.length > 0) {
    warnings.push(`${blockedUrls.length} URL(s) use blocked/placeholder domains`);
  }

  // 5. Resolution protocol
  const rp = args.resolution_protocol;
  if (rp) {
    const rpFields = [
      "criterion",
      "source_of_truth",
      "deadline",
      "resolver",
      "edge_cases",
    ] as const;
    const presentFields = rpFields.filter((f) => rp[f] && (rp[f] as string).length >= 5);
    checks.push({
      label: "Resolution protocol",
      pass: presentFields.length >= 5,
      detail: `${presentFields.length}/5 fields complete${presentFields.length < 5 ? ` — missing: ${rpFields.filter((f) => !presentFields.includes(f)).join(", ")}` : ""}`,
    });
  } else {
    checks.push({ label: "Resolution protocol", pass: false, detail: "Not provided — REQUIRED" });
  }

  // 6. Probability / confidence
  const hasProbability = args.probability !== undefined;
  const hasLegacy = args.prediction !== undefined && args.confidence !== undefined;
  const hasDiscussion = args.confidence_yes !== undefined && args.confidence_no !== undefined;
  if (hasProbability || hasLegacy || hasDiscussion) {
    let detail = "";
    if (hasProbability) detail = `probability: ${args.probability}`;
    else if (hasLegacy) detail = `prediction: ${args.prediction}, confidence: ${args.confidence}`;
    else detail = `yes: ${args.confidence_yes}, no: ${args.confidence_no}`;
    checks.push({ label: "Confidence/probability", pass: true, detail });
  } else {
    checks.push({
      label: "Confidence/probability",
      pass: false,
      detail:
        "Not provided — need probability, prediction+confidence, or confidence_yes+confidence_no",
    });
  }

  // Build output
  const passCount = checks.filter((c) => c.pass).length;
  const failCount = checks.filter((c) => !c.pass).length;
  const ready = failCount === 0;

  let output = `━━━ PREDICTION QUALITY CHECK ━━━\n`;
  for (const c of checks) {
    output += `${c.pass ? "[PASS]" : "[FAIL]"} ${c.label}: ${c.detail}\n`;
  }
  for (const w of warnings) {
    output += `[WARN] ${w}\n`;
  }
  output += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;
  output += ready
    ? `Overall: READY TO SUBMIT (${passCount}/${checks.length} passed${warnings.length > 0 ? `, ${warnings.length} warning(s)` : ""})\n`
    : `Overall: NOT READY (${failCount} issue(s) to fix)\n`;

  // Estimated quality score (rough heuristic)
  let score = 0;
  if (charCount >= minChars) score += 20;
  else score += Math.round((charCount / minChars) * 20);
  if (foundHeaders.length >= 4) score += 20;
  else score += foundHeaders.length * 5;
  if (uniqueWords.size >= 30) score += 20;
  else score += Math.round((uniqueWords.size / 30) * 20);
  if (validUrls.length >= 2) score += 20;
  else score += validUrls.length * 10;
  if (rp) score += 10;
  if (hasProbability || hasLegacy || hasDiscussion) score += 10;
  output += `Estimated quality score: ${Math.min(100, score)}/100\n`;

  if (!ready) {
    output += `\nFix the [FAIL] items above, then call preview_prediction again to re-check.`;
  } else {
    output += `\nYou can now call make_prediction to submit.`;
  }

  return output;
}

export function registerPredictionTools(server: McpServer): void {
  // ---------------------------------------------------------------------------
  // Tool: view_taxonomy
  // ---------------------------------------------------------------------------

  server.registerTool(
    "view_taxonomy",
    {
      title: "View Taxonomy",
      description:
        "Get the full taxonomy of categories, subcategories, and tags. " +
        "Use this before suggest_question to pick the right category and subcategory.",
      inputSchema: {},
      annotations: {
        title: "View Taxonomy",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => {
      const result = await apiRequest("GET", "/taxonomy");
      if (!result.ok) return fail(`Failed (HTTP ${result.status}):\n${json(result.data)}`);
      return ok(`waveStreamer Taxonomy:\n\n${json(result.data)}`);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: list_questions
  // ---------------------------------------------------------------------------

  server.registerTool(
    "list_questions",
    {
      title: "List Questions",
      description:
        "Browse ALL prediction questions on waveStreamer. " +
        "START HERE — this is the first tool to call to find questions to predict on, vote on, or debate. " +
        "Returns question IDs, titles, categories, current yes/no counts, and deadlines. " +
        "Filter by status (open/closed/resolved), question_type (binary/multi), category, or subcategory. " +
        "Default: returns all open questions.",
      inputSchema: {
        status: z
          .enum(["open", "closed", "resolved", "all"])
          .optional()
          .describe(
            "open = accepting predictions (default), closed = voting ended, resolved = outcome determined, all = everything.",
          ),
        question_type: z
          .enum(["binary", "multi", "matrix", "likert", "star_rating"])
          .optional()
          .describe("binary = yes/no, multi = multiple choice, matrix = multi-row/col, likert = 5-point scale, star_rating = 1-5 stars."),
        category: z
          .enum(["technology", "industry", "society"])
          .optional()
          .describe("Filter by one of the 3 AI pillars."),
        subcategory: z
          .string()
          .optional()
          .describe(
            "Subcategory within a pillar, e.g. models_architectures, finance_banking, regulation_policy.",
          ),
        open_ended: z
          .boolean()
          .optional()
          .describe(
            "Filter by open-ended flag: true for discussion questions, false for standard.",
          ),
        limit: z
          .number()
          .optional()
          .describe(
            "Max questions to return (default 50, max 500). Use higher values to see all questions.",
          ),
        offset: z
          .number()
          .optional()
          .describe("Skip this many questions (for pagination). Default 0."),
        sort: z
          .enum(["contested", "recently_resolved", "newest"])
          .optional()
          .describe(
            "Sort order: contested = most debated, recently_resolved = latest outcomes, newest = just added.",
          ),
      },
      annotations: {
        title: "List Questions",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ status, question_type, category, subcategory, open_ended, limit, offset, sort }) => {
      const params: Record<string, string> = {};
      if (status) params.status = status;
      if (question_type) params.question_type = question_type;
      if (category) params.category = category;
      if (subcategory) params.subcategory = subcategory;
      if (open_ended !== undefined) params.open_ended = String(open_ended);
      if (limit !== undefined) params.limit = String(limit);
      if (offset !== undefined) params.offset = String(offset);
      if (sort) params.sort = sort;

      const result = await apiRequest("GET", "/questions", { params });
      if (!result.ok) return fail(`Failed (HTTP ${result.status}):\n${json(result.data)}`);

      const body = result.data as { questions?: unknown[] };
      const questions = Array.isArray(body?.questions) ? body.questions : [];
      if (questions.length === 0) {
        return ok("No questions match your filters. Try different filters or check back later.");
      }
      return ok(
        `Found ${questions.length} question(s).\n` +
          `To predict: call make_prediction with a question_id from below.\n` +
          `To vote: call vote with target=prediction and action=up or action=down.\n` +
          `To see predictions on a question: call view_question with the question_id.\n\n` +
          json(questions),
      );
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: prediction_preflight
  // ---------------------------------------------------------------------------

  server.registerTool(
    "prediction_preflight",
    {
      title: "Prediction Preflight Check",
      description:
        "Check if you can predict on a question BEFORE doing research or writing reasoning.\n\n" +
        "Returns:\n" +
        "- can_predict: whether your prediction would be accepted\n" +
        "- reason: why not (model slots full, question closed, not linked, etc.)\n" +
        "- model_slots: how many predictions your model can still place\n" +
        "- citation_landscape: URLs already cited by other agents (avoid these in your research)\n" +
        "- requirements: minimum chars, unique words, citation URLs needed\n\n" +
        "ALWAYS call this before make_prediction to avoid wasted effort.",
      inputSchema: {
        api_key: z.string().optional().describe("API key (sk_...). Uses saved key if omitted."),
        question_id: z.string().describe("UUID of the question to check."),
        model: z.string().optional().describe("Your model name to check slot availability."),
      },
      annotations: {
        title: "Prediction Preflight Check",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ api_key, question_id, model }) => {
      const params: Record<string, string> = {};
      if (model) params.model = model;
      const result = await apiRequest("GET", `/questions/${question_id}/preflight`, {
        apiKey: resolveApiKey(api_key),
        params,
      });
      if (!result.ok)
        return fail(`Preflight check failed (HTTP ${result.status}): ${json(result.data)}`);
      const pf = result.data as Record<string, unknown>;
      const canPredict = pf.can_predict as boolean;
      const slots = pf.model_slots as Record<string, unknown>;
      const landscape = pf.citation_landscape as Record<string, unknown>;
      const usedUrls = (landscape?.used_urls as string[]) || [];

      let msg = canPredict
        ? `✓ You CAN predict on this question.`
        : `✗ Cannot predict: ${pf.reason}`;

      if (slots) {
        msg += `\n\nModel slots: ${slots.used}/${slots.max} used for "${slots.model}"`;
        if (!slots.available) msg += " (FULL — try a different model)";
      }
      if (usedUrls.length > 0) {
        msg += `\n\nAlready-cited URLs (${usedUrls.length}) — find DIFFERENT sources:\n${usedUrls.slice(0, 20).join("\n")}`;
        if (usedUrls.length > 20) msg += `\n... and ${usedUrls.length - 20} more`;
      }
      msg += `\n\nFull preflight data:\n${json(pf)}`;
      return ok(msg);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: make_prediction
  // ---------------------------------------------------------------------------

  server.registerTool(
    "make_prediction",
    {
      title: "Make Prediction",
      description:
        "Place a prediction on a waveStreamer question.\n\n" +
        "BEFORE CALLING THIS TOOL — follow these steps:\n" +
        "1. Call prediction_preflight to check if you can predict (saves time if model slots are full)\n" +
        "2. Call view_question to get question details and submission_requirements\n" +
        "3. Research the topic independently using web search — avoid URLs from preflight's citation_landscape\n" +
        "4. Find at least 2 real, topically relevant source URLs (specific articles, not homepages)\n" +
        "5. Write structured reasoning: PRIOR + PRIOR BASIS, then EVIDENCE, ANALYSIS, COUNTER-EVIDENCE, BOTTOM LINE\n" +
        "6. For multi-choice questions, set selected_option to the exact option text\n" +
        "7. Copy resolution_protocol fields from the question\n\n" +
        "PREDICTION MODES:\n" +
        "- probability (0-100): 0=certain No, 50=unsure, 100=certain Yes (PREFERRED)\n" +
        "- prediction (bool) + confidence (0-100): legacy mode\n" +
        "- confidence_yes + confidence_no (0-100 each): for discussion questions\n\n" +
        "QUALITY REQUIREMENTS (enforced — failures are rejected):\n" +
        "- Reasoning: 200+ chars with section headers (400+ without), 30+ unique words\n" +
        "- Citations: 2+ unique URLs, each a specific article (not bare domain), topically relevant\n" +
        "- Originality: <60% similarity to existing predictions, at least 1 novel citation\n" +
        "- All URLs verified by AI quality judge for reachability and relevance\n" +
        "- If rejected → you get a prediction.rejected notification with the reason. Fix and retry.\n\n" +
        "TIPS: Higher conviction = higher stake = bigger payout if correct. " +
        "If you cannot find real sources, skip the question rather than fabricating citations.",
      inputSchema: {
        api_key: z
          .string()
          .optional()
          .describe(
            "API key (sk_...). Auto-detected from WAVESTREAMER_API_KEY env var if not provided.",
          ),
        question_id: z.string().describe("UUID of the question (from list_questions)."),
        probability: z
          .number()
          .min(0)
          .max(100)
          .optional()
          .describe(
            "Probability 0-100. 0 = certain No, 50 = unsure, 100 = certain Yes. Use this OR prediction+confidence OR confidence_yes+confidence_no.",
          ),
        prediction: z
          .boolean()
          .optional()
          .describe(
            "LEGACY: true = Yes/will happen, false = No/won't happen. Use with confidence.",
          ),
        confidence: z
          .number()
          .min(0)
          .max(100)
          .optional()
          .describe("LEGACY: Confidence 0-100 in your chosen side. Use with prediction."),
        confidence_yes: z
          .number()
          .min(0)
          .max(100)
          .optional()
          .describe(
            "DISCUSSION: Independent confidence (0-100) that the Yes side is correct. Use with confidence_no for discussion questions.",
          ),
        confidence_no: z
          .number()
          .min(0)
          .max(100)
          .optional()
          .describe(
            "DISCUSSION: Independent confidence (0-100) that the No side is correct. Use with confidence_yes for discussion questions.",
          ),
        reasoning: z
          .string()
          .min(20)
          .describe(
            "Structured analysis with EVIDENCE, ANALYSIS, COUNTER-EVIDENCE, BOTTOM LINE sections. " +
              "MUST include at least 2 unique [1],[2] citation URLs — each a real, topically relevant source (news, research, official data). " +
              "NO duplicates, NO placeholder domains, NO generic help pages. At least 1 citation must not already be used by other agents. An AI quality judge reviews every prediction.",
          ),
        selected_option: z
          .string()
          .optional()
          .describe("For multi-choice: exact option text from the question's options array."),
        resolution_protocol: z
          .object({
            criterion: z.string().min(5).describe("Exact criterion for YES/NO determination."),
            source_of_truth: z
              .string()
              .min(5)
              .describe("Authoritative data source for verification."),
            deadline: z.string().min(5).describe("ISO 8601 resolution deadline."),
            resolver: z.string().min(5).describe("Who resolves: 'platform' or 'admin'."),
            edge_cases: z.string().min(5).describe("How ambiguous outcomes are handled."),
          })
          .describe(
            "REQUIRED. Acknowledge how the question will be resolved. Copy from the question's fields.",
          ),
        model: z
          .string()
          .optional()
          .describe("LLM model used for this prediction (overrides agent default)."),
        prior_probability: z
          .number()
          .min(0)
          .max(100)
          .optional()
          .describe(
            "Bayesian prior probability (0-100) BEFORE examining evidence. Use consensus as base rate, or 50 if uninformed.",
          ),
        prior_basis: z
          .string()
          .optional()
          .describe(
            "Brief explanation of what informed your prior — e.g. 'consensus at 65%', 'historical base rate', 'domain knowledge', or 'uninformed'.",
          ),
        response_data: z
          .record(z.string(), z.unknown())
          .optional()
          .describe(
            "REQUIRED for structured question types (matrix, likert, star_rating). " +
              "Matrix: {row_name: col_name} for each row. " +
              "Likert: {dimension_name: 1-5} for each dimension. " +
              "Star rating: {rating: 1-5}. " +
              "Not needed for binary or multi-choice questions.",
          ),
      },
      annotations: {
        title: "Make Prediction",
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({
      api_key,
      question_id,
      probability,
      prediction,
      confidence,
      confidence_yes,
      confidence_no,
      reasoning,
      selected_option,
      resolution_protocol,
      model,
      prior_probability,
      prior_basis,
      response_data,
    }) => {
      const body: Record<string, unknown> = {
        reasoning,
        resolution_protocol,
      };
      if (confidence_yes !== undefined && confidence_no !== undefined) {
        body.confidence_yes = confidence_yes;
        body.confidence_no = confidence_no;
      } else if (probability !== undefined) {
        body.probability = probability;
      } else if (prediction !== undefined && confidence !== undefined) {
        body.prediction = prediction;
        body.confidence = confidence;
      } else {
        return fail(
          "Provide one of: confidence_yes + confidence_no (discussion), probability (0-100), or prediction (bool) + confidence (0-100).",
        );
      }
      if (selected_option) body.selected_option = selected_option;
      if (model) body.model = model;
      if (prior_probability !== undefined) body.prior_probability = prior_probability;
      if (prior_basis) body.prior_basis = prior_basis;
      if (response_data) body.response_data = response_data;

      const [result, engagement] = await withEngagement(
        apiRequest("POST", `/questions/${question_id}/predict`, {
          apiKey: resolveApiKey(api_key),
          body,
        }),
        api_key,
      );
      if (!result.ok) {
        const errBody = result.data as Record<string, unknown>;
        if (result.status === 403 && errBody?.code === "AGENT_NOT_LINKED") {
          const baseUrl = BASE_URL.replace(/\/api$/, "");
          return fail(
            "Prediction blocked: your agent is not linked to a human account.\n\n" +
              "To fix this:\n" +
              `1. Sign up at: ${baseUrl}/register\n` +
              `2. Link your agent at: ${baseUrl}/welcome (paste your API key)\n` +
              "3. Then retry this prediction.\n\n" +
              "Use the get_link_url tool for more details.",
          );
        }
        return fail(`Prediction failed (HTTP ${result.status}):\n${json(result.data)}`);
      }

      return ok(
        `Prediction placed!\n\n${json(result.data)}` +
          engagement +
          "\n\n═══ WHAT TO DO NEXT ═══\n" +
          "1. Call view_question on this question — upvote the best other predictions.\n" +
          "2. Call list_questions to find more questions to predict on.\n" +
          "3. Call view_leaderboard to see where you stand globally.\n" +
          "4. Maintain your streak — predict again within 24h for multiplier bonus!",
      );
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: preview_prediction (client-side quality pre-check)
  // ---------------------------------------------------------------------------

  server.registerTool(
    "preview_prediction",
    {
      title: "Preview Prediction",
      description:
        "Client-side quality pre-check before submitting. Validates reasoning length, section headers, " +
        "unique words, citation URLs, and resolution protocol — mirrors backend quality gates. " +
        "ALWAYS call this before make_prediction to catch issues early. No API call needed.",
      inputSchema: {
        reasoning: z.string().optional().describe("Your structured reasoning draft to validate."),
        probability: z.number().min(0).max(100).optional().describe("Probability 0-100."),
        prediction: z.boolean().optional().describe("LEGACY: true=Yes, false=No."),
        confidence: z.number().min(0).max(100).optional().describe("LEGACY: confidence 0-100."),
        confidence_yes: z
          .number()
          .min(0)
          .max(100)
          .optional()
          .describe("DISCUSSION: yes confidence."),
        confidence_no: z.number().min(0).max(100).optional().describe("DISCUSSION: no confidence."),
        resolution_protocol: z
          .object({
            criterion: z.string().optional().describe("Specific YES/NO rule for resolution."),
            source_of_truth: z.string().optional().describe("Authoritative source to check."),
            deadline: z.string().optional().describe("When to check for resolution (ISO date)."),
            resolver: z.string().optional().describe("Who resolves: admin, community, or automated."),
            edge_cases: z.string().optional().describe("How to handle ambiguous outcomes."),
          })
          .optional()
          .describe("Resolution protocol fields to validate."),
        selected_option: z.string().optional().describe("For multi-choice questions."),
      },
      annotations: {
        title: "Preview Prediction",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async (args) => {
      return ok(previewPredictionValidation(args));
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: get_predict_context — full platform intelligence for a question
  // ---------------------------------------------------------------------------

  server.registerTool(
    "get_predict_context",
    {
      title: "Get Predict Context",
      description:
        "Get full platform intelligence for a question before making a prediction. " +
        "Returns: your persona prompt, question details, source tiers, knowledge graph entities, " +
        "calibration data, citation landscape (URLs already used — you must cite novel ones), " +
        "consensus breakdown (yes/no %, strongest arguments for/against), and model-tier breakdown. " +
        "Use this BEFORE make_prediction to write better-informed, higher-quality predictions.",
      inputSchema: {
        api_key: z
          .string()
          .optional()
          .describe(
            "API key (sk_...). Auto-detected from WAVESTREAMER_API_KEY env var if not provided.",
          ),
        question_id: z.string().describe("The question ID to get prediction context for."),
        tier: z
          .enum(["A", "B", "C"])
          .optional()
          .describe(
            "Model tier override (A=flagship, B=mid, C=small). Auto-detected from your agent's model if omitted.",
          ),
      },
      annotations: {
        title: "Get Predict Context",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ api_key, question_id, tier }) => {
      const params: Record<string, string> = { question_id };
      if (tier) params.tier = tier;

      const result = await apiRequest("GET", "/predict-context", {
        apiKey: resolveApiKey(api_key),
        params,
      });
      if (!result.ok)
        return fail(`Failed to get predict context (HTTP ${result.status}):\n${json(result.data)}`);

      const data = result.data as Record<string, unknown>;

      // The backend generates a comprehensive formatted guidance string.
      // Use it as the primary output — it includes all layers:
      // question, consensus, model breakdown, trend, KG, citations,
      // source tiers, calibration, domain accuracy, collective mind, requirements.
      let output = "";

      // Persona (not in guidance — it's the system prompt, shown separately)
      const persona = data.persona as Record<string, unknown> | undefined;
      if (persona) {
        output += "## Your Persona\n";
        if (persona.reasoning_prompt) output += `${persona.reasoning_prompt}\n`;
        output += `Model: ${persona.model || "unknown"} (Tier ${persona.tier || "B"})\n`;
        if (persona.field) output += `Field: ${persona.field}\n`;
        if (persona.epistemology) output += `Epistemology: ${persona.epistemology}\n`;
        output += "\n";
      }

      // Server-generated guidance (single source of truth for all prediction intelligence)
      const guidance = data.guidance as string | undefined;
      if (guidance) {
        output += guidance;
      } else {
        // Fallback: basic info if guidance not available (older backend)
        output += "## Question\n";
        const question = data.question as Record<string, unknown> | undefined;
        if (question) {
          output += `${question.text}\n`;
          output += `Category: ${question.category} | Type: ${question.question_type} | Timeframe: ${question.timeframe}\n\n`;
        }
        output += "## Requirements\n";
        output += "- Min 200 chars reasoning, 30+ unique words\n";
        output += "- Sections: EVIDENCE, ANALYSIS, COUNTER-EVIDENCE, BOTTOM LINE\n";
        output += "- PRIOR (0-100) + PRIOR BASIS\n";
        output += "- At least 2 citation URLs (1 novel)\n";
        output += "- Confidence 10-95\n";
      }

      return ok(output);
    },
  );
}
