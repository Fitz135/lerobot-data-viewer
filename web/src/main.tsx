import React from "react";
import ReactDOM from "react-dom/client";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import "./styles.css";
import { apiGet, apiPost, getApiBase, setApiBase, videoUrl } from "./api";
import type {
  Dataset,
  Episode,
  EpisodeDetail,
  HealthCheck,
  IndexRuns,
  Paged,
  Task,
  TaskEpisodeSummary,
  TaskSummary,
  Timeseries,
  VideoRow,
} from "./types";

type Route =
  | { name: "global" }
  | { name: "dataset"; datasetId: string }
  | { name: "task"; datasetId: string; taskId: string }
  | { name: "episode"; datasetId: string; taskId: string; episodeIndex: number };

function parseRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const parts = hash.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "datasets" && parts[1] && parts[2] === "tasks" && parts[3] && parts[4] === "episodes" && parts[5]) {
    return { name: "episode", datasetId: parts[1], taskId: parts[3], episodeIndex: Number(parts[5]) };
  }
  if (parts[0] === "datasets" && parts[1] && parts[2] === "tasks" && parts[3]) {
    return { name: "task", datasetId: parts[1], taskId: parts[3] };
  }
  if (parts[0] === "datasets" && parts[1]) {
    return { name: "dataset", datasetId: parts[1] };
  }
  return { name: "global" };
}

function href(parts: string[]): string {
  return `#/${parts.map(encodeURIComponent).join("/")}`;
}

