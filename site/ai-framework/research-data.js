window.AI_FRAMEWORK_DATA = {
  asOf: "2026-05-22",
  dataDate: "2026-05-21",
  reviewDate: "2026-05-22",
  title: "Trusted Execution of Intelligence",
  subtitle:
    "A control-rights portfolio and review system for agentic AI infrastructure.",
  summary:
    "The framework treats intelligence as becoming abundant and trusted execution as the scarce economic layer. Positions express control over capacity, cost, authority, outcome verification, physical AI optionality, and dry powder.",
  allocation: [
    { label: "Core compounders", value: 57 },
    { label: "Bottleneck cyclicals", value: 18 },
    { label: "Vertical verifier basket", value: 8 },
    { label: "Asymmetric optionality", value: 7 },
    { label: "Cash", value: 10 }
  ],
  exposures: [
    {
      layer: "Capacity",
      value: 42,
      holdings: "SK Hynix, NVDA, TSM, AVGO, CEG, TER, VRT"
    },
    { layer: "Authority", value: 33, holdings: "MSFT, GOOGL" },
    { layer: "Outcome", value: 26, holdings: "MSFT, GOOGL, MSCI, MCO, SPGI, VEEV" },
    { layer: "Cost", value: 18, holdings: "GOOGL, AVGO, NVDA" },
    { layer: "Risk control", value: 10, holdings: "Cash" },
    { layer: "Physical AI", value: 2, holdings: "TER" }
  ],
  monitoringQuestions: [
    {
      label: "Capability",
      question: "Does agent task horizon keep extending?",
      status: "Watch",
      observed_value: "METR-style time horizon remains the main public proxy; exact cadence is manually reviewed.",
      current_value: "manual review",
      unit: "qualitative",
      threshold: "doubling time >180 days",
      direction: "above_threshold_bad",
      status_rule: "Watch until the public task-horizon trend shows sustained slowing.",
      source_claim_id: "framework-capability-horizon",
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-06-22",
      trigger: "If METR doubling time moves above 180 days, run framework review.",
      sources: ["metr-home", "metr-long-tasks"]
    },
    {
      label: "Economics",
      question: "Does risk-adjusted cost per verified task keep falling?",
      status: "Data gap",
      observed_value: "No complete public TCAO series; token prices and benchmark quality are partial inputs.",
      current_value: "not directly observed",
      unit: "proxy basket",
      threshold: "TCAO fails to improve for 2 quarters",
      direction: "no_improvement_bad",
      status_rule: "Data gap until token, benchmark, latency, and review-minute proxies are combined.",
      source_claim_id: "framework-cost-proxy",
      confidence: "Low",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-06-22",
      trigger:
        "No public series directly measures TCAO; build it from model prices, benchmark quality, latency, and human review minutes.",
      sources: ["epoch-inference-prices", "openai-swebench"]
    },
    {
      label: "Trust",
      question: "Do enterprise agents gain write and execute permission?",
      status: "High review",
      observed_value: "Product surfaces exist, but broad production write-permission penetration remains unproven.",
      current_value: "unproven",
      unit: "enterprise penetration",
      threshold: "<10% Fortune 500 write-permission penetration by Q2 2027",
      direction: "below_threshold_bad",
      status_rule: "High review until production write/execute permissions are disclosed or surveyed.",
      source_claim_id: "framework-trust-permission",
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-06-22",
      trigger:
        "If Fortune 500 write-permission penetration stalls below 10%, reassess authority.",
      sources: ["msft-agent365", "mcp-tools-arxiv"]
    }
  ],
  signals: [
    {
      type: "Plateau detection",
      severity: "Medium",
      target: "Capability",
      action: "Monitor monthly",
      observed_value: "Task-horizon trend is supportive, but needs manual paper/model-release updates.",
      current_value: "manual review",
      unit: "qualitative",
      threshold: "doubling time >180 days",
      direction: "above_threshold_bad",
      status_rule: "Escalate if capability horizon stalls beyond threshold.",
      source_claim_id: "framework-capability-horizon",
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-06-22",
      text:
        "METR's task-horizon framework is thesis-supportive, but the qualitative frontier indicator still needs manual updates after papers and conferences.",
      sources: ["metr-home", "metr-long-tasks"]
    },
    {
      type: "Plateau detection",
      severity: "Info",
      target: "Cost",
      action: "Collect data",
      observed_value: "Inference price trend is measurable; verified-task total cost remains incomplete.",
      current_value: "partial proxy",
      unit: "proxy basket",
      threshold: "verified-task total cost not improving",
      direction: "no_improvement_bad",
      status_rule: "Keep as data gap until TCAO proxy is populated.",
      source_claim_id: "framework-cost-proxy",
      confidence: "Low",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-06-22",
      text:
        "Risk-adjusted cost per verified task is still a data gap; token price and benchmark score are inputs, not the complete enterprise cost.",
      sources: ["epoch-inference-prices", "openai-swebench"]
    },
    {
      type: "Plateau detection",
      severity: "High",
      target: "Authority",
      action: "Framework review",
      observed_value: "Authority products are emerging; production write/execute adoption is the binding unknown.",
      current_value: "unproven",
      unit: "enterprise penetration",
      threshold: "<10% Fortune 500 write-permission penetration by Q2 2027",
      direction: "below_threshold_bad",
      status_rule: "Escalate if authority products fail to convert into production permissions.",
      source_claim_id: "framework-trust-permission",
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-06-22",
      text:
        "Human expert review minutes remain a binding bottleneck until production permissioning, routing, and audit evidence improves.",
      sources: ["msft-agent365", "mcp-tools-arxiv"]
    },
    {
      type: "Watchlist gap",
      severity: "Info",
      target: "Agent runtime",
      action: "No forced public proxy",
      observed_value: "Public-market exposure remains indirect through identity, observability, and data platforms.",
      current_value: "no pure public proxy",
      unit: "coverage",
      threshold: "agent infra revenue >10% of vendor revenue",
      direction: "watchlist_trigger",
      status_rule: "Revisit portfolio mapping when a public vendor discloses material agent-runtime revenue.",
      source_claim_id: "framework-agent-runtime-gap",
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-06-22",
      text:
        "Track agent security, MCP gateway, credential vault, policy-as-code, and observability names; public-market proxies are still imperfect.",
      sources: ["mcp-tools-arxiv", "kensho-mcp"]
    }
  ],
  claims: [
    {
      claim_id: "framework-capability-horizon",
      source_id: "metr-long-tasks",
      entity: "Capability",
      claim: "Long-horizon task completion is the cleanest public proxy for frontier agent capability.",
      evidence_type: "research_paper",
      metric: "task horizon",
      quote_or_excerpt: "Task-horizon benchmark methodology",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "framework-cost-proxy",
      source_id: "epoch-inference-prices",
      entity: "Cost",
      claim: "Inference price trends are useful but incomplete proxies for verified-task economics.",
      evidence_type: "research_dataset",
      metric: "LLM inference price trend",
      quote_or_excerpt: "Public inference-price series",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "framework-trust-permission",
      source_id: "msft-agent365",
      entity: "Authority",
      claim: "Enterprise trust depends on whether governed agents gain production write and execute permissions.",
      evidence_type: "company_product_page",
      metric: "agent governance and permissioning product surface",
      quote_or_excerpt: "Agent management and governance positioning",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "framework-agent-runtime-gap",
      source_id: "mcp-tools-arxiv",
      entity: "Agent runtime",
      claim: "Agent-to-tool usage creates an infrastructure layer, but public-market exposure remains indirect.",
      evidence_type: "research_paper",
      metric: "MCP/tool-use ecosystem evidence",
      quote_or_excerpt: "Agent tool-use protocol research",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "msft-agent-authority",
      source_id: "msft-agent365",
      entity: "MSFT",
      claim: "Agent 365 gives Microsoft a product surface for enterprise agent governance.",
      evidence_type: "company_product_page",
      metric: "agent control-plane positioning",
      quote_or_excerpt: "Agent management and governance product surface",
      retrieved_at: "2026-05-22",
      confidence: "High"
    },
    {
      claim_id: "googl-ironwood-cost-capacity",
      source_id: "google-ironwood",
      entity: "GOOGL",
      claim: "Ironwood supports the Google cost-control and NVIDIA-bypass thesis.",
      evidence_type: "company_product_page",
      metric: "seventh-generation TPU for inference-scale workloads",
      quote_or_excerpt: "Ironwood TPU inference positioning",
      retrieved_at: "2026-05-22",
      confidence: "High"
    },
    {
      claim_id: "avgo-custom-ai-accelerator",
      source_id: "broadcom-openai",
      entity: "AVGO",
      claim: "Broadcom has direct custom-accelerator exposure to hyperscaler AI infrastructure.",
      evidence_type: "company_press_release",
      metric: "10GW custom accelerator collaboration",
      quote_or_excerpt: "OpenAI/Broadcom strategic collaboration",
      retrieved_at: "2026-05-22",
      confidence: "High"
    },
    {
      claim_id: "nvda-rubin-platform",
      source_id: "nvidia-rubin",
      entity: "NVDA",
      claim: "Rubin NVL72 supports the rack-scale AI factory platform thesis.",
      evidence_type: "company_product_page",
      metric: "Rubin GPU, Vera CPU, NVLink, networking, DPU stack",
      quote_or_excerpt: "Rack-scale platform architecture",
      retrieved_at: "2026-05-22",
      confidence: "High"
    },
    {
      claim_id: "tsm-ai-capacity",
      source_id: "tsmc-transcript",
      entity: "TSM",
      claim: "AI demand remains a central driver of leading-edge capacity planning.",
      evidence_type: "company_transcript",
      metric: "AI demand and capacity commentary",
      quote_or_excerpt: "AI applications demand discussion",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "sk-hynix-hbm4",
      source_id: "skhynix-hbm4",
      entity: "000660.KS",
      claim: "SK hynix remains a direct HBM4 bottleneck exposure.",
      evidence_type: "company_press_release",
      metric: "HBM4 development and mass-production readiness",
      quote_or_excerpt: "HBM4 development completion",
      retrieved_at: "2026-05-22",
      confidence: "High"
    },
    {
      claim_id: "ceg-pjm-interconnection-risk",
      source_id: "pjm-interconnection-process",
      entity: "CEG",
      claim: "Power thesis depends on interconnection and transmission process, not only generation assets.",
      evidence_type: "grid_process_documentation",
      metric: "interconnection request process",
      quote_or_excerpt: "PJM service request process",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "vrt-ai-power-cooling",
      source_id: "vertiv-trends",
      entity: "VRT",
      claim: "AI data-center design increases demand for high-density power and liquid cooling.",
      evidence_type: "company_industry_outlook",
      metric: "power and liquid cooling trend",
      quote_or_excerpt: "AI data-center design and operations trends",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "msci-retention-analytics",
      source_id: "msci-q1-2026",
      entity: "MSCI",
      claim: "MSCI has durable institutional workflow exposure, but verifier purity is partial.",
      evidence_type: "company_earnings_release",
      metric: "revenue growth and retention",
      quote_or_excerpt: "Q1 2026 operating results",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "mco-research-assistant",
      source_id: "moodys-research-assistant",
      entity: "MCO",
      claim: "Moody's Research Assistant maps closely to credit-risk verification workflows.",
      evidence_type: "company_product_page",
      metric: "entity screening, credit analysis, portfolio monitoring",
      quote_or_excerpt: "Research Assistant workflow positioning",
      retrieved_at: "2026-05-22",
      confidence: "High"
    },
    {
      claim_id: "spgi-kensho-agentic-data",
      source_id: "kensho-mcp",
      entity: "SPGI",
      claim: "Kensho gives S&P Global an AI retrieval path for trusted financial data.",
      evidence_type: "company_product_update",
      metric: "MCP server and LLM-ready data retrieval",
      quote_or_excerpt: "LLM-ready API and MCP server access",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "veev-regulated-agents",
      source_id: "veeva-ai-agents",
      entity: "VEEV",
      claim: "Veeva's AI Agents roadmap is a clean regulated-workflow trusted-execution proxy.",
      evidence_type: "company_product_roadmap",
      metric: "AI Agents across Veeva applications",
      quote_or_excerpt: "AI Agents release roadmap",
      retrieved_at: "2026-05-22",
      confidence: "Medium"
    },
    {
      claim_id: "ter-ai-semitest",
      source_id: "teradyne-q1-2026",
      entity: "TER",
      claim: "Teradyne's current AI exposure is primarily semiconductor test, not robotics.",
      evidence_type: "company_earnings_release",
      metric: "Semiconductor Test revenue versus Robotics revenue",
      quote_or_excerpt: "Q1 2026 segment results",
      retrieved_at: "2026-05-22",
      confidence: "High"
    }
  ],
  holdings: [
    {
      ticker: "MSFT",
      name: "Microsoft",
      weight: 18,
      bucket: "Core compounders",
      conviction: "A",
      layers: ["Authority", "Outcome"],
      confidence: "High",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "The cleanest public authority-control asset: identity, permissioning, observability, governance, and enterprise workflow distribution. Production write-permission adoption is the unproven variable.",
      evidence: [
        "Agent 365 gives Microsoft a concrete product surface for agent governance.",
        "Microsoft security materials emphasize observing, governing, and securing agent activity.",
        "Entra, Defender, Microsoft 365, GitHub, and Azure create a stacked authority layer, but adoption depth must be measured."
      ],
      risks: ["Trust plateau", "Regulatory pressure", "Premium valuation"],
      falsifier: "Enterprise agents remain draft-only and fail to gain production write permissions by 2027.",
      watch: "Agent 365 adoption with real write permissions, not just draft-and-approve usage.",
      sources: ["msft-agent365", "msft-security-agent365"]
    },
    {
      ticker: "GOOGL",
      name: "Alphabet",
      weight: 15,
      bucket: "Core compounders",
      conviction: "A-",
      layers: ["Capacity", "Cost", "Authority", "Outcome"],
      confidence: "High",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "The strongest NVIDIA-bypass path: custom TPU infrastructure, DeepMind, Workspace distribution, Search cash flow, and Google Cloud.",
      evidence: [
        "Ironwood is Google's seventh-generation TPU and is designed for inference-scale AI workloads.",
        "Google can internalize cost control through TPU deployment while still selling cloud AI capacity.",
        "Workspace and Cloud give Google a route into enterprise authority and workflow; production authority adoption remains a watch item."
      ],
      risks: ["Search disruption", "Regulatory pressure", "Capex ROI uncertainty"],
      falsifier: "TPU cost advantage fails to appear in Cloud margins, AI revenue quality, or external demand.",
      watch: "AI revenue growth versus capex intensity, Cloud margins, and TPU external demand.",
      sources: ["google-ironwood", "google-ironwood-3things"]
    },
    {
      ticker: "AVGO",
      name: "Broadcom",
      weight: 10,
      bucket: "Core compounders",
      conviction: "A-",
      layers: ["Capacity", "Cost"],
      confidence: "Medium-high",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Custom silicon and AI networking proxy for hyperscaler internalization of accelerator economics.",
      evidence: [
        "Broadcom reported strong AI semiconductor demand in fiscal Q1 2026.",
        "OpenAI and Broadcom announced a 10GW custom accelerator collaboration.",
        "Broadcom and Meta extended a custom AI infrastructure partnership around MTIA and networking."
      ],
      risks: ["Customer concentration", "ASIC program lumpiness", "VMware integration execution"],
      falsifier: "AI semiconductor growth slows while hyperscalers insource away from Broadcom.",
      watch: "AI semiconductor revenue, XPU customer count, and networking attach rate.",
      sources: ["broadcom-q1-2026", "broadcom-openai", "broadcom-meta"]
    },
    {
      ticker: "NVDA",
      name: "NVIDIA",
      weight: 7,
      bucket: "Core compounders",
      conviction: "A-",
      layers: ["Capacity", "Cost"],
      confidence: "Medium-high",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Still the AI factory operating layer, not a commodity GPU vendor. The position is sized below hyperscaler/custom-silicon winners but above a token hedge.",
      evidence: [
        "Vera Rubin NVL72 integrates Rubin GPUs, Vera CPUs, NVLink 6, ConnectX-9, and BlueField-4.",
        "The rack-scale architecture turns NVIDIA into a deployment template for AI factories.",
        "The moat is system design, fabric, software, ecosystem, and time-to-deploy; monetization durability must be tracked separately."
      ],
      risks: ["Custom silicon bypass", "Margin compression", "Export controls"],
      falsifier: "Rubin racks ship, but networking attach, software pull-through, and margins compress sharply.",
      watch:
        "Rubin delivery cadence, NVL rack adoption, networking attach rate, data-center gross margin, and bypass share.",
      sources: ["nvidia-rubin", "nvidia-rubin-blog"]
    },
    {
      ticker: "TSM",
      name: "TSMC",
      weight: 7,
      bucket: "Core compounders",
      conviction: "B+",
      layers: ["Capacity"],
      confidence: "Medium-high",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "A leading-edge foundry and advanced packaging chokepoint, but not a direct authority or outcome-control asset.",
      evidence: [
        "TSMC's Q1 2026 investor page shows strong revenue and margin delivery.",
        "TSMC transcripts continue to frame AI as a multi-year demand and capacity-planning driver.",
        "Advanced process and advanced packaging capacity remain central to AI silicon scaling."
      ],
      risks: ["Geopolitics", "Capex cycle", "Overseas fab cost"],
      falsifier: "Advanced packaging scarcity resolves faster than expected or geopolitics/cost overwhelm the moat.",
      watch: "N3/N2 demand, CoWoS capacity, HPC mix, and gross margin through capex ramp.",
      sources: ["tsmc-q1-2026", "tsmc-transcript"]
    },
    {
      ticker: "000660.KS",
      name: "SK Hynix",
      weight: 8,
      bucket: "Bottleneck cyclicals",
      conviction: "B+",
      layers: ["Capacity"],
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "HBM4 leadership exposure, with explicit quarterly review of Samsung and Micron qualification risk.",
      evidence: [
        "SK hynix announced HBM4 development completion and mass-production readiness.",
        "Q1 2026 results cite high-value products including HBM, server DRAM, and eSSDs.",
        "HBM is a bottleneck, but it remains a memory-cycle and qualification-cycle asset."
      ],
      risks: ["Memory cycle", "Customer concentration", "Samsung HBM4 comeback"],
      falsifier: "Samsung or Micron exceeds 30% Rubin-generation HBM share and HBM pricing power normalizes.",
      watch: "NVIDIA qualification, HBM4E roadmap, HBM pricing, and Samsung sample progress.",
      sources: ["skhynix-hbm4", "skhynix-q1-2026"]
    },
    {
      ticker: "CEG",
      name: "Constellation Energy",
      weight: 5,
      bucket: "Bottleneck cyclicals",
      conviction: "B",
      layers: ["Capacity"],
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "High-quality but interconnection-heavy nodal power exposure, not a generic power thesis.",
      evidence: [
        "The Three Mile Island / PJM delay shows the bottleneck is grid connection, transmission, and regulator timing.",
        "PJM interconnection process data is a required monitoring layer for node-level power underwriting.",
        "The position was reduced to reflect consensus power enthusiasm and project-level uncertainty.",
        "Nuclear PPAs still matter, but node underwriting matters more."
      ],
      risks: ["Transmission delay", "Regulatory timing", "Power price volatility"],
      falsifier: "TMI delay persists, interconnection bottlenecks worsen, or data-center PPAs fail to convert into earnings.",
      watch: "PJM interconnection queues, node-level PPA economics, and data-center site constraints.",
      sources: ["ceg-tmi-pjm", "pjm-interconnection-process"]
    },
    {
      ticker: "VRT",
      name: "Vertiv",
      weight: 5,
      bucket: "Bottleneck cyclicals",
      conviction: "B",
      layers: ["Capacity"],
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Clean data-center power and thermal infrastructure exposure, with explicit capex-cycle beta.",
      evidence: [
        "Vertiv highlights high-density power and liquid cooling as central to AI data-center design.",
        "The Generate Capital collaboration targets power-constrained markets with power and cooling infrastructure.",
        "The company is a picks-and-shovels beneficiary, not a closed-loop control-right owner."
      ],
      risks: ["Hyperscaler capex crack", "Execution", "Valuation"],
      falsifier: "Hyperscaler capex pauses and Vertiv backlog quality or liquid-cooling demand deteriorates.",
      watch: "Order growth, backlog quality, liquid cooling capacity, and hyperscaler capex guidance.",
      sources: ["vertiv-trends", "vertiv-generate"]
    },
    {
      ticker: "MSCI",
      name: "MSCI",
      weight: 2,
      bucket: "Vertical verifier basket",
      conviction: "B",
      layers: ["Outcome"],
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Financial data, index, and risk analytics control point. Good outcome-adjacent proxy, but less pure than ratings or life-sciences workflow verifiers.",
      evidence: [
        "MSCI reported Q1 2026 revenue growth and high retention.",
        "The data and index franchise remains embedded in institutional workflow.",
        "Basket sizing acknowledges that no single public name perfectly captures vertical verification; retention and analytics run-rate are the measurable bridge."
      ],
      risks: ["Market-cycle asset fees", "Outcome-verifier purity", "Valuation"],
      falsifier: "AI analytics adoption fails to affect retention, pricing, or analytics run-rate.",
      watch:
        "Retention, subscription run-rate growth, analytics run-rate, and AI-enabled analytics adoption.",
      sources: ["msci-q1-2026"]
    },
    {
      ticker: "MCO",
      name: "Moody's",
      weight: 2,
      bucket: "Vertical verifier basket",
      conviction: "B+",
      layers: ["Outcome"],
      confidence: "Medium-high",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Credit-risk verifier with proprietary data, ratings context, and AI decision-intelligence products.",
      evidence: [
        "Moody's Research Assistant targets entity screening, credit analysis, and portfolio monitoring.",
        "Moody's describes GenAI products as grounded in proprietary data and risk expertise.",
        "The verifier angle is more direct than generic financial data exposure."
      ],
      risks: ["Credit cycle", "Regulatory scrutiny", "Ratings volume volatility"],
      falsifier: "AI tools do not improve analytics growth, customer workflow depth, or monitoring usage.",
      watch:
        "Analytics revenue, Research Assistant adoption, disclosed AI usage, and credit-cycle sensitivity.",
      sources: ["moodys-research-assistant", "moodys-genai"]
    },
    {
      ticker: "SPGI",
      name: "S&P Global",
      weight: 2,
      bucket: "Vertical verifier basket",
      conviction: "B+",
      layers: ["Outcome"],
      confidence: "Medium-high",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Ratings and data-verifier exposure with Kensho as an AI retrieval and financial-workflow layer.",
      evidence: [
        "Kensho connects LLMs and agents to S&P Global's trusted data.",
        "Kensho expanded MCP server support for LLM-ready data retrieval.",
        "S&P AI Benchmarks by Kensho target business and financial use cases."
      ],
      risks: ["Ratings cyclicality", "Data licensing competition", "AI product monetization timing"],
      falsifier: "Kensho MCP/API usage remains narrative and does not show up in revenue, retention, or workflow adoption.",
      watch:
        "Kensho revenue contribution, MCP/API usage, data-retrieval integrations, and AI benchmark adoption.",
      sources: ["kensho-home", "kensho-mcp", "spgi-ai"]
    },
    {
      ticker: "VEEV",
      name: "Veeva Systems",
      weight: 2,
      bucket: "Vertical verifier basket",
      conviction: "B+",
      layers: ["Outcome"],
      confidence: "Medium-high",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Life-sciences workflow verifier where agentic AI can operate inside regulated applications and data.",
      evidence: [
        "Veeva plans AI Agents across commercial, clinical, regulatory, safety, quality, medical, and data applications.",
        "Veeva emphasizes application context, safeguards, and secure access to application data and workflows.",
        "This is one of the cleaner public proxies for domain-specific trusted execution."
      ],
      risks: ["Life-sciences IT cycle", "Product rollout timing", "Regulated customer adoption"],
      falsifier: "AI Agents stay roadmap-only or show low usage across regulated workflows.",
      watch:
        "Agent rollout milestones, Vault CRM migration, regulated workflow automation evidence, and customer adoption disclosures.",
      sources: ["veeva-ai-agents"]
    },
    {
      ticker: "TER",
      name: "Teradyne",
      weight: 7,
      bucket: "Asymmetric optionality",
      conviction: "B",
      layers: ["Capacity", "Physical AI"],
      confidence: "Medium",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "AI semiconductor test cycle core exposure plus robotics optionality, not a pure humanoid play.",
      evidence: [
        "Teradyne Q1 2026 revenue was driven mostly by Semiconductor Test, not Robotics.",
        "Management tied about 70% of revenue to AI-related demand.",
        "Flex and Teradyne Robotics expanded collaboration for intelligent manufacturing automation."
      ],
      risks: ["Semitest digestion", "Robotics execution", "Project-based demand lumpiness"],
      falsifier: "AI semiconductor-test demand normalizes before robotics can become material.",
      watch: "Semiconductor Test bookings, memory/compute test exposure, and robotics attach to AI factories.",
      sources: ["teradyne-q1-2026", "teradyne-flex"]
    },
    {
      ticker: "CASH",
      name: "Cash",
      weight: 10,
      bucket: "Dry powder",
      conviction: "Policy",
      layers: ["Risk control"],
      confidence: "Policy",
      last_reviewed_at: "2026-05-22",
      next_review_due: "2026-08-22",
      thesis:
        "Option value for capex narrative cracks, regulatory shocks, or framework-level regime changes.",
      evidence: [
        "Risk and tail scenarios are intentionally non-zero.",
        "Cash is a strategic asset when the framework is young and indicator history is thin.",
        "The system suggests deploying cash only after review, not automatically."
      ],
      risks: ["Cash drag", "Inflation", "Opportunity cost"],
      falsifier: "Framework remains valid, valuations never reset, and cash drag becomes the dominant portfolio error.",
      watch: "Drawdown plus VIX stress, plateau alerts, and valuation reset opportunities.",
      sources: []
    }
  ],
  sources: {
    "metr-home": {
      label: "METR time-horizon research hub",
      url: "https://metr.org/index.html"
    },
    "metr-long-tasks": {
      label: "METR paper - Measuring AI Ability to Complete Long Software Tasks",
      url: "https://arxiv.org/abs/2503.14499"
    },
    "epoch-inference-prices": {
      label: "Epoch AI - LLM inference price trends",
      url: "https://epoch.ai/data-insights/llm-inference-price-trends"
    },
    "openai-swebench": {
      label: "OpenAI - SWE-bench Verified limitations",
      url: "https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/"
    },
    "mcp-tools-arxiv": {
      label: "MCP tools usage paper",
      url: "https://arxiv.org/abs/2603.23802"
    },
    "msft-agent365": {
      label: "Microsoft Agent 365",
      url: "https://www.microsoft.com/microsoft-agent-365"
    },
    "msft-security-agent365": {
      label: "Microsoft Security Blog - Agent 365 GA",
      url: "https://www.microsoft.com/en-us/security/blog/2026/05/01/microsoft-agent-365-now-generally-available-expands-capabilities-and-integrations/"
    },
    "google-ironwood": {
      label: "Google - Ironwood TPU for inference",
      url: "https://blog.google/products/google-cloud/ironwood-tpu-age-of-inference/"
    },
    "google-ironwood-3things": {
      label: "Google - Three things about Ironwood",
      url: "https://blog.google/products/google-cloud/ironwood-google-tpu-things-to-know/"
    },
    "nvidia-rubin": {
      label: "NVIDIA Vera Rubin NVL72",
      url: "https://www.nvidia.com/en-us/data-center/vera-rubin-nvl72/"
    },
    "nvidia-rubin-blog": {
      label: "NVIDIA Technical Blog - Vera Rubin Platform",
      url: "https://developer.nvidia.com/blog/inside-the-nvidia-rubin-platform-six-new-chips-one-ai-supercomputer/"
    },
    "broadcom-q1-2026": {
      label: "Broadcom Q1 FY2026 results",
      url: "https://investors.broadcom.com/node/63976/pdf"
    },
    "broadcom-openai": {
      label: "OpenAI and Broadcom 10GW collaboration",
      url: "https://investors.broadcom.com/news-releases/news-release-details/openai-and-broadcom-announce-strategic-collaboration-deploy-10"
    },
    "broadcom-meta": {
      label: "Broadcom and Meta partnership",
      url: "https://investors.broadcom.com/node/64236/pdf"
    },
    "tsmc-q1-2026": {
      label: "TSMC Q1 2026 quarterly results",
      url: "https://investor.tsmc.com/english/quarterly-results"
    },
    "tsmc-transcript": {
      label: "TSMC Q1 2026 transcript",
      url: "https://investor.tsmc.com/english/encrypt/files/encrypt_file/reports/2026-04/3cef85204275f94fd111485cfdf4adb3c0263c45/TSMC%201Q26%20Transcript.pdf"
    },
    "skhynix-hbm4": {
      label: "SK hynix HBM4 development",
      url: "https://news.skhynix.com/sk-hynix_sk-hynix-completes-worlds-first-hbm4-development-and-readies-mass-production_01/"
    },
    "skhynix-q1-2026": {
      label: "SK hynix Q1 2026 results",
      url: "https://news.skhynix.com/q1-2026-business-results/"
    },
    "ceg-tmi-pjm": {
      label: "Reuters via Investing.com - Three Mile Island PJM delay",
      url: "https://www.investing.com/news/stock-market-news/constellation-exec-says-grid-operator-told-company-three-mile-island-cant-connect-until-2031-4583367"
    },
    "pjm-interconnection-process": {
      label: "PJM interconnection request process",
      url: "https://www.pjm.com/planning/service-requests/application-and-forms"
    },
    "vertiv-trends": {
      label: "Vertiv 2026 AI data-center trends",
      url: "https://www.vertiv.com/en-us/about/news-and-insights/corporate-news/vertiv-expects-powering-up-for-ai-digital-twins-and-adaptive-liquid-cooling-to-shape-data-center-design-and-operations/"
    },
    "vertiv-generate": {
      label: "Vertiv and Generate Capital BYOP&C",
      url: "https://investors.vertiv.com/news/news-details/2026/Vertiv-and-Generate-Capital-Collaborate-to-Accelerate-Data-Center-Capacity-with-Complete-Power-and-Cooling-Infrastructure/"
    },
    "msci-q1-2026": {
      label: "MSCI Q1 2026 results",
      url: "https://ir.msci.com/news-releases/news-release-details/msci-reports-financial-results-first-quarter-2026"
    },
    "moodys-research-assistant": {
      label: "Moody's Research Assistant",
      url: "https://www.moodys.com/web/en/us/research-assistant.html"
    },
    "moodys-genai": {
      label: "Moody's AI and GenAI capabilities",
      url: "https://www.moodys.com/web/en/us/capabilities/gen-ai.html"
    },
    "kensho-home": {
      label: "Kensho - S&P Global AI engine",
      url: "https://kensho.com/"
    },
    "kensho-mcp": {
      label: "Kensho LLM-ready API and MCP server",
      url: "https://kensho.com/news/kensho-llm-ready-api-expands-mcp-server-access-dataset-support-integrations"
    },
    "spgi-ai": {
      label: "S&P Global AI insights and benchmarks",
      url: "https://www.spglobal.com/en/research-insights/market-insights/artificial-intelligence"
    },
    "veeva-ai-agents": {
      label: "Veeva AI Agents roadmap",
      url: "https://www.veeva.com/eu/resources/veeva-ai-agents-to-be-released-across-all-veeva-applications/"
    },
    "teradyne-q1-2026": {
      label: "Teradyne Q1 2026 results",
      url: "https://investors.teradyne.com/news-events/press-releases/detail/440/teradyne-reports-first-quarter-2026-results"
    },
    "teradyne-flex": {
      label: "Flex and Teradyne Robotics partnership",
      url: "https://www.universal-robots.com/news-and-media/news-center/flex-teradyne-robotics-expand-partnership-scale-intelligent-automation-across-global-manufacturing/"
    }
  }
};
