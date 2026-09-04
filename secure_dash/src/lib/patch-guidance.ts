/**
 * Playbook-backed remediation copy for the task Patches tab.
 * Example snippets are defensive (bind, auth, headers) — not apply/exploit steps.
 */
import type { Patch } from "@/lib/security";
import { formatEvidence } from "@/lib/task-attack-chain";

export type AssistStack = "nginx" | "express" | "docker-compose" | "linux" | "generic";

export type PatchFinding = {
  id: string;
  title: string;
  severity: string;
  source_tool?: string | null;
  evidence?: unknown;
  remediation?: string | null;
};

export type ExampleFix = {
  filename: string;
  language: string;
  code: string;
  summary: string;
};

export type PatchGuidance = {
  playbook: string;
  summary: string;
  why: string;
  recommendations: string[];
  example: ExampleFix;
  assistPrompt: string;
};

export const ASSIST_STACKS: { id: AssistStack; label: string }[] = [
  { id: "nginx", label: "nginx" },
  { id: "express", label: "Express / Node" },
  { id: "docker-compose", label: "Docker Compose" },
  { id: "linux", label: "Linux host" },
  { id: "generic", label: "Generic" },
];

const PLAYBOOKS: Record<string, Omit<PatchGuidance, "playbook" | "assistPrompt">> = {
  "network-hardening": {
    summary: "Limit which interfaces and ports the service listens on so unused attack surface is not reachable.",
    why: "Open ports discovered during recon are often default binds (0.0.0.0) or leftover debug listeners.",
    recommendations: [
      "Bind the app to 127.0.0.1 (or an internal interface) unless it must be public.",
      "Close unused listeners in the process manager, container publish list, and host firewall.",
      "Keep only the ports the product actually serves; drop admin/debug ports from the compose `ports:` map.",
      "If a port must stay open, put it behind auth and restrict source networks.",
    ],
    example: {
      filename: "docker-compose.yml",
      language: "yaml",
      summary: "Stop publishing unused container ports; keep the app on loopback if this is a lab-only service.",
      code: `services:
  app:
    # Do not publish admin/debug ports. Bind only what clients need.
    ports:
      - "127.0.0.1:3000:3000"
    # extra unused publishes (ftp, metrics, node inspector) stay internal
    expose:
      - "3000"`,
    },
  },
  "api-hardening": {
    summary: "Put authentication and rate limits on REST and /api surfaces that recon listed as public.",
    why: "Crawlers and HTTP probes treat unauthenticated JSON routes as high-value follow-up targets.",
    recommendations: [
      "Require a session or API token on every mutating route and on sensitive reads.",
      "Add per-IP and per-user rate limits on /rest, /api, and search endpoints.",
      "Return 401/404 for undocumented routes instead of listing them in public OpenAPI if they are internal.",
      "Disable directory indexes and verbose error bodies on API 500s.",
    ],
    example: {
      filename: "src/middleware/apiGuard.ts",
      language: "typescript",
      summary: "Auth gate plus a simple rate limiter for Express REST mounts.",
      code: `import rateLimit from "express-rate-limit";
import type { RequestHandler } from "express";

export const apiLimiter = rateLimit({
  windowMs: 60_000,
  limit: 60,
  standardHeaders: true,
  legacyHeaders: false,
});

export const requireSession: RequestHandler = (req, res, next) => {
  if (!req.session?.userId) {
    res.status(401).json({ error: "authentication required" });
    return;
  }
  next();
};

// app.use("/rest", apiLimiter, requireSession, restRouter);
// app.use("/api", apiLimiter, requireSession, apiRouter);`,
    },
  },
  "content-discovery-hardening": {
    summary: "Stop serving paths that wordlists found (ftp, backups, admin panels) unless they are meant to be public.",
    why: "Discovered 200s on /ftp and similar paths usually mean a leftover share or unauthenticated file tree.",
    recommendations: [
      "Remove or relocate public file trees that are not part of the product.",
      "Require authentication (or VPN) before serving those paths.",
      "Return 404 for tooling paths instead of 200/403 if they should not exist.",
      "Add a deny rule at the reverse proxy so a missed app route cannot republish them.",
    ],
    example: {
      filename: "nginx/hardening.conf",
      language: "nginx",
      summary: "Deny commonly discovered leftover paths at the reverse proxy.",
      code: `location ^~ /ftp {
    return 404;
}
location ^~ /backup {
    return 404;
}
location ~* \\.(bak|old|sql|zip)$ {
    deny all;
}`,
    },
  },
  "exposure-hardening": {
    summary: "Hide version banners, debug pages, and missing security headers that scanners flag as exposure.",
    why: "Info/low nuclei matches (missing headers, exposed panels) leak stack details and weaken browser isolation.",
    recommendations: [
      "Send Content-Security-Policy, X-Content-Type-Options, Referrer-Policy, and a tight frame policy.",
      "Turn off server/version tokens and verbose error pages in production.",
      "Disable leftover admin/debug panels or put them on a private network.",
      "HSTS only when TLS is correctly terminated for the real hostname.",
    ],
    example: {
      filename: "nginx/security-headers.conf",
      language: "nginx",
      summary: "Baseline response headers and hidden version tokens.",
      code: `server_tokens off;

add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header X-Frame-Options "DENY" always;
add_header Content-Security-Policy "default-src 'self'" always;`,
    },
  },
  "identity-hardening": {
    summary: "Rotate default or staging credentials and require unique secrets per environment.",
    why: "Weak or documented demo logins are a common initial-access finding after recon.",
    recommendations: [
      "Rotate every default/staging password and API key that was accepted.",
      "Disable demo users in non-lab environments.",
      "Store secrets in the environment or a secret manager, not in source or compose files.",
      "Add lockout or MFA on administrative logins.",
    ],
    example: {
      filename: ".env",
      language: "bash",
      summary: "Replace documented defaults; inject secrets at runtime.",
      code: `# Do not ship default passwords. Rotate and inject at deploy time.
APP_ADMIN_EMAIL=ops@example.internal
APP_ADMIN_PASSWORD=  # set from secret store, never commit
SESSION_SECRET=      # openssl rand -hex 32`,
    },
  },
  "input-validation": {
    summary: "Parameterize queries and validate export/search inputs so injection cannot reach a shell or database.",
    why: "Command or query injection on export endpoints is a typical follow-on from an unauthenticated API surface.",
    recommendations: [
      "Use parameterized queries or an ORM; never concatenate user input into shell or SQL.",
      "Allow-list export formats and field names.",
      "Reject unexpected characters early and log the rejection.",
      "Add a WAF/proxy rule as defense in depth, not as the only control.",
    ],
    example: {
      filename: "src/export.ts",
      language: "typescript",
      summary: "Allow-list the export type and keep user input out of the shell.",
      code: `const FORMATS = new Set(["csv", "json"]);

export function exportQuery(format: string, userId: string) {
  if (!FORMATS.has(format)) {
    throw new Error("unsupported format");
  }
  // parameterized — do not pass format/userId to child_process
  return { text: "select * from exports where user_id = $1", values: [userId] };
}`,
    },
  },
  "persistence-cleanup": {
    summary: "Remove unauthorized scheduled jobs and lock down directories that accept implants.",
    why: "Cron or startup hooks written during a test persist after the run unless cleaned up.",
    recommendations: [
      "Delete unauthorized files under /etc/cron.d, systemd, and user crontabs.",
      "Make cron directories root-owned and not world-writable.",
      "Audit leftover reverse-shell or updater scripts.",
      "Record the cleanup in the task notes so the next run can verify they stay gone.",
    ],
    example: {
      filename: "hardening.sh",
      language: "bash",
      summary: "Tighten cron directory permissions after removing unauthorized jobs.",
      code: `chown root:root /etc/cron.d
chmod 700 /etc/cron.d
# review remaining jobs
ls -la /etc/cron.d`,
    },
  },
  "upgrade-package": {
    summary: "Upgrade or patch the vulnerable package and confirm the service still starts.",
    why: "Blue scans often map a CVE to a specific package version.",
    recommendations: [
      "Identify the installed package and the fixed version from the advisory.",
      "Upgrade in a matching environment before production.",
      "Restart the service and re-run the scanner to confirm the finding is gone.",
      "Pin the new version so a later rebuild cannot roll back.",
    ],
    example: {
      filename: "package.json",
      language: "json",
      summary: "Pin the patched dependency once the advisory version is known.",
      code: `{
  "overrides": {
    "vulnerable-lib": ">=1.4.2"
  }
}`,
    },
  },
  "general-hardening": {
    summary: "Review the discovery finding, confirm it is in scope, and apply the least-privilege fix.",
    why: "Generic recon hits still need an owner, a control, and a way to verify they are closed.",
    recommendations: [
      "Confirm the evidence still reproduces against the intended target.",
      "Decide whether to remove the surface, authenticate it, or document it as accepted risk.",
      "Apply the matching playbook (network, API, content, or headers) rather than a one-off change.",
      "Re-run the same recon tool after the change to verify the finding is gone.",
    ],
    example: {
      filename: "NOTES.md",
      language: "markdown",
      summary: "Track the finding through a small, verifiable change.",
      code: `## Finding
- Evidence: (paste scanner line)
- Owner:
- Fix: remove | authenticate | restrict network
- Verify: rerun the same tool; finding absent`,
    },
  },
};

