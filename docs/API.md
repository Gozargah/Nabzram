# window.pywebview.api Reference

This document lists all methods exposed to the frontend via `window.pywebview.api` and their response shapes.

Global error model (all methods)
- Errors are returned as an object and NEVER thrown by the bridge:
```json
{
  "success": false,
  "message": "Human readable error message",
  "data": { /* optional extra details */ }
}
```

When calling from the UI, you should check if `res.success === false` and handle accordingly.

---

Window controls (from WindowApi)
- show(): void
- hide(): void
- minimize(): void
- maximize(): void
- restore(): void
- close(): void
- toggle(): void
- quit(): void
- is_visible(): boolean
- is_focused(): boolean
- toggle_fullscreen(): void
- set_on_top(value: boolean): void
- resize(width: number, height: number): void
- move(x: number, y: number): void
- get_size(): { 0: number, 1: number }  // tuple [width, height]
- get_position(): { 0: number, 1: number } // tuple [x, y]

Notes: These methods either return primitives/tuples or no value. On internal errors you will receive the global error model.

---

Settings
1) get_settings()
Response:
```json
{
  "socks_port": number | null,
  "http_port": number | null,
  "xray_binary": string | null,
  "xray_assets_folder": string | null,
  "xray_log_level": "debug" | "info" | "warning" | "error" | "none" | null
}
```

2) update_settings(payload)
Payload:
```json
{
  "socks_port"?: number,
  "http_port"?: number,
  "xray_binary"?: string,
  "xray_assets_folder"?: string,
  "xray_log_level"?: "debug" | "info" | "warning" | "error" | "none"
}
```
Success response:
```json
{
  "message": "Settings updated successfully",
  "socks_port": number | null,
  "http_port": number | null,
  "xray_binary": string | null,
  "xray_assets_folder": string | null,
  "xray_log_level": "debug" | "info" | "warning" | "error" | "none" | null
}
```
Error response: global error model (e.g., validation issues)

---

Subscriptions
1) list_subscriptions()
Response:
```json
[
  {
    "id": string,
    "name": string,
    "url": string,
    "last_updated": string | null, // ISO datetime
    "server_count": number,
    "user_info": {
      "used_traffic": number,
      "total": number | null,
      "expire": string | null // ISO datetime
    } | null
  }
]
```

2) get_subscription(subscription_id)
Response:
```json
{
  "id": string,
  "name": string,
  "url": string,
  "last_updated": string | null,
  "server_count": number,
  "user_info": { "used_traffic": number, "total": number | null, "expire": string | null } | null,
  "servers": [ { "id": string, "remarks": string, "status": "stopped" | "running" | "error" } ]
}
```
Error: global error model (e.g., not found)

3) create_subscription(payload)
Payload:
```json
{ "name": string, "url": string }
```
Success response:
```json
{ "message": string, "id": string, "name": string, "server_count": number }
```
Error: global error model

4) update_subscription(subscription_id, payload)
Payload:
```json
{ "name"?: string, "url"?: string }
```
Success response:
```json
{ "message": "Subscription updated successfully", "id": string, "name": string }
```
Error: global error model

5) delete_subscription(subscription_id)
Success response:
```json
{ "message": string, "id": string, "name": string }
```
Error: global error model

6) refresh_subscription_servers(subscription_id)
Success response:
```json
{
  "message": string,
  "id": string,
  "server_count": number,
  "last_updated": string | null
}
```
Error: global error model

---

Server control
1) start_server(subscription_id, server_id)
Success response:
```json
{ "message": string, "server_id": string, "status": "running", "remarks": string }
```
If already running, returns the same shape with an informative message.
Error: global error model

2) stop_server()
Success response (server not running):
```json
{ "message": "No server is currently running", "server_id": null, "status": "stopped" }
```
Success response (stopped):
```json
{ "message": "Server stopped successfully", "server_id": string, "status": "stopped" }
```
Error: global error model

3) get_server_status()
If no server running:
```json
{ "message": "No server is currently running", "server_id": null, "status": "stopped", "remarks": null, "process_id": null, "start_time": null, "allocated_ports": null }
```
If running:
```json
{
  "message": "Server is running",
  "server_id": string,
  "status": "running",
  "remarks": string,
  "process_id": number | null,
  "start_time": string | null, // ISO datetime
  "allocated_ports": [ { "port": number, "protocol": string, "tag": string | null } ]
}
```
Error: global error model (rare)

4) test_subscription_servers(subscription_id)
Response:
```json
{
  "message": string,
  "subscription_id": string,
  "subscription_name": string,
  "total_servers": number,
  "successful_tests": number,
  "failed_tests": number,
  "results": [
    {
      "server_id": string,
      "remarks": string,
      "success": boolean,
      "ping_ms": number | null,
      "error": string | null,
      "socks_port": number,
      "http_port": number
    }
  ]
}
```
Error: global error model (e.g., subscription not found)

---

System
1) get_xray_status()
Response:
```json
{
  "available": boolean,
  "version": string | null,
  "commit": string | null,
  "go_version": string | null,
  "arch": string | null
}
```

---

Updates
1) get_xray_version_info()
Success response:
```json
{
  "current_version": string | null,
  "latest_version": string,
  "available_versions": [ { "version": string, "size_bytes": number | null } ]
}
```
Error: global error model

2) update_xray(payload)
Payload:
```json
{ "version"?: string }
```
Success response (already up to date):
```json
{ "message": "Xray is already up to date (version <v>)", "version": string, "current_version": string | null }
```
Success response (updated):
```json
{ "message": "Successfully updated Xray to version <v>", "version": string, "current_version": string | null }
```
Error: global error model (e.g., invalid version or download failure)

3) update_geodata()
Success response:
```json
{
  "message": string,
  "updated_files": { "geoip.dat": boolean, "geosite.dat": boolean, "...": boolean },
  "assets_folder": string
}
```
Error: global error model (e.g., assets folder not configured)

---

Appearance
1) get_appearance()
Response:
```json
{
  "theme": string | null,
  "font": string | null
}
```

2) update_appearance(payload)
Payload:
```json
{
  "theme"?: string,
  "font"?: string
}
```
Success response:
```json
{
  "success": true,
  "message": "Appearance updated successfully",
  "theme": string | null,
  "font": string | null
}
```
Error: global error model (e.g., validation issues)

---

UI error-handling pattern
```ts
async function callApp<T>(method: string, ...args: any[]): Promise<T> {
  const api = (window as any).pywebview?.api;
  if (!api || typeof api[method] !== 'function') {
    throw new Error(`App API not available: ${method}`);
  }
  const res = await api[method](...args);
  if (res && typeof res === 'object' && res.success === false) {
    const extra = res.data && Object.keys(res.data).length ? ` (${JSON.stringify(res.data)})` : '';
    throw new Error(`${res.message || 'Operation failed'}${extra}`);
  }
  return res as T;
}
```


