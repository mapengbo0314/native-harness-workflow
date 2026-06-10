import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { RepoSummary } from "../types";
import { BarChart, Bar, ResponsiveContainer, Tooltip } from "recharts";
import { useTheme, ThemeSwitcher } from "../ThemeContext";

export function Overview() {
  const [repos, setRepos] = useState<RepoSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { theme } = useTheme();

  useEffect(() => {
    api
      .repos()
      .then((data) =>
        setRepos(
          [...data].sort((a, b) => b.commits_last_30d - a.commits_last_30d),
        ),
      )
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const page: React.CSSProperties = {
    minHeight: "100vh",
    background: theme.pageBg,
    padding: "32px 40px",
    fontFamily: "system-ui, sans-serif",
  };

  if (loading)
    return (
      <div style={page}>
        <div style={{ color: theme.textMuted }}>Loading…</div>
      </div>
    );
  if (error)
    return (
      <div style={page}>
        <div style={{ color: theme.critical }}>{error}</div>
      </div>
    );

  return (
    <div style={page}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 20,
        }}
      >
        <h1
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: theme.textPrimary,
            margin: 0,
          }}
        >
          Repository overview
        </h1>
        <ThemeSwitcher />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {repos.map((r) => (
          <RepoRow
            key={`${r.org}/${r.repo}`}
            r={r}
            onClick={() => navigate(`/${r.org}/${r.repo}`)}
          />
        ))}
      </div>
    </div>
  );
}

function RepoRow({ r, onClick }: { r: RepoSummary; onClick: () => void }) {
  const { theme } = useTheme();
  const sparkData = (r.commits_per_week || [])
    .slice(-8)
    .map((count, i) => ({ i, count }));
  const aiPct = r.ai_pct !== null ? Math.round(r.ai_pct * 100) : null;
  const churnStatus = r.commit_size
    ? r.commit_size.p50 > 150
      ? "critical"
      : r.commit_size.p50 > 50
        ? "warn"
        : "healthy"
    : null;

  const rowCard: React.CSSProperties = {
    background: theme.cardBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: "14px 20px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: 28,
    overflow: "hidden",
    transition: "border-color 0.15s",
  };

  return (
    <div onClick={onClick} style={rowCard}>
      <div style={{ minWidth: 200, maxWidth: 240 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{ fontWeight: 600, color: theme.textPrimary, fontSize: 14 }}
          >
            {r.display_name}
          </div>
          <AgentBadge files={r.agent_files} />
          <HarnessBadge harness={r.harness} />
        </div>
        <div style={{ fontSize: 11, color: theme.textFaint }}>
          {r.org}/{r.repo}
        </div>
        {r.last_commit_message && (
          <div
            style={{
              fontSize: 11,
              color: theme.textDim,
              marginTop: 4,
              lineHeight: 1.4,
            }}
            title={r.last_commit_message}
          >
            "{truncate(r.last_commit_message, 48)}"
          </div>
        )}
        {r.last_commit_date && (
          <div style={{ fontSize: 10, color: theme.textFaint, marginTop: 2 }}>
            {r.last_commit_author && (
              <span style={{ color: theme.textDim }}>
                {r.last_commit_author} ·{" "}
              </span>
            )}
            {timeAgo(r.last_commit_date)}
          </div>
        )}
      </div>

      <div style={{ width: 120, flexShrink: 0 }}>
        <ResponsiveContainer width="100%" height={36}>
          <BarChart
            data={sparkData}
            barSize={10}
            margin={{ top: 2, bottom: 2, left: 0, right: 0 }}
          >
            <Bar dataKey="count" fill={theme.accent} radius={[2, 2, 0, 0]} />
            <Tooltip
              contentStyle={{
                background: theme.pageBg,
                border: `1px solid ${theme.borderStrong}`,
                fontSize: 11,
                padding: "2px 8px",
              }}
              formatter={(v: number) => [v, "commits"]}
              labelFormatter={() => ""}
            />
          </BarChart>
        </ResponsiveContainer>
        <div
          style={{ fontSize: 10, color: theme.textFaint, textAlign: "center" }}
        >
          8 weeks
        </div>
      </div>

      <div style={{ minWidth: 140 }}>
        {(() => {
          const total =
            (r.top_authors || []).reduce((s, a) => s + a.count, 0) || 1;
          return (r.top_authors || []).slice(0, 3).map((a) => {
            const pct = Math.min(100, Math.round((a.count / total) * 100));
            const firstName = a.name.split(/[\s@]/)[0];
            return (
              <div
                key={a.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 3,
                }}
              >
                <div
                  style={{
                    width: 60,
                    height: 3,
                    background: theme.border,
                    borderRadius: 2,
                    flexShrink: 0,
                  }}
                >
                  <div
                    style={{
                      width: `${pct}%`,
                      height: 3,
                      background: theme.accent,
                      borderRadius: 2,
                    }}
                  />
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: theme.textMuted,
                    whiteSpace: "nowrap",
                    width: 70,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {firstName}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: theme.textFaint,
                    width: 20,
                    textAlign: "right",
                  }}
                >
                  {a.count}
                </div>
              </div>
            );
          });
        })()}
      </div>

      <div
        style={{
          display: "flex",
          gap: 16,
          alignItems: "center",
          flexShrink: 0,
        }}
      >
        <Stat
          value={r.commits_last_30d}
          label="commits"
          color={theme.textSecondary}
          theme={theme}
        />
        <Stat
          value={r.open_prs}
          label="open PRs"
          color={r.open_prs > 5 ? theme.warn : theme.textSecondary}
          theme={theme}
        />
        {aiPct !== null && (
          <Stat
            value={`${aiPct}%`}
            label="AI"
            color={theme.accentSecondary}
            theme={theme}
          />
        )}
        {r.commit_size && (
          <Stat
            value={`${r.commit_size.p50}L`}
            label="p50"
            color={
              churnStatus === "critical"
                ? theme.critical
                : churnStatus === "warn"
                  ? theme.warn
                  : theme.healthy
            }
            theme={theme}
          />
        )}
      </div>

      {(r.dirty_authors || []).length > 0 && (
        <div
          title={`Unrecognized git identities:\n${(r.dirty_authors || []).map((d) => `  "${d.raw_name}" <${d.email}> (${d.count})`).join("\n")}\n\nFix: git config --global user.name / user.email on each machine,\nthen add to mailmap.yaml`}
          style={{
            fontSize: 11,
            color: theme.warn,
            whiteSpace: "nowrap",
            cursor: "help",
          }}
        >
          ⚠ {(r.dirty_authors || []).length} unknown{" "}
          {(r.dirty_authors || []).length === 1 ? "identity" : "identities"}
        </div>
      )}

      <div style={{ minWidth: 90, textAlign: "right" }}>
        {r.scan_status === "scanning" && r.scan_progress ? (
          <div>
            <div style={{ fontSize: 10, color: theme.accent }}>scanning…</div>
            <div
              style={{
                background: theme.border,
                borderRadius: 2,
                height: 3,
                marginTop: 3,
              }}
            >
              <div
                style={{
                  background: theme.accent,
                  height: 3,
                  borderRadius: 2,
                  width: `${r.scan_progress.total > 0 ? Math.round((r.scan_progress.done / r.scan_progress.total) * 100) : 0}%`,
                }}
              />
            </div>
          </div>
        ) : r.has_deep_scan ? (
          <div style={{ fontSize: 10, color: theme.healthy }}>● scanned</div>
        ) : (
          <div style={{ fontSize: 10, color: theme.borderStrong }}>no scan</div>
        )}
        {r.last_scanned_at && (
          <div style={{ fontSize: 9, color: theme.borderStrong, marginTop: 2 }}>
            {timeAgo(r.last_scanned_at)}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  value,
  label,
  color,
  theme,
}: {
  value: string | number;
  label: string;
  color: string;
  theme: import("../theme").Theme;
}) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 16, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 10, color: theme.textFaint }}>{label}</div>
    </div>
  );
}

