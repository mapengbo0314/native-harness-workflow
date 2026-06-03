import { Octokit } from "@octokit/rest";
import dotenv from "dotenv";
import type { Mailmap } from "./config";
import { resolveAuthor } from "./config";
dotenv.config({ path: require("path").join(__dirname, "../../../.env") });

let octokit: Octokit;

export function getOctokit(): Octokit {
  if (!octokit) {
    if (!process.env.GITHUB_TOKEN)
      throw new Error("GITHUB_TOKEN not set in .env");
    octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
  }
  return octokit;
}

export interface CommitSummary {
  sha: string;
  date: string;
  author: string;
  message: string;
  additions: number;
  deletions: number;
}

export interface CommitFile {
  sha: string;
  filename: string;
  additions: number;
  deletions: number;
}

export interface PrSummary {
  number: number;
  title: string;
  merged_at: string | null;
  additions: number;
  deletions: number;
  changed_files: number;
  cycle_time_hours: number | null;
}

/** Fetch commits list (no per-file stats) for a date window. */
export async function fetchCommitList(
  org: string,
  repo: string,
  since: string,
): Promise<CommitSummary[]> {
  const gh = getOctokit();
  const commits: CommitSummary[] = [];

  for await (const response of gh.paginate.iterator(gh.repos.listCommits, {
    owner: org,
    repo,
    since,
    per_page: 100,
  })) {
    for (const c of response.data) {
      commits.push({
        sha: c.sha,
        date: c.commit.author?.date ?? "",
        author: c.commit.author?.name ?? "unknown",
        message: c.commit.message,
        additions: 0,
        deletions: 0,
      });
    }
  }
  return commits;
}

/** Fetch per-file stats for a single commit. */
export async function fetchCommitDetail(
  org: string,
  repo: string,
  sha: string,
): Promise<{ additions: number; deletions: number; files: CommitFile[] }> {
  const gh = getOctokit();
  const { data } = await gh.repos.getCommit({ owner: org, repo, ref: sha });
  return {
    additions: data.stats?.additions ?? 0,
    deletions: data.stats?.deletions ?? 0,
    files: (data.files ?? []).map((f) => ({
      sha,
      filename: f.filename ?? "",
      additions: f.additions,
      deletions: f.deletions,
    })),
  };
}

/** Fetch recent merged PRs (last 90d). */
export async function fetchRecentPrs(
  org: string,
  repo: string,
): Promise<PrSummary[]> {
  const gh = getOctokit();
  const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString();
  const prs: PrSummary[] = [];

  for await (const response of gh.paginate.iterator(gh.pulls.list, {
    owner: org,
    repo,
    state: "closed",
    sort: "updated",
    direction: "desc",
    per_page: 100,
  })) {
    for (const pr of response.data) {
      if (!pr.merged_at) continue;
      if (pr.merged_at < cutoff) break;
      const created = new Date(pr.created_at).getTime();
      const merged = new Date(pr.merged_at).getTime();
      prs.push({
        number: pr.number,
        title: pr.title,
        merged_at: pr.merged_at,
        additions: 0,
        deletions: 0,
        changed_files:
          (pr as unknown as { changed_files?: number }).changed_files ?? 0,
        cycle_time_hours: Math.round((merged - created) / 36e5),
      });
    }
  }
  return prs;
}

/** Fetch open PRs count via pulls list (no deprecated search endpoint). */
export async function fetchOpenPrCount(
  org: string,
  repo: string,
): Promise<number> {
  const gh = getOctokit();
  let count = 0;
  for await (const response of gh.paginate.iterator(gh.pulls.list, {
    owner: org,
    repo,
    state: "open",
    per_page: 100,
  })) {
    count += response.data.length;
    if (response.data.length < 100) break;
  }
  return count;
}

