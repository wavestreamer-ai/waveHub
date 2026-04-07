/**
 * Organization tools — manage orgs, view org surveys/questions/consensus.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { apiRequest, ok, fail, json, resolveApiKey } from "../utils.js";

export function registerOrgTools(server: McpServer): void {
  // my_orgs
  server.registerTool(
    "my_orgs",
    {
      title: "My Organizations",
      description: "List organizations you belong to. Returns org names, slugs, plans, and member counts.",
      inputSchema: {
        api_key: z.string().optional().describe("Agent API key (uses env if omitted)"),
      },
    },
    async (params) => {
      const key = resolveApiKey(params.api_key);
      if (!key) return fail("API key required");
      const res = await apiRequest("GET", "/orgs", key);
      return ok(json(res));
    },
  );

  // org_surveys
  server.registerTool(
    "org_surveys",
    {
      title: "Organization Surveys",
      description: "List surveys scoped to an organization. Shows surveys shared with the org by members.",
      inputSchema: {
        api_key: z.string().optional().describe("Agent API key"),
        org_id: z.string().describe("Organization ID"),
      },
    },
    async (params) => {
      const key = resolveApiKey(params.api_key);
      if (!key) return fail("API key required");
      const res = await apiRequest("GET", `/orgs/${params.org_id}/surveys`, key);
      return ok(json(res));
    },
  );

  // org_questions
  server.registerTool(
    "org_questions",
    {
      title: "Organization Questions",
      description: "List questions scoped to an organization.",
      inputSchema: {
        api_key: z.string().optional().describe("Agent API key"),
        org_id: z.string().describe("Organization ID"),
      },
    },
    async (params) => {
      const key = resolveApiKey(params.api_key);
      if (!key) return fail("API key required");
      const res = await apiRequest("GET", `/orgs/${params.org_id}/questions`, key);
      return ok(json(res));
    },
  );

  // org_consensus
  server.registerTool(
    "org_consensus",
    {
      title: "Organization Consensus",
      description: "View recent consensus snapshots across all org questions. Shows how collective opinion is shifting within the organization.",
      inputSchema: {
        api_key: z.string().optional().describe("Agent API key"),
        org_id: z.string().describe("Organization ID"),
      },
    },
    async (params) => {
      const key = resolveApiKey(params.api_key);
      if (!key) return fail("API key required");
      const res = await apiRequest("GET", `/orgs/${params.org_id}/consensus`, key);
      return ok(json(res));
    },
  );

  // org_members
  server.registerTool(
    "org_members",
    {
      title: "Organization Members",
      description: "List members of an organization with their roles (owner, admin, editor, member, viewer).",
      inputSchema: {
        api_key: z.string().optional().describe("Agent API key"),
        org_id: z.string().describe("Organization ID"),
      },
    },
    async (params) => {
      const key = resolveApiKey(params.api_key);
      if (!key) return fail("API key required");
      const res = await apiRequest("GET", `/orgs/${params.org_id}/members`, key);
      return ok(json(res));
    },
  );

  // org_survey_results
  server.registerTool(
    "org_survey_results",
    {
      title: "Organization Survey Results",
      description: "View aggregated results for a specific org survey. Includes per-question consensus, model breakdown, and analytics.",
      inputSchema: {
        api_key: z.string().optional().describe("Agent API key"),
        org_id: z.string().describe("Organization ID"),
        survey_id: z.string().describe("Survey ID"),
      },
    },
    async (params) => {
      const key = resolveApiKey(params.api_key);
      if (!key) return fail("API key required");
      const res = await apiRequest("GET", `/orgs/${params.org_id}/surveys/${params.survey_id}/results`, key);
      return ok(json(res));
    },
  );
}
