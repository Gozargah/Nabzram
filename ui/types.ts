export enum ServerStatus {
  STOPPED = 'stopped',
  RUNNING = 'running',
  ERROR = 'error',
}

export interface Server {
  id: string;
  remarks: string;
  status: ServerStatus;
}

export interface SubscriptionUserInfo {
  used_traffic: number;
  total: number | null;
  expire: string | null;
}

export interface Subscription {
  id: string;
  name: string;
  url: string;
  last_updated: string | null;
  server_count: number;
  user_info: SubscriptionUserInfo | null;
}

export interface SubscriptionDetail extends Subscription {
  servers: Server[];
}

export interface AllocatedPort {
  port: number;
  protocol: string;
  tag: string;
}

export interface ServerStatusResponse {
  success: boolean;
  message: string;
  server_id: string | null;
  status: ServerStatus;
  remarks: string | null;
  process_id?: number | null;
  start_time?: string | null;
  allocated_ports?: AllocatedPort[] | null;
}

export interface SubscriptionCreate {
  name: string;
  url: string;
}

export interface SubscriptionUpdate {
  name?: string | null;
  url?: string | null;
}

export interface ServerTestResult {
  server_id: string;
  remarks: string;
  success: boolean;
  ping_ms: number | null;
  error: string | null;
  socks_port: number;
  http_port: number;
}

export interface SubscriptionUrlTestResponse {
  success: boolean;
  message: string;
  subscription_id: string;
  subscription_name: string;
  total_servers: number;
  successful_tests: number;
  failed_tests: number;
  results: ServerTestResult[];
}

export interface SettingsResponse {
  socks_port: number | null;
  http_port: number | null;
  xray_binary: string | null;
  xray_assets_folder: string | null;
  xray_log_level: string | null;
}

export interface SettingsUpdate {
  socks_port?: number | null;
  http_port?: number | null;
  xray_binary?: string | null;
  xray_assets_folder?: string | null;
  xray_log_level?: string | null;
}

export interface SystemInfo {
  available: boolean;
  version: string | null;
  commit: string | null;
  go_version: string | null;
  arch: string | null;
}

export interface XrayAssetInfo {
    version: string;
    size_bytes: number | null;
}

export interface XrayVersionInfo {
    current_version: string | null;
    latest_version: string;
    available_versions: XrayAssetInfo[];
}

export interface XrayUpdateRequest {
    version?: string | null;
}

export interface XrayUpdateResponse {
    success: boolean;
    message: string;
    version: string;
    current_version: string | null;
}

export interface GeodataUpdateResponse {
    success: boolean;
    message: string;
    updated_files: Record<string, boolean>;
    assets_folder: string;
}