export interface RecentActivity {
  weekly_counts: number[];
  last_commit_date: string | null;
  last_commit_message: string | null;
  last_commit_author: string | null;
  top_authors: { name: string; count: number }[];
  ai_commit_count: number;
  total_commit_count: number;
  dirty_authors: { raw_name: string; email: string; count: number }[];
}

/** Fetch recent commits (N weeks) and extract all overview-card data in one pass. */
export async function fetchRecentActivity(
  org: string,
  repo: string,
  aiPatterns: RegExp[],
  mailmap: Mailmap,
  weeks = 12,
): Promise<RecentActivity> {
  const gh = getOctokit();
  const since = new Date(
    Date.now() - weeks * 7 * 24 * 60 * 60 * 1000,
  ).toISOString();

  const weekKey = (dateStr: string): number => {
    const d = new Date(dateStr);
    const day = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() - (day - 1));
    d.setUTCHours(0, 0, 0, 0);
    return d.getTime();
  };

  const now = Date.now();
  const buckets = new Map<number, number>();
  for (let i = 0; i < weeks; i++) {
    buckets.set(
      weekKey(new Date(now - i * 7 * 24 * 60 * 60 * 1000).toISOString()),
      0,
    );
  }

  const authorCounts = new Map<string, number>();
  const dirtyMap = new Map<
    string,
    { raw_name: string; email: string; count: number }
  >();
  let lastDate: string | null = null;
  let lastMessage: string | null = null;
  let lastAuthor: string | null = null;
  let aiCount = 0;
  let total = 0;

  try {
    for await (const response of gh.paginate.iterator(gh.repos.listCommits, {
      owner: org,
      repo,
      since,
      per_page: 100,
    })) {
      for (const c of response.data) {
        const date = c.commit.author?.date ?? c.commit.committer?.date ?? "";
        const rawName = c.commit.author?.name ?? "unknown";
        const email = c.commit.author?.email ?? "";
        const message = c.commit.message ?? "";
        if (!date) continue;

        const canonical = resolveAuthor(rawName, email, mailmap);
        const displayName = canonical ?? rawName;

        total++;
        if (lastDate === null) {
          lastDate = date;
          lastMessage = message.split("\n")[0];
          lastAuthor = displayName;
        }
        authorCounts.set(displayName, (authorCounts.get(displayName) ?? 0) + 1);
        if (aiPatterns.some((p) => p.test(message))) aiCount++;

        if (!canonical) {
          const key = `${rawName}|${email}`;
          const existing = dirtyMap.get(key);
          dirtyMap.set(key, {
            raw_name: rawName,
            email,
            count: (existing?.count ?? 0) + 1,
          });
        }

        const wk = weekKey(date);
        if (buckets.has(wk)) buckets.set(wk, (buckets.get(wk) ?? 0) + 1);
      }
    }
  } catch {
    // return what we have
  }

  const top_authors = [...authorCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([name, count]) => ({ name, count }));

  const weekly_counts = [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, count]) => count);

  const dirty_authors = [...dirtyMap.values()].sort(
    (a, b) => b.count - a.count,
  );

  return {
    weekly_counts,
    last_commit_date: lastDate,
    last_commit_message: lastMessage,
    last_commit_author: lastAuthor,
    top_authors,
    ai_commit_count: aiCount,
    total_commit_count: total,
    dirty_authors,
  };
}

/** Check which agent config files exist in the repo root. */
export async function fetchAgentFiles(
  org: string,
  repo: string,
): Promise<{ claude_md: boolean; agents_md: boolean }> {
  const gh = getOctokit();
  const check = async (path: string) => {
    try {
      await gh.repos.getContent({ owner: org, repo, path });
      return true;
    } catch {
      return false;
    }
  };
  const [claude_md, agents_md] = await Promise.all([
    check("CLAUDE.md"),
    check("AGENTS.md"),
  ]);
  return { claude_md, agents_md };
}

/** Throttle: simple sleep between API calls in deep scan. */
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