export function normalizePlaybook(playbook: string | null | undefined): string {
  const key = (playbook || "general-hardening").trim().toLowerCase();
  return PLAYBOOKS[key] ? key : "general-hardening";
}

export function defaultAssistStack(playbook: string): AssistStack {
  switch (normalizePlaybook(playbook)) {
    case "network-hardening":
    case "persistence-cleanup":
    case "upgrade-package":
      return "linux";
    case "api-hardening":
    case "identity-hardening":
    case "input-validation":
      return "express";
    case "content-discovery-hardening":
    case "exposure-hardening":
      return "nginx";
    default:
      return "generic";
  }
}

export function findingForPatch(patch: Patch, findings: PatchFinding[] | undefined): PatchFinding | undefined {
  if (!findings?.length) return undefined;
  return findings.find((f) => f.id === patch.finding_id);
}

export function guidanceForPatch(patch: Patch, finding?: PatchFinding | null, target?: string): PatchGuidance {
  const playbook = normalizePlaybook(patch.playbook);
  const base = PLAYBOOKS[playbook] ?? PLAYBOOKS["general-hardening"]!;
  const host = target?.trim() || "the target";
  const evidence = formatEvidence(finding?.evidence) || formatEvidence(patch.evidence);
  const findingRemediation = finding?.remediation?.trim();
  const recommendations = findingRemediation
    ? [findingRemediation, ...base.recommendations.filter((r) => r !== findingRemediation)]
    : base.recommendations;

  const assistPrompt = [
    `Propose a defensive fix for this authorized lab finding on ${host}.`,
    `Patch: ${patch.title}`,
    `Playbook: ${playbook}`,
    finding ? `Finding: ${finding.title} (${finding.severity})` : null,
    evidence ? `Evidence:\n${evidence.slice(0, 500)}` : null,
    "Return hardened config or application code only. Do not include exploit steps.",
  ]
    .filter(Boolean)
    .join("\n");

  return {
    playbook,
    summary: base.summary,
    why: base.why,
    recommendations,
    example: base.example,
    assistPrompt,
  };
}

