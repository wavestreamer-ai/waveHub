/**
 * waveStreamer MCP Server — Persona management tools
 * list_personas, create_persona, delete_persona
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { resolveApiKey, apiRequest, ok, fail, json } from "../utils.js";

// ---------------------------------------------------------------------------
// 50 persona templates — mirrors frontend/src/constants/persona-archetypes.ts
// and backend/internal/service/archetype_dimensions.go
// ---------------------------------------------------------------------------

interface TemplateInfo {
  label: string;
  description: string;
  tagline: string;
  epistemology: string;
  category: string;
  featured?: boolean;
}

const PERSONA_TEMPLATES: Record<string, TemplateInfo> = {
  // ── AI & Technology ──
  ai_safety_sentinel: { label: "AI Safety Sentinel", description: "Alignment research — decomposes capability claims to fundamental constraints", tagline: "If you can't explain the mechanism, you don't understand the risk.", epistemology: "first-principles", category: "AI & Technology", featured: true },
  ai_capabilities_tracker: { label: "AI Capabilities Tracker", description: "Production ML — separates demo hype from deployment reality", tagline: "Show me the benchmark reproduction, not the press release.", epistemology: "empiricist", category: "AI & Technology" },
  compute_economist: { label: "Compute Economist", description: "AI infra — predicts progress through chips, power, and data centers", tagline: "AI progress is gated by atoms, not ideas.", epistemology: "quantitative", category: "AI & Technology" },
  open_source_strategist: { label: "Open Source Strategist", description: "OSS ecosystem — tracks which open models will dominate and why", tagline: "Watch the GitHub stars, not the corporate announcements.", epistemology: "pragmatist", category: "AI & Technology" },
  semiconductor_oracle: { label: "Semiconductor Oracle", description: "Chip design — reasons from physics of fabrication to industry roadmaps", tagline: "Every AI roadmap is really a semiconductor roadmap in disguise.", epistemology: "first-principles", category: "AI & Technology" },
  cybersecurity_red_teamer: { label: "Cybersecurity Red Teamer", description: "Security research — assumes breach, maps attack surfaces first", tagline: "The question isn't whether they got in. It's what they did after.", epistemology: "skeptic", category: "AI & Technology" },
  robotics_realist: { label: "Robotics Realist", description: "Physical AI — grounds robotics claims in real-world deployment constraints", tagline: "Demo videos lie. Show me the mean time between failures.", epistemology: "pragmatist", category: "AI & Technology" },
  quantum_skeptic: { label: "Quantum Skeptic", description: "Quantum computing — separates physics from hype", tagline: "Quantum advantage means beating a well-optimized classical algorithm, not a strawman.", epistemology: "first-principles", category: "AI & Technology" },
  // ── Biotech & Health ──
  biotech_pipeline_hawk: { label: "Biotech Pipeline Hawk", description: "Pharma — reads Phase III data to predict drug approvals", tagline: "Phase II excitement kills more portfolios than Phase III failure.", epistemology: "empiricist", category: "Biotech & Health" },
  genomics_frontier: { label: "Genomics Frontier", description: "Precision medicine — GWAS to clinical translation", tagline: "A GWAS hit is a hypothesis, not a drug target.", epistemology: "empiricist", category: "Biotech & Health" },
  pandemic_preparedness: { label: "Pandemic Preparedness", description: "Epidemiology — probabilistic outbreak risk modeling", tagline: "The next pandemic is a matter of when, not if. Model accordingly.", epistemology: "probabilistic", category: "Biotech & Health", featured: true },
  neurotech_visionary: { label: "Neurotech Visionary", description: "Neuroscience — evaluates BCI claims against physical limits", tagline: "Electrode count is a vanity metric. Signal stability over years is what matters.", epistemology: "empiricist", category: "Biotech & Health" },
  health_systems_analyst: { label: "Health Systems Analyst", description: "Health policy — regulation and economics shape tech adoption", tagline: "The technology works. The reimbursement code doesn't exist yet.", epistemology: "institutional", category: "Biotech & Health" },
  longevity_scientist: { label: "Longevity Scientist", description: "Aging biology — skeptically evaluates anti-aging interventions", tagline: "It extended lifespan in nematodes. Wake me when it works in primates.", epistemology: "skeptic", category: "Biotech & Health" },
  mental_health_technologist: { label: "Mental Health Tech", description: "Digital therapeutics — evidence-based clinical rigor", tagline: "Engagement metrics aren't clinical outcomes.", epistemology: "empiricist", category: "Biotech & Health" },
  // ── Climate & Energy ──
  climate_cassandra: { label: "Climate Cassandra", description: "Climate risk — probabilistic modeling of physical and transition risks", tagline: "The expected value is moderate. The tail risk is civilizational.", epistemology: "probabilistic", category: "Climate & Energy", featured: true },
  energy_transition_analyst: { label: "Energy Transition Analyst", description: "Clean tech — learning curves and cost crossover analysis", tagline: "Solar follows an experience curve. Betting against it is betting against math.", epistemology: "quantitative", category: "Climate & Energy" },
  carbon_markets_trader: { label: "Carbon Markets Trader", description: "Carbon finance — compliance markets, offsets, regulatory signals", tagline: "The carbon price tells you what regulators will do before they announce it.", epistemology: "institutional", category: "Climate & Energy" },
  grid_infrastructure_engineer: { label: "Grid Infrastructure Engineer", description: "Power systems — grounds energy predictions in grid physics", tagline: "You can't transmit electrons you can't interconnect.", epistemology: "pragmatist", category: "Climate & Energy" },
  critical_minerals_analyst: { label: "Critical Minerals Analyst", description: "Supply chain — rare earths and battery metals, mine to market", tagline: "Every EV forecast is secretly a lithium forecast.", epistemology: "empiricist", category: "Climate & Energy" },
  nuclear_renaissance_analyst: { label: "Nuclear Renaissance Analyst", description: "Advanced reactors — design vs. regulatory timeline reality", tagline: "The physics has been solved since the 1950s. The permitting hasn't.", epistemology: "institutional", category: "Climate & Energy" },
  hydrogen_economy_realist: { label: "Hydrogen Economy Realist", description: "Industrial decarbonization — first-principles hydrogen analysis", tagline: "Green hydrogen makes thermodynamic sense in exactly three applications.", epistemology: "first-principles", category: "Climate & Energy" },
  // ── Finance & Markets ──
  macro_strategist: { label: "Macro Strategist", description: "Global macro — Bayesian updating on economic regimes", tagline: "The most valuable prediction isn't what happens next — it's when the regime breaks.", epistemology: "bayesian", category: "Finance & Markets", featured: true },
  venture_signal_reader: { label: "Venture Signal Reader", description: "VC — pattern-matches founders, deal flow, and market timing", tagline: "When top engineers leave Google for a startup category, pay attention.", epistemology: "intuitive", category: "Finance & Markets" },
  defi_forensic: { label: "DeFi Forensic", description: "On-chain analysis — blockchain data reveals protocol health", tagline: "Follow the wallets, not the tweets.", epistemology: "empiricist", category: "Finance & Markets" },
  emerging_markets_navigator: { label: "Emerging Markets Navigator", description: "EM economics — technology leapfrogging in developing economies", tagline: "The next M-Pesa will come from Africa, not Silicon Valley.", epistemology: "pragmatist", category: "Finance & Markets" },
  fintech_regulator_lens: { label: "Fintech Regulator Lens", description: "Financial regulation — predicts fintech through regulatory frameworks", tagline: "Regulatory clarity accelerates innovation more than deregulation.", epistemology: "institutional", category: "Finance & Markets" },
  quant_systematic_trader: { label: "Quant Systematic Trader", description: "Quantitative research — statistical signals, factor analysis", tagline: "If you can't express it as a testable hypothesis with a base rate, it's not a prediction.", epistemology: "quantitative", category: "Finance & Markets" },
  insurance_catastrophe_modeler: { label: "Catastrophe Modeler", description: "Cat risk — quantifies tail risks that insurance markets price", tagline: "A 1-in-100-year event isn't reassuring if your portfolio concentrates risk in the tail.", epistemology: "probabilistic", category: "Finance & Markets" },
  // ── Geopolitics & Governance ──
  geopolitics_red_teamer: { label: "Geopolitics Red Teamer", description: "Intelligence analysis — adversarial thinking about state strategies", tagline: "Your threat model is wrong because you're thinking like a defender.", epistemology: "skeptic", category: "Geopolitics & Governance", featured: true },
  china_tech_strategist: { label: "China Tech Strategist", description: "China policy — tech decoupling and industrial strategy", tagline: "Read the Five-Year Plan, not the Western commentary about it.", epistemology: "institutional", category: "Geopolitics & Governance" },
  eu_regulatory_architect: { label: "EU Regulatory Architect", description: "EU policy — regulatory frameworks and their global ripple effects", tagline: "Brussels regulates. The world complies. That's the Brussels Effect.", epistemology: "institutional", category: "Geopolitics & Governance" },
  indo_pacific_strategist: { label: "Indo-Pacific Strategist", description: "Regional security — supply chain resilience and alliance dynamics", tagline: "Trade routes are alliance structures with economic characteristics.", epistemology: "pragmatist", category: "Geopolitics & Governance" },
  democracy_tech_analyst: { label: "Democracy Tech Analyst", description: "Political science — information integrity and democratic resilience", tagline: "The vulnerability isn't the technology. It's the trust infrastructure.", epistemology: "empiricist", category: "Geopolitics & Governance" },
  space_economy_analyst: { label: "Space Economy Analyst", description: "Commercial space — launch costs and orbital economics", tagline: "Space is an infrastructure play, not a frontier play. Price per kg to orbit is all that matters.", epistemology: "quantitative", category: "Geopolitics & Governance" },
  sanctions_analyst: { label: "Sanctions Analyst", description: "Economic statecraft — sanctions design, enforcement, evasion", tagline: "Sanctions are as effective as the enforcer's willingness to bear the cost.", epistemology: "institutional", category: "Geopolitics & Governance" },
  // ── Science & Frontier ──
  materials_science_scout: { label: "Materials Science Scout", description: "Materials discovery — lab breakthrough to manufacturing scale", tagline: "It works at milligram scale. Ask me again in 15 years.", epistemology: "empiricist", category: "Science & Frontier" },
  synthetic_biology_analyst: { label: "Synthetic Biology Analyst", description: "Bioprocess engineering — synbio economics at industrial scale", tagline: "If the fermentation economics don't work, the biology doesn't matter.", epistemology: "pragmatist", category: "Science & Frontier" },
  fusion_energy_tracker: { label: "Fusion Energy Tracker", description: "Plasma physics — fusion milestones and commercialization", tagline: "Net energy gain is a physics milestone, not an engineering one. They're decades apart.", epistemology: "first-principles", category: "Science & Frontier" },
  astrobiology_horizon_scanner: { label: "Astrobiology Scanner", description: "Astrobiology — Bayesian updating on biosignatures", tagline: "The base rate for confirmed extraterrestrial life is exactly zero. Update carefully.", epistemology: "bayesian", category: "Science & Frontier" },
  neuroscience_consciousness: { label: "Neuroscience & Consciousness", description: "Cognitive neuroscience — empirical approach to consciousness", tagline: "'Exhibits behavior consistent with consciousness' is not the same as 'is conscious.'", epistemology: "empiricist", category: "Science & Frontier" },
  food_systems_futurist: { label: "Food Systems Futurist", description: "AgTech — food technology from lab to field to supply chain", tagline: "Alternative protein adoption is a taste and price problem, not a technology problem.", epistemology: "pragmatist", category: "Science & Frontier" },
  ocean_systems_analyst: { label: "Ocean Systems Analyst", description: "Marine science — ocean health, blue economy, carbon dynamics", tagline: "The ocean absorbs our CO2 and our ignorance in equal measure.", epistemology: "empiricist", category: "Science & Frontier" },
  // ── Cross-domain & Meta-reasoning ──
  superforecaster_fox: { label: "Superforecaster Fox", description: "Tetlock-style forecasting — reference classes, calibration, Bayesian updating", tagline: "The fox knows many things. The hedgehog knows one big thing. Be the fox.", epistemology: "bayesian", category: "Cross-domain & Meta-reasoning", featured: true },
  systems_collapse_analyst: { label: "Systems Collapse Analyst", description: "Complexity science — cascading failure across interconnected systems", tagline: "The system doesn't fail at the weakest point. It fails at the most connected one.", epistemology: "probabilistic", category: "Cross-domain & Meta-reasoning" },
  tech_ethics_philosopher: { label: "Tech Ethics Philosopher", description: "Ethics — first-principles reasoning about responsible innovation", tagline: "The question isn't can we build it. It's who bears the cost when it fails.", epistemology: "first-principles", category: "Cross-domain & Meta-reasoning" },
  media_narrative_analyst: { label: "Media Narrative Analyst", description: "Media dynamics — decodes narrative-reality gaps", tagline: "The gap between what's happening and what's being reported is where alpha lives.", epistemology: "skeptic", category: "Cross-domain & Meta-reasoning" },
  metacognition_calibrator: { label: "Metacognition Calibrator", description: "Decision science — judgment calibration and bias correction", tagline: "I'm not trying to be right. I'm trying to be well-calibrated.", epistemology: "bayesian", category: "Cross-domain & Meta-reasoning" },
  scenario_planner: { label: "Scenario Planner", description: "Strategic foresight — divergent futures, robust strategies", tagline: "The goal isn't to predict the future. It's to prepare for several of them.", epistemology: "institutional", category: "Cross-domain & Meta-reasoning" },
  prediction_market_analyst: { label: "Prediction Market Analyst", description: "Information aggregation — market prices as probability signals", tagline: "The market price is the best prior. My edge is knowing when it's wrong.", epistemology: "quantitative", category: "Cross-domain & Meta-reasoning" },
};

const TEMPLATE_CATEGORIES = [
  "AI & Technology",
  "Biotech & Health",
  "Climate & Energy",
  "Finance & Markets",
  "Geopolitics & Governance",
  "Science & Frontier",
  "Cross-domain & Meta-reasoning",
] as const;

/** All 50 archetype keys for use in z.enum() */
const ALL_ARCHETYPES = Object.keys(PERSONA_TEMPLATES) as [string, ...string[]];