function HarnessBadge({
  harness,
}: {
  harness: import("../types").RepoSummary["harness"];
}) {
  if (!harness) return null;
  if (!harness.installed)
    return (
      <span title="Harness not installed" style={pill("#2d1a1a", "#ef4444")}>
        no harness
      </span>
    );
  const { installed_version, current_version, up_to_date, built_at } = harness;
  const label = installed_version ? `v${installed_version}` : "harness";
  const tooltip = [
    `Installed: ${installed_version ?? "unknown"}`,
    current_version ? `Current: ${current_version}` : null,
    built_at ? `Built: ${new Date(built_at).toLocaleDateString()}` : null,
    up_to_date === false ? "⚠ Reinstall to update" : null,
  ]
    .filter(Boolean)
    .join("\n");

  if (up_to_date === false)
    return (
      <span title={tooltip} style={pill("#2d2200", "#f59e0b")}>
        {label} → v{current_version}
      </span>
    );
  return (
    <span title={tooltip} style={pill("#1a2a1a", "#4ade80")}>
      {label} ✓
    </span>
  );
}

function AgentBadge({
  files,
}: {
  files: { claude_md: boolean; agents_md: boolean } | undefined;
}) {
  if (!files) return null;
  const { claude_md, agents_md } = files;
  if (!claude_md && !agents_md)
    return (
      <span
        title="No CLAUDE.md or AGENTS.md found"
        style={pill("#374151", "#6b7280")}
      >
        no agent cfg
      </span>
    );
  const labels = [claude_md && "CLAUDE.md", agents_md && "AGENTS.md"]
    .filter(Boolean)
    .join(" + ");
  return (
    <span title={labels} style={pill("#1a2e1a", "#22c55e")}>
      {labels}
    </span>
  );
}

function pill(bg: string, color: string): React.CSSProperties {
  return {
    background: bg,
    color,
    fontSize: 9,
    fontWeight: 600,
    padding: "1px 5px",
    borderRadius: 3,
    letterSpacing: 0.3,
    whiteSpace: "nowrap" as const,
  };
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const h = Math.floor(diff / 36e5);
  if (h < 1) return "just now";
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return `${Math.floor(d / 30)}mo ago`;
}
