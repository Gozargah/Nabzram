

import {
    Subscription,
    SubscriptionDetail,
    ServerStatusResponse,
    SubscriptionCreate,
    SubscriptionUpdate,
    SettingsResponse,
    SettingsUpdate,
    SubscriptionUrlTestResponse,
    SystemInfo,
    XrayVersionInfo,
    XrayUpdateRequest,
    XrayUpdateResponse,
    GeodataUpdateResponse,
    SubscriptionCreateResponse,
    SubscriptionUpdateResponse,
    SubscriptionDeleteResponse,
    SubscriptionRefreshResponse,
    ServerStartResponse,
    ServerStopResponse,
    SettingsUpdateResponse,
    LogSnapshotResponse,
    LogStreamBatchResponse
} from '../types';

async function callApp<T>(method: string, ...args: any[]): Promise<T> {
  const api = (window as any).pywebview?.api;
  if (!api || typeof api[method] !== 'function') {
    throw new Error(`App API not available: ${method}`);
  }
  const res = await api[method].apply(api, args);
  if (res && typeof res === 'object' && res.success === false) {
    const extra = res.data && Object.keys(res.data).length ? ` (${JSON.stringify(res.data)})` : '';
    throw new Error(`${res.message || 'Operation failed'}${extra}`);
  }
  return res as T;
}

export async function getSubscriptions(): Promise<Subscription[]> {
    return callApp<Subscription[]>('list_subscriptions');
}

export async function getSubscriptionDetails(id: string): Promise<SubscriptionDetail> {
    return callApp<SubscriptionDetail>('get_subscription', id);
}

export async function createSubscription(data: SubscriptionCreate): Promise<SubscriptionCreateResponse> {
    return callApp('create_subscription', data);
}

export async function updateSubscription(id: string, data: SubscriptionUpdate): Promise<SubscriptionUpdateResponse> {
    return callApp('update_subscription', id, data);
}

export async function deleteSubscription(id: string): Promise<SubscriptionDeleteResponse> {
    return callApp('delete_subscription', id);
}

export async function refreshSubscriptionServers(id: string): Promise<SubscriptionRefreshResponse> {
    return callApp('refresh_subscription_servers', id);
}

export async function startServer(subscriptionId: string, serverId: string): Promise<ServerStartResponse> {
    return callApp('start_server', subscriptionId, serverId);
}

export async function stopServer(): Promise<ServerStopResponse> {
    return callApp('stop_server');
}

export async function getServerStatus(): Promise<ServerStatusResponse> {
    return callApp<ServerStatusResponse>('get_server_status');
}

export async function getSettings(): Promise<SettingsResponse> {
    return callApp<SettingsResponse>('get_settings');
}

export async function updateSettings(data: SettingsUpdate): Promise<SettingsUpdateResponse> {
    return callApp('update_settings', data);
}

export async function testSubscriptionServers(id: string): Promise<SubscriptionUrlTestResponse> {
    return callApp<SubscriptionUrlTestResponse>('test_subscription_servers', id);
}

export async function getXrayStatus(): Promise<SystemInfo> {
    return callApp<SystemInfo>('get_xray_status');
}

export async function getXrayVersionInfo(): Promise<XrayVersionInfo> {
    return callApp<XrayVersionInfo>('get_xray_version_info');
}

export async function updateXray(data: XrayUpdateRequest): Promise<XrayUpdateResponse> {
    return callApp<XrayUpdateResponse>('update_xray', data);
}

export async function updateGeodata(): Promise<GeodataUpdateResponse> {
    return callApp<GeodataUpdateResponse>('update_geodata');
}

export async function getLogSnapshot(limit?: number): Promise<LogSnapshotResponse> {
    return callApp<LogSnapshotResponse>('get_log_snapshot', limit);
}

export async function getLogStreamBatch(since_ms?: number, limit?: number): Promise<LogStreamBatchResponse> {
    return callApp<LogStreamBatchResponse>('get_log_stream_batch', since_ms, limit);
}