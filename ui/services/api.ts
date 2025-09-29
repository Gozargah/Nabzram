import { API_BASE_URL } from '../constants';
import { Subscription, SubscriptionDetail, ServerStatusResponse, SubscriptionCreate, SubscriptionUpdate, SettingsResponse, SettingsUpdate, SubscriptionUrlTestResponse, SystemInfo, XrayVersionInfo, XrayUpdateRequest, XrayUpdateResponse, GeodataUpdateResponse } from '../types';

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        let errorData;
        try {
            errorData = await response.json();
        } catch (e) {
            throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
        }
        const errorMessage = errorData.detail?.[0]?.msg || errorData.detail || 'An unknown API error occurred';
        throw new Error(errorMessage);
    }
    return response.json() as Promise<T>;
}

export async function getSubscriptions(): Promise<Subscription[]> {
    const response = await fetch(`${API_BASE_URL}/subscriptions`);
    return handleResponse<Subscription[]>(response);
}

export async function getSubscriptionDetails(id: string): Promise<SubscriptionDetail> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/${id}`);
    return handleResponse<SubscriptionDetail>(response);
}

export async function createSubscription(data: SubscriptionCreate): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/subscriptions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

export async function updateSubscription(id: string, data: SubscriptionUpdate): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

export async function deleteSubscription(id: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/${id}`, {
        method: 'DELETE',
    });
    return handleResponse(response);
}

export async function refreshSubscriptionServers(id: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/${id}/update`, {
        method: 'POST',
    });
    return handleResponse(response);
}

export async function startServer(subscriptionId: string, serverId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/${subscriptionId}/servers/${serverId}/start`, {
        method: 'POST',
    });
    return handleResponse(response);
}

export async function stopServer(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/server/stop`, {
        method: 'POST',
    });
    return handleResponse(response);
}

export async function getServerStatus(): Promise<ServerStatusResponse> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/server/status`);
    return handleResponse<ServerStatusResponse>(response);
}

export async function getSettings(): Promise<SettingsResponse> {
    const response = await fetch(`${API_BASE_URL}/settings`);
    return handleResponse<SettingsResponse>(response);
}

export async function updateSettings(data: SettingsUpdate): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return handleResponse(response);
}

export async function testSubscriptionServers(id: string): Promise<SubscriptionUrlTestResponse> {
    const response = await fetch(`${API_BASE_URL}/subscriptions/${id}/url-test`, {
        method: 'POST',
    });
    return handleResponse<SubscriptionUrlTestResponse>(response);
}

export async function getXrayStatus(): Promise<SystemInfo> {
    const response = await fetch(`${API_BASE_URL}/system/xray`);
    return handleResponse<SystemInfo>(response);
}

export async function getXrayVersionInfo(): Promise<XrayVersionInfo> {
    const response = await fetch(`${API_BASE_URL}/updates/xray/info`);
    return handleResponse<XrayVersionInfo>(response);
}

export async function updateXray(data: XrayUpdateRequest): Promise<XrayUpdateResponse> {
    const response = await fetch(`${API_BASE_URL}/updates/xray/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    return handleResponse<XrayUpdateResponse>(response);
}

export async function updateGeodata(): Promise<GeodataUpdateResponse> {
    const response = await fetch(`${API_BASE_URL}/updates/geodata/update`, {
        method: 'POST',
    });
    return handleResponse<GeodataUpdateResponse>(response);
}