function useRoute(): Route {
  const [route, setRoute] = React.useState<Route>(() => parseRoute());
  React.useEffect(() => {
    const onHash = () => setRoute(parseRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return route;
}

function useApi<T>(path: string, deps: React.DependencyList): { data: T | null; loading: boolean; error: string | null; reload: () => void } {
  const [data, setData] = React.useState<T | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [tick, setTick] = React.useState(0);
  React.useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    apiGet<T>(path)
      .then((result) => {
        if (alive) setData(result);
      })
      .catch((err: Error) => {
        if (alive) setError(err.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [...deps, tick]);
  return { data, loading, error, reload: () => setTick((value) => value + 1) };
}

function number(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat().format(value);
}

function seconds(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  if (value < 120) return `${value.toFixed(1)}s`;
  const minutes = value / 60;
  if (minutes < 120) return `${minutes.toFixed(1)}m`;
  return `${(minutes / 60).toFixed(1)}h`;
}

function App() {
  const route = useRoute();
  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="#/">LeRobot Data Viewer</a>
        <ApiBaseControl />
      </header>
      <main>
        {route.name === "global" && <GlobalDashboard />}
        {route.name === "dataset" && <DatasetDetail datasetId={route.datasetId} />}
        {route.name === "task" && <TaskDetail datasetId={route.datasetId} taskId={route.taskId} />}
        {route.name === "episode" && (
          <EpisodeBrowser datasetId={route.datasetId} taskId={route.taskId} episodeIndex={route.episodeIndex} />
        )}
      </main>
    </div>
  );
}

function ApiBaseControl() {
  const [value, setValue] = React.useState(() => getApiBase());
  return (
    <form
      className="apiBase"
      onSubmit={(event) => {
        event.preventDefault();
        setApiBase(value);
        window.location.reload();
      }}
    >
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        aria-label="API base URL"
        placeholder="https://example.com/api"
      />
      <button type="submit">Set API</button>
    </form>
  );
}

function ErrorBox({ message }: { message: string }) {
  return <div className="notice error">{message}</div>;
}

function Loading() {
  return <div className="notice">Loading...</div>;
}

function StatGrid({ stats }: { stats: Array<[string, string]> }) {
  return (
    <div className="statGrid">
      {stats.map(([label, value]) => (
        <div className="stat" key={label}>
          <div className="statValue">{value}</div>
          <div className="statLabel">{label}</div>
        </div>
      ))}
    </div>
  );
}

function GlobalDashboard() {
  const { data, loading, error } = useApi<{ datasets: Dataset[] }>("/datasets", []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  const datasets = data?.datasets ?? [];
  const totals = datasets.reduce(
    (acc, item) => {
      acc.tasks += item.task_count ?? 0;
      acc.episodes += item.episode_count ?? 0;
      acc.frames += item.frame_count ?? 0;
      acc.videos += item.video_count ?? 0;
      acc.errors += item.error_count ?? 0;
      acc.warnings += item.warning_count ?? 0;
      return acc;
    },
    { tasks: 0, episodes: 0, frames: 0, videos: 0, errors: 0, warnings: 0 },
  );
  return (
    <section>
      <div className="sectionHeader">
        <div>
          <h1>Global Dashboard</h1>
          <p>{datasets.length} registered datasets</p>
        </div>
      </div>
      <StatGrid
        stats={[
          ["Datasets", number(datasets.length)],
          ["Tasks", number(totals.tasks)],
          ["Episodes", number(totals.episodes)],
          ["Frames", number(totals.frames)],
          ["Videos", number(totals.videos)],
          ["Errors", number(totals.errors)],
          ["Warnings", number(totals.warnings)],
        ]}
      />
      <table className="dataTable">
        <thead>
          <tr>
            <th>Dataset</th>
            <th>Tasks</th>
            <th>Episodes</th>
            <th>Frames</th>
            <th>Videos</th>
            <th>Issues</th>
            <th>Indexed</th>
            <th>Root</th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((dataset) => (
            <tr key={dataset.id}>
              <td><a href={href(["datasets", dataset.id])}>{dataset.name}</a></td>
              <td>{number(dataset.task_count)}</td>
              <td>{number(dataset.episode_count)}</td>
              <td>{number(dataset.frame_count)}</td>
              <td>{number(dataset.video_count)}</td>
              <td><IssueText error={dataset.error_count} warning={dataset.warning_count} /></td>
              <td>{dataset.last_indexed_at ? dataset.last_indexed_at : "not indexed"}</td>
              <td className={dataset.root_exists ? "muted" : "bad"}>{dataset.root}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function IssueText({ error, warning, info }: { error?: number | null; warning?: number | null; info?: number | null }) {
  return (
    <span className="issueText">
      <span className={error ? "bad" : "muted"}>{number(error ?? 0)} errors</span>
      <span className={warning ? "warn" : "muted"}>{number(warning ?? 0)} warnings</span>
      {info !== undefined && <span className="muted">{number(info ?? 0)} info</span>}
    </span>
  );
}

function DatasetDetail({ datasetId }: { datasetId: string }) {
  const [search, setSearch] = React.useState("");
  const [issue, setIssue] = React.useState("any");
  const [refreshWatch, setRefreshWatch] = React.useState<{ previousRunId: number | null; activeRunId: number | null } | null>(null);
  const detail = useApi<Dataset>(`/datasets/${encodeURIComponent(datasetId)}`, [datasetId]);
  const taskSummary = useApi<TaskSummary>(`/datasets/${encodeURIComponent(datasetId)}/task-summary`, [datasetId]);
  const tasks = useApi<Paged<Task>>(
    `/datasets/${encodeURIComponent(datasetId)}/tasks?search=${encodeURIComponent(search)}&issue=${issue}&page_size=100`,
    [datasetId, search, issue],
  );
  const runs = useApi<IndexRuns>(`/index-runs?dataset_id=${encodeURIComponent(datasetId)}&limit=5`, [datasetId]);
  const latestRun = runs.data?.runs?.[0] ?? null;

  React.useEffect(() => {
    if (!refreshWatch) return;
    const timer = window.setInterval(() => {
      runs.reload();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [refreshWatch]);

  React.useEffect(() => {
    if (!refreshWatch || !latestRun) return;
    const isExistingRunningRun = latestRun.id === refreshWatch.previousRunId && latestRun.status === "running";
    const isNewRun = latestRun.id !== refreshWatch.previousRunId;
    const activeRunId = refreshWatch.activeRunId;

    if (activeRunId === null && (isExistingRunningRun || isNewRun)) {
      setRefreshWatch({ ...refreshWatch, activeRunId: latestRun.id });
      return;
    }

    if (activeRunId !== null && latestRun.id === activeRunId && latestRun.status !== "running") {
      setRefreshWatch(null);
      detail.reload();
      taskSummary.reload();
      tasks.reload();
    }
  }, [refreshWatch, latestRun?.id, latestRun?.status]);

  if (detail.loading) return <Loading />;
  if (detail.error) return <ErrorBox message={detail.error} />;
  const dataset = detail.data;
  if (!dataset) return null;
  const active = dataset.active_generation_id !== null && dataset.active_generation_id !== undefined;
  async function refresh(smoke: boolean) {
    const previousRunId = latestRun?.id ?? null;
    await apiPost(
      `/datasets/${encodeURIComponent(datasetId)}/refresh?smoke=${smoke ? "true" : "false"}${smoke ? "&max_tasks=2&max_episodes_per_task=2" : ""}`,
    );
    setRefreshWatch({ previousRunId, activeRunId: null });
    runs.reload();
  }
  return (
    <section>
      <Breadcrumb items={[["Global", "#/"], [dataset.name, href(["datasets", datasetId])]]} />
      <div className="sectionHeader">
        <div>
          <h1>{dataset.name}</h1>
          <p className={dataset.root_exists ? "muted" : "bad"}>{dataset.root}</p>
        </div>
        <div className="actions">
          <button onClick={() => refresh(true)}>Smoke Refresh</button>
          <button onClick={() => refresh(false)}>Full Refresh</button>
        </div>
      </div>
      {!active && (
        <div className="notice">
          No active index. Run <code>make index-smoke</code> or start a smoke refresh.
        </div>
      )}
      <StatGrid
        stats={[
          ["Tasks", number(dataset.task_count)],
          ["Episodes", number(dataset.episode_count)],
          ["Frames", number(dataset.frame_count)],
          ["Videos", number(dataset.video_count)],
          ["Duration", seconds(dataset.duration_sec)],
          ["Errors", number(dataset.error_count)],
          ["Warnings", number(dataset.warning_count)],
        ]}
      />
      <RefreshPanel runs={runs.data} />
      {active && (
        <>
          <DatasetGlobalInfo
            datasetId={datasetId}
            summary={taskSummary.data}
            loading={taskSummary.loading}
            error={taskSummary.error}
          />
          <EpisodeSearch datasetId={datasetId} tasks={taskSummary.data?.items ?? []} />
          <div className="toolbar">
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search task or description" />
            <select value={issue} onChange={(event) => setIssue(event.target.value)}>
              <option value="any">Issues</option>
              <option value="error">Errors</option>
              <option value="warning">Warnings</option>
            </select>
          </div>
          {tasks.loading && <Loading />}
          {tasks.error && <ErrorBox message={tasks.error} />}
          {tasks.data && <TaskTable datasetId={datasetId} tasks={tasks.data.items} />}
        </>
      )}
    </section>
  );
}

function DatasetGlobalInfo({
  datasetId,
  summary,
  loading,
  error,
}: {
  datasetId: string;
  summary: TaskSummary | null;
  loading: boolean;
  error: string | null;
}) {
  return (
    <div className="globalInfo">
      <div className="subsectionHeader">
        <h2>task</h2>
        {summary && (
          <div className="muted">
            {number(summary.total)} tasks / {number(summary.episode_total)} episodes
          </div>
        )}
      </div>
      {loading && <Loading />}
      {error && <ErrorBox message={error} />}
      {summary && (
        <div className="tableScroll">
          <table className="dataTable compactTable">
            <thead>
              <tr>
                <th>Task</th>
                <th>Episodes</th>
              </tr>
            </thead>
            <tbody>
              {summary.items.map((task) => (
                <tr key={task.task_id}>
                  <td>
                    <a href={href(["datasets", datasetId, "tasks", task.task_id])}>{task.task_id}</a>
                    {task.task_text && <div className="description">{task.task_text}</div>}
                  </td>
                  <td>{number(task.episode_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EpisodeSearch({ datasetId, tasks }: { datasetId: string; tasks: TaskEpisodeSummary[] }) {
  const [taskId, setTaskId] = React.useState("");
  const [episodeId, setEpisodeId] = React.useState("");
  const [result, setResult] = React.useState<Paged<Episode> | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const requestId = React.useRef(0);

  React.useEffect(() => {
    setTaskId((current) => {
      if (!tasks.length) return "";
      return tasks.some((task) => task.task_id === current) ? current : tasks[0].task_id;
    });
  }, [tasks]);

  React.useEffect(() => {
    requestId.current += 1;
    setResult(null);
    setError(null);
  }, [datasetId, taskId, episodeId]);

  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedEpisode = episodeId.trim();
    if (!taskId || !trimmedEpisode) {
      requestId.current += 1;
      setResult(null);
      setError(null);
      return;
    }
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const query = `${taskId}/${trimmedEpisode}`;
      const data = await apiGet<Paged<Episode>>(
        `/datasets/${encodeURIComponent(datasetId)}/episodes/search?q=${encodeURIComponent(query)}&page_size=100`,
      );
      if (currentRequest === requestId.current) {
        setResult(data);
      }
    } catch (err) {
      if (currentRequest === requestId.current) {
        setError((err as Error).message);
      }
    } finally {
      if (currentRequest === requestId.current) {
        setLoading(false);
      }
    }
  }

  return (
    <div className="searchBlock">
      <form className="toolbar" onSubmit={search}>
        <select value={taskId} onChange={(event) => setTaskId(event.target.value)} disabled={!tasks.length}>
          {!tasks.length && <option value="">No tasks</option>}
          {tasks.map((task) => (
            <option value={task.task_id} key={task.task_id}>{task.task_id}</option>
          ))}
        </select>
        <input
          value={episodeId}
          onChange={(event) => setEpisodeId(event.target.value)}
          placeholder="Episode id: 12 or episode_000012"
        />
        <button type="submit">Find Episode</button>
      </form>
      {loading && <Loading />}
      {error && <ErrorBox message={error} />}
      {result && (
        <div>
          <div className="muted searchSummary">{number(result.total)} matching episodes</div>
          <EpisodeTable datasetId={datasetId} episodes={result.items} showTask />
        </div>
      )}
    </div>
  );
}

function RefreshPanel({ runs }: { runs: IndexRuns | null }) {
  const latest = runs?.runs?.[0];
  if (!latest) return null;
  const pct = latest.total_items ? Math.round((latest.processed_items / latest.total_items) * 100) : 0;
  return (
    <div className="runPanel">
      <div>
        <strong>{latest.status}</strong> / {latest.phase}
      </div>
      <div className="progress"><div style={{ width: `${pct}%` }} /></div>
      <div className="muted">{number(latest.processed_items)} / {number(latest.total_items)}</div>
      {latest.error_message && <div className="bad">{latest.error_message}</div>}
    </div>
  );
}

function TaskTable({ datasetId, tasks }: { datasetId: string; tasks: Task[] }) {
  return (
    <table className="dataTable">
      <thead>
        <tr>
          <th>Task</th>
          <th>Episodes</th>
          <th>Frames</th>
          <th>Length p50/p95</th>
          <th>Videos</th>
          <th>Issues</th>
        </tr>
      </thead>
      <tbody>
        {tasks.map((task) => (
          <tr key={task.task_id}>
            <td>
              <a href={href(["datasets", datasetId, "tasks", task.task_id])}>{task.task_id}</a>
              <div className="description">{task.task_text}</div>
            </td>
            <td>{number(task.episode_count)}</td>
            <td>{number(task.frame_count)}</td>
            <td>{number(Math.round(task.p50_length ?? 0))} / {number(Math.round(task.p95_length ?? 0))}</td>
            <td>{number(task.video_count)}</td>
            <td><IssueText error={task.error_count} warning={task.warning_count} info={task.info_count} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TaskDetail({ datasetId, taskId }: { datasetId: string; taskId: string }) {
  const [issue, setIssue] = React.useState("any");
  const [sort, setSort] = React.useState("episode");
  const task = useApi<Task>(`/datasets/${encodeURIComponent(datasetId)}/tasks/${encodeURIComponent(taskId)}`, [datasetId, taskId]);
  const episodes = useApi<Paged<Episode>>(
    `/datasets/${encodeURIComponent(datasetId)}/tasks/${encodeURIComponent(taskId)}/episodes?issue=${issue}&sort=${sort}&page_size=100`,
    [datasetId, taskId, issue, sort],
  );
  if (task.loading) return <Loading />;
  if (task.error) return <ErrorBox message={task.error} />;
  const item = task.data;
  if (!item) return null;
  return (
    <section>
      <Breadcrumb items={[["Global", "#/"], [datasetId, href(["datasets", datasetId])], [taskId, href(["datasets", datasetId, "tasks", taskId])]]} />
      <div className="sectionHeader">
        <div>
          <h1>{taskId}</h1>
          <p>{item.task_text}</p>
        </div>
      </div>
      <StatGrid
        stats={[
          ["Episodes", number(item.episode_count)],
          ["Frames", number(item.frame_count)],
          ["Videos", number(item.video_count)],
          ["p50 length", number(Math.round(item.p50_length ?? 0))],
          ["p95 length", number(Math.round(item.p95_length ?? 0))],
          ["Errors", number(item.error_count)],
          ["Warnings", number(item.warning_count)],
        ]}
      />
      <div className="toolbar">
        <select value={issue} onChange={(event) => setIssue(event.target.value)}>
          <option value="any">Issues</option>
          <option value="error">Errors</option>
          <option value="warning">Warnings</option>
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="episode">Episode</option>
          <option value="length">Length</option>
          <option value="issues">Issues</option>
        </select>
      </div>
      {episodes.loading && <Loading />}
      {episodes.error && <ErrorBox message={episodes.error} />}
      {episodes.data && <EpisodeTable datasetId={datasetId} taskId={taskId} episodes={episodes.data.items} />}
    </section>
  );
}

function EpisodeTable({
  datasetId,
  taskId,
  episodes,
  showTask = false,
}: {
  datasetId: string;
  taskId?: string;
  episodes: Episode[];
  showTask?: boolean;
}) {
  return (
    <table className="dataTable">
      <thead>
        <tr>
          {showTask && <th>Task</th>}
          <th>Episode</th>
          <th>Length</th>
          <th>Duration</th>
          <th>Rows</th>
          <th>Frame Range</th>
          <th>Issues</th>
        </tr>
      </thead>
      <tbody>
        {episodes.map((episode) => (
          <tr key={`${episode.task_id}-${episode.episode_index}`}>
            {showTask && <td><a href={href(["datasets", datasetId, "tasks", episode.task_id])}>{episode.task_id}</a></td>}
            <td><a href={href(["datasets", datasetId, "tasks", taskId ?? episode.task_id, "episodes", String(episode.episode_index)])}>episode_{String(episode.episode_index).padStart(6, "0")}</a></td>
            <td>{number(episode.length)}</td>
            <td>{seconds(episode.duration_sec)}</td>
            <td>{number(episode.row_count)}</td>
            <td>{number(episode.frame_start)} - {number(episode.frame_end)}</td>
            <td><IssueText error={episode.error_count} warning={episode.warning_count} info={episode.info_count} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Breadcrumb({ items }: { items: Array<[string, string]> }) {
  return (
    <nav className="breadcrumb">
      {items.map(([label, link], index) => (
        <React.Fragment key={link}>
          {index > 0 && <span>/</span>}
          <a href={link}>{label}</a>
        </React.Fragment>
      ))}
    </nav>
  );
}

function EpisodeBrowser({ datasetId, taskId, episodeIndex }: { datasetId: string; taskId: string; episodeIndex: number }) {
  const detail = useApi<EpisodeDetail>(
    `/datasets/${encodeURIComponent(datasetId)}/tasks/${encodeURIComponent(taskId)}/episodes/${episodeIndex}`,
    [datasetId, taskId, episodeIndex],
  );
  const timeseries = useApi<Timeseries>(
    `/datasets/${encodeURIComponent(datasetId)}/tasks/${encodeURIComponent(taskId)}/episodes/${episodeIndex}/timeseries?downsample=1000`,
    [datasetId, taskId, episodeIndex],
  );
  const [frame, setFrame] = React.useState(0);
  const [playing, setPlaying] = React.useState(false);
  const videoRefs = React.useRef<Record<string, HTMLVideoElement | null>>({});
  const episode = detail.data?.episode;
  const videos = detail.data?.videos ?? [];

  React.useEffect(() => {
    setFrame(0);
    setPlaying(false);
  }, [datasetId, taskId, episodeIndex]);

  const fps = episode?.fps || 30;
  const maxFrame = Math.max((episode?.length ?? 1) - 1, 0);

  function seekAll(nextFrame: number) {
    const clamped = Math.max(0, Math.min(maxFrame, Math.round(nextFrame)));
    setFrame(clamped);
    const time = clamped / fps;
    Object.values(videoRefs.current).forEach((video) => {
      if (video && Number.isFinite(time)) video.currentTime = time;
    });
  }

  async function togglePlay() {
    if (playing) {
      Object.values(videoRefs.current).forEach((video) => video?.pause());
      setPlaying(false);
      return;
    }
    seekAll(frame);
    await Promise.allSettled(Object.values(videoRefs.current).map((video) => video?.play()));
    setPlaying(true);
  }

  React.useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      const primary = videos[0] ? videoRefs.current[videos[0].camera_key] : null;
      if (!primary) return;
      const nextFrame = Math.max(0, Math.min(maxFrame, Math.round(primary.currentTime * fps)));
      setFrame(nextFrame);
      const target = nextFrame / fps;
      Object.entries(videoRefs.current).forEach(([key, video]) => {
        if (key !== videos[0]?.camera_key && video && Math.abs(video.currentTime - target) > 0.12) {
          video.currentTime = target;
        }
      });
      if (nextFrame >= maxFrame) setPlaying(false);
    }, 100);
    return () => window.clearInterval(timer);
  }, [playing, videos, fps, maxFrame]);

  if (detail.loading) return <Loading />;
  if (detail.error) return <ErrorBox message={detail.error} />;
  if (!episode) return null;
  const timeSeriesData = timeseries.data;
  const stateKeys = timeSeriesData ? Object.keys(timeSeriesData.series).filter((key) => key.startsWith("observation.state.")) : [];
  const actionKeys = timeSeriesData ? Object.keys(timeSeriesData.series).filter((key) => key.startsWith("action.")) : [];
  return (
    <section>
      <Breadcrumb
        items={[
          ["Global", "#/"],
          [datasetId, href(["datasets", datasetId])],
          [taskId, href(["datasets", datasetId, "tasks", taskId])],
          [`episode_${String(episodeIndex).padStart(6, "0")}`, href(["datasets", datasetId, "tasks", taskId, "episodes", String(episodeIndex)])],
        ]}
      />
      <div className="sectionHeader">
        <div>
          <h1>episode_{String(episodeIndex).padStart(6, "0")}</h1>
          <p>{episode.task_text}</p>
        </div>
      </div>
      <StatGrid
        stats={[
          ["Length", number(episode.length)],
          ["FPS", number(episode.fps)],
          ["Duration", seconds(episode.duration_sec)],
          ["Rows", number(episode.row_count)],
          ["Errors", number(episode.error_count)],
          ["Warnings", number(episode.warning_count)],
        ]}
      />
      <div className="episodeLayout">
        <div className="videoAndPlots">
          <VideoGrid
            datasetId={datasetId}
            taskId={taskId}
            episodeIndex={episodeIndex}
            videos={videos}
            videoRefs={videoRefs}
          />
          <div className="transport">
            <button onClick={() => seekAll(frame - 1)}>Prev</button>
            <button onClick={togglePlay}>{playing ? "Pause" : "Play"}</button>
            <button onClick={() => seekAll(frame + 1)}>Next</button>
            <input
              type="range"
              min={0}
              max={maxFrame}
              value={frame}
              onChange={(event) => seekAll(Number(event.target.value))}
            />
            <span>Frame {number(frame)} / {number(maxFrame)}</span>
            <span>{seconds(frame / fps)}</span>
          </div>
          {timeseries.loading && <Loading />}
          {timeseries.error && <ErrorBox message={`Timeseries failed: ${timeseries.error}`} />}
          {timeSeriesData && (
            <>
              {timeSeriesData.downsampled && (
                <div className="notice">
                  Timeseries is downsampled from {number(timeSeriesData.source_length)} frames for browser performance.
                </div>
              )}
              <TimeSeriesPlot title="observation.state" data={timeSeriesData} keys={stateKeys} frame={frame} />
              <TimeSeriesPlot title="action" data={timeSeriesData} keys={actionKeys} frame={frame} />
            </>
          )}
        </div>
        <aside className="sidePanel">
          <h2>Health</h2>
          <HealthList checks={detail.data?.health_checks ?? []} />
          <h2>Files</h2>
          <div className="fileList">
            <div>{episode.parquet_path}</div>
            {videos.map((video) => <div key={video.camera_key}>{video.camera_key}: {video.path}</div>)}
          </div>
        </aside>
      </div>
    </section>
  );
}

function VideoGrid({
  datasetId,
  taskId,
  episodeIndex,
  videos,
  videoRefs,
}: {
  datasetId: string;
  taskId: string;
  episodeIndex: number;
  videos: VideoRow[];
  videoRefs: React.MutableRefObject<Record<string, HTMLVideoElement | null>>;
}) {
  return (
    <div className={`videoGrid count${Math.min(videos.length, 4)}`}>
      {videos.map((video, index) => (
        <figure className={index === 0 ? "primaryVideo" : ""} key={video.camera_key}>
          <video
            ref={(node) => { videoRefs.current[video.camera_key] = node; }}
            src={videoUrl(datasetId, taskId, episodeIndex, video.camera_key)}
            muted
            playsInline
            preload="metadata"
          />
          <figcaption>{video.camera_key.replace("observation.images.", "")}</figcaption>
        </figure>
      ))}
    </div>
  );
}

function TimeSeriesPlot({ title, data, keys, frame }: { title: string; data: Timeseries; keys: string[]; frame: number }) {
  const [selected, setSelected] = React.useState<string[]>(() => defaultSeries(keys));
  React.useEffect(() => {
    setSelected(defaultSeries(keys));
  }, [keys.join("|")]);
  return (
    <div className="plotBlock">
      <div className="plotHeader">
        <h2>{title}</h2>
        <select
          value=""
          onChange={(event) => {
            const value = event.target.value;
            if (value && !selected.includes(value)) setSelected([...selected, value]);
          }}
        >
          <option value="">Add series</option>
          {keys.map((key) => <option value={key} key={key}>{key.replace(`${title}.`, "")}</option>)}
        </select>
      </div>
      <div className="chips">
        {selected.map((key) => (
          <button key={key} onClick={() => setSelected(selected.filter((item) => item !== key))}>{key.replace(`${title}.`, "")}</button>
        ))}
      </div>
      <UPlotChart data={data} keys={selected} frame={frame} />
    </div>
  );
}

function defaultSeries(keys: string[]): string[] {
  const grippers = keys.filter((key) => key.toLowerCase().includes("gripper"));
  if (grippers.length) return grippers.slice(0, 4);
  return keys.slice(0, 6);
}

const LINE_COLORS = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#9333ea",
  "#ca8a04",
  "#0891b2",
  "#db2777",
  "#4f46e5",
  "#ea580c",
  "#0f766e",
];

function lineColor(index: number): string {
  return LINE_COLORS[index % LINE_COLORS.length];
}

function UPlotChart({ data, keys, frame }: { data: Timeseries; keys: string[]; frame: number }) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const plotRef = React.useRef<uPlot | null>(null);
  React.useEffect(() => {
    if (!ref.current) return;
    plotRef.current?.destroy();
    const width = Math.max(ref.current.clientWidth, 320);
    const aligned = [data.frame_index, ...keys.map((key) => data.series[key] ?? [])] as uPlot.AlignedData;
    const opts: uPlot.Options = {
      width,
      height: 240,
      cursor: { x: true, y: false },
      scales: { x: { time: false } },
      axes: [{ label: "frame" }, {}],
      series: [
        {},
        ...keys.map((key, index) => ({
          label: key.split(".").slice(-1)[0],
          stroke: lineColor(index),
          width: 1.5,
          points: { show: false },
        })),
      ],
    };
    plotRef.current = new uPlot(opts, aligned, ref.current);
    const observer = new ResizeObserver(() => {
      if (ref.current && plotRef.current) plotRef.current.setSize({ width: ref.current.clientWidth, height: 240 });
    });
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      plotRef.current?.destroy();
      plotRef.current = null;
    };
  }, [data, keys.join("|")]);
  React.useEffect(() => {
    const plot = plotRef.current;
    if (!plot) return;
    const idx = data.frame_index.findIndex((item) => item >= frame);
    if (idx >= 0) plot.setCursor({ left: plot.valToPos(data.frame_index[idx], "x"), top: 0 });
  }, [frame, data]);
  return <div className="plot" ref={ref} />;
}

function HealthList({ checks }: { checks: HealthCheck[] }) {
  if (!checks.length) return <div className="notice">No health checks for this episode.</div>;
  return (
    <div className="healthList">
      {checks.map((check, index) => (
        <div className={`health ${check.severity}`} key={`${check.code}-${index}`}>
          <strong>{check.severity}</strong>
          <span>{check.code}</span>
          <p>{check.message}</p>
        </div>
      ))}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(<App />);