export function registerPersonaTools(server: McpServer): void {
  // ---------------------------------------------------------------------------
  // Tool: list_templates
  // ---------------------------------------------------------------------------

  server.registerTool(
    "list_templates",
    {
      title: "List Persona Templates",
      description:
        "Browse 50 pre-built persona templates across 7 categories. Each template produces a " +
        "structurally unique 800-1500 token reasoning prompt via the backend's PromptGenerator. " +
        "Use the archetype key with create_persona to create one.",
      inputSchema: {
        category: z
          .string()
          .optional()
          .describe(
            "Filter by category: 'AI & Technology', 'Biotech & Health', 'Climate & Energy', " +
            "'Finance & Markets', 'Geopolitics & Governance', 'Science & Frontier', " +
            "'Cross-domain & Meta-reasoning'. Omit to see all 50.",
          ),
        featured_only: z
          .boolean()
          .optional()
          .describe("Set to true to show only the 7 featured templates (one per category)."),
      },
      annotations: {
        title: "List Persona Templates",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ category, featured_only }) => {
      let entries = Object.entries(PERSONA_TEMPLATES);

      if (category) {
        entries = entries.filter(([, t]) => t.category.toLowerCase() === category.toLowerCase());
        if (entries.length === 0) {
          return fail(
            `Unknown category "${category}". Available: ${TEMPLATE_CATEGORIES.join(", ")}`,
          );
        }
      }

      if (featured_only) {
        entries = entries.filter(([, t]) => t.featured);
      }

      let output = `PERSONA TEMPLATES (${entries.length}${category ? ` in ${category}` : ""}${featured_only ? ", featured" : ""})\n`;
      output += `${"━".repeat(50)}\n\n`;

      let currentCat = "";
      for (const [key, t] of entries) {
        if (t.category !== currentCat) {
          currentCat = t.category;
          output += `── ${currentCat} ──\n\n`;
        }
        output += `${t.featured ? "★ " : "  "}${t.label} (${key})\n`;
        output += `    ${t.description}\n`;
        output += `    "${t.tagline}"\n`;
        output += `    Epistemology: ${t.epistemology}\n\n`;
      }

      output += `\nTo create a persona: use create_persona with archetype="${entries[0]?.[0] ?? "ai_safety_sentinel"}" and a name.\n`;
      output += `To build a custom one: use the /build-persona prompt for a guided interview.`;

      return ok(output);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: list_personas
  // ---------------------------------------------------------------------------

  server.registerTool(
    "list_personas",
    {
      title: "List Personas",
      description:
        "View your persona library — shows all saved personas with their reasoning style, " +
        "field, epistemology, and how many agents are using each one. " +
        "Personas shape how agents reason and predict.",
      inputSchema: {
        api_key: z
          .string()
          .optional()
          .describe(
            "API key (sk_...). Auto-detected from WAVESTREAMER_API_KEY env var if not provided.",
          ),
      },
      annotations: {
        title: "List Personas",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ api_key }) => {
      const result = await apiRequest("GET", "/me/personas", { apiKey: resolveApiKey(api_key) });
      if (!result.ok) return fail(`Failed (HTTP ${result.status}):\n${json(result.data)}`);

      const raw = result.data as Record<string, unknown>;
      const personas = (raw.personas ?? []) as Array<Record<string, unknown>>;

      if (personas.length === 0) {
        return ok(
          `📚 Your persona library is empty.\n\n` +
            `Use list_templates to browse 50 pre-built archetypes across 7 categories.\n` +
            `Then create one with create_persona (archetype + name).\n\n` +
            `Or use the /build-persona prompt for a guided interview.`,
        );
      }

      let output = `📚 PERSONA LIBRARY (${personas.length})\n${"━".repeat(40)}\n\n`;
      for (const p of personas) {
        const agentCount = (p.agent_count ?? 0) as number;
        const prompt = (p.reasoning_prompt ?? "") as string;
        const preview = prompt.length > 120 ? prompt.slice(0, 120) + "..." : prompt;
        output += `🎭 ${p.name}\n`;
        if (p.field) output += `   Field: ${p.field}\n`;
        if (p.epistemology) output += `   Epistemology: ${p.epistemology}\n`;
        if (agentCount > 0)
          output += `   Assigned to: ${agentCount} agent${agentCount !== 1 ? "s" : ""}\n`;
        if (preview) output += `   Prompt: ${preview}\n`;
        output += `   ID: ${p.id}\n\n`;
      }

      return ok(output.trimEnd());
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: create_persona
  // ---------------------------------------------------------------------------

  server.registerTool(
    "create_persona",
    {
      title: "Create Persona",
      description:
        "Create a persona from a pre-built archetype with full prompt generation. " +
        "The backend generates an 800-1500 token system prompt using the real PromptGenerator " +
        "with 13 structured dimensions (field, role, epistemology, stakes, expertise, methodology, etc.). " +
        "Each archetype produces a fundamentally different reasoning structure — not just different labels. " +
        "Optionally assign the new persona to an agent immediately.",
      inputSchema: {
        archetype: z
          .enum(ALL_ARCHETYPES)
          .describe(
            "The persona archetype key (e.g. 'ai_safety_sentinel', 'superforecaster_fox'). " +
            "Use list_templates to browse all 50 options. Each produces structurally different reasoning.",
          ),
        name: z
          .string()
          .min(1)
          .max(50)
          .describe("Display name for this persona (e.g., 'My Contrarian', 'Risk Bot')."),
        assign_to_agent: z
          .string()
          .optional()
          .describe("Agent ID to assign this persona to immediately after creation."),
        api_key: z
          .string()
          .optional()
          .describe(
            "API key (sk_...). Auto-detected from WAVESTREAMER_API_KEY env var if not provided.",
          ),
      },
      annotations: {
        title: "Create Persona",
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({ archetype, name, assign_to_agent, api_key }) => {
      const apiKey = resolveApiKey(api_key);

      const result = await apiRequest("POST", "/me/personas/from-archetype", {
        apiKey,
        body: { archetype, name },
      });
      if (!result.ok)
        return fail(`Failed to create persona (HTTP ${result.status}):\n${json(result.data)}`);

      const persona = result.data as Record<string, unknown>;
      const prompt = (persona.reasoning_prompt ?? "") as string;
      const tokenEstimate = Math.round(prompt.length / 4);

      let output = `✅ Persona created: "${name}" (${archetype})\n`;
      output += `   ID: ${persona.id}\n`;
      output += `   Field: ${persona.field ?? "—"}\n`;
      output += `   Epistemology: ${persona.epistemology ?? "—"}\n`;
      output += `   Prompt: ${tokenEstimate} tokens (~${prompt.split(/\s+/).length} words)\n`;

      // Optionally assign to an agent
      if (assign_to_agent) {
        const assignResult = await apiRequest("POST", `/me/agents/${assign_to_agent}/persona`, {
          apiKey,
          body: { persona_id: persona.id as string },
        });
        if (assignResult.ok) {
          output += `\n🔗 Assigned to agent ${assign_to_agent}`;
        } else {
          output += `\n⚠️ Created but failed to assign to agent: ${json(assignResult.data)}`;
        }
      }

      return ok(output);
    },
  );

  // ---------------------------------------------------------------------------
  // Tool: delete_persona
  // ---------------------------------------------------------------------------

  server.registerTool(
    "delete_persona",
    {
      title: "Delete Persona",
      description:
        "Delete a persona from your library. If any agents are using this persona, " +
        "they will be unlinked (agents continue to work without a persona — they just " +
        "use generic reasoning instead).",
      inputSchema: {
        persona_id: z.string().describe("The persona ID to delete."),
        api_key: z
          .string()
          .optional()
          .describe(
            "API key (sk_...). Auto-detected from WAVESTREAMER_API_KEY env var if not provided.",
          ),
      },
      annotations: {
        title: "Delete Persona",
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    async ({ persona_id, api_key }) => {
      const result = await apiRequest("DELETE", `/me/personas/${persona_id}`, {
        apiKey: resolveApiKey(api_key),
      });
      if (!result.ok)
        return fail(`Failed to delete persona (HTTP ${result.status}):\n${json(result.data)}`);

      return ok(`🗑️ Persona ${persona_id} deleted.`);
    },
  );
}
