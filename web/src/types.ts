export interface Dataset {
  id: string;
  name: string;
  root: string;
  root_exists?: boolean;
  active_generation_id?: number | null;
  last_indexed_at?: string | null;
  task_count?: number | null;
  episode_count?: number | null;
  frame_count?: number | null;
  video_count?: number | null;
  duration_sec?: number | null;
  error_count?: number | null;
  warning_count?: number | null;
  info_count?: number | null;
  cameras?: string[];
  schema?: Record<string, unknown>;
}

export interface Task {
  dataset_id: string;
  generation_id: number;
  task_id: string;
  task_text: string | null;
  episode_count: number;
  frame_count: number;
  video_count: number;
  duration_sec: number;
  min_length: number | null;
  p50_length: number | null;
  p95_length: number | null;
  max_length: number | null;
  error_count: number;
  warning_count: number;
  info_count: number;
  cameras: string[];
  schema: Record<string, unknown>;
}

export interface TaskEpisodeSummary {
  task_id: string;
  task_text: string | null;
  episode_count: number;
}

export interface TaskSummary {
  items: TaskEpisodeSummary[];
  total: number;
  episode_total: number;
}

export interface Episode {
  dataset_id: string;
  generation_id: number;
  task_id: string;
  episode_index: number;
  length: number;
  fps: number;
  duration_sec: number;
  parquet_path: string;
  task_text: string | null;
  cameras: string[];
  frame_start: number | null;
  frame_end: number | null;
  timestamp_start: number | null;
  timestamp_end: number | null;
  row_count: number | null;
  error_count: number;
  warning_count: number;
  info_count: number;
}

export interface VideoRow {
  camera_key: string;
  path: string;
  exists_flag: number;
  width: number | null;
  height: number | null;
  fps: number | null;
  duration_sec: number | null;
  codec: string | null;
  nb_frames: number | null;
  probe_error: string | null;
}

export interface HealthCheck {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  path: string | null;
  details: Record<string, unknown>;
}

export interface EpisodeDetail {
  episode: Episode & { uid: string };
  videos: VideoRow[];
  health_checks: HealthCheck[];
}

export interface Timeseries {
  frame_index: number[];
  timestamp: number[];
  series: Record<string, number[]>;
  downsampled: boolean;
  source_length: number;
}

export interface Paged<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface IndexRun {
  id: number;
  dataset_id: string;
  generation_id: number | null;
  status: string;
  phase: string;
  started_at: string;
  finished_at: string | null;
  total_items: number;
  processed_items: number;
  error_message: string | null;
}

export interface IndexRuns {
  runs: IndexRun[];
  events: Array<Record<string, unknown>>;
}