export function tailorFix(
  patch: Patch,
  stack: AssistStack,
  notes: string,
  finding?: PatchFinding | null,
  target?: string,
): ExampleFix {
  const playbook = normalizePlaybook(patch.playbook);
  const host = target?.trim() || "127.0.0.1";
  const extra = notes.trim();
  const noteBlock = extra ? `\n# Operator notes: ${extra.replace(/\n/g, " ")}\n` : "";

  if (stack === "nginx" && (playbook === "network-hardening" || playbook === "content-discovery-hardening")) {
    return {
      filename: "nginx/site.conf",
      language: "nginx",
      summary: "Bind locally and hide leftover paths at the proxy.",
      code: `server {
    listen 127.0.0.1:80;
    server_name ${host.replace(/^https?:\/\//, "").split("/")[0] || "localhost"};
${noteBlock}
    location ^~ /ftp { return 404; }
    location ^~ /api-docs { auth_basic "restricted"; auth_basic_user_file /etc/nginx/.htpasswd; }

    location / {
        proxy_pass http://127.0.0.1:3000;
    }
}`,
    };
  }

  if (stack === "express" && (playbook === "api-hardening" || playbook === "identity-hardening")) {
    return {
      filename: "src/app.ts",
      language: "typescript",
      summary: "Listen on loopback and require auth on /rest and /api.",
      code: `import express from "express";
import rateLimit from "express-rate-limit";
${noteBlock}
const app = express();
const limiter = rateLimit({ windowMs: 60_000, limit: 60 });

app.set("trust proxy", 1);
app.use("/rest", limiter, requireSession);
app.use("/api", limiter, requireSession);

app.listen(3000, "127.0.0.1");`,
    };
  }

  if (stack === "docker-compose" && playbook === "network-hardening") {
    return {
      filename: "docker-compose.yml",
      language: "yaml",
      summary: "Publish only the needed port on loopback.",
      code: `services:
  app:
    ports:
      - "127.0.0.1:3000:3000"${extra ? `\n    # ${extra}` : ""}`,
    };
  }

  if (stack === "linux" && playbook === "network-hardening") {
    return {
      filename: "ufw-rules.sh",
      language: "bash",
      summary: "Default-deny inbound, then allow only the app port from trusted nets.",
      code: `ufw default deny incoming
ufw default allow outgoing
ufw allow from 127.0.0.1 to any port 3000
# ufw allow from 10.0.0.0/8 to any port 3000
ufw enable${extra ? `\n# ${extra}` : ""}`,
    };
  }

  const fallback = guidanceForPatch(patch, finding, target).example;
  if (!extra) return fallback;
  return {
    ...fallback,
    summary: `${fallback.summary} Tailored with your notes.`,
    code: `${fallback.code}\n\n# Operator notes\n# ${extra.replace(/\n/g, "\n# ")}`,
  };
}
