# Homey

Control an Athom Homey from Noxus workflows using Homey's authenticated HTTP
API.

## Nodes

- **List Homey devices** returns every device visible to the configured
  credential.
- **Get Homey device** loads the connected Homey's devices into a selector and
  returns the selected device with its current capabilities.
- **Set Homey capability** lets you select a device, loads that device's
  capabilities, and changes the selected capability such as `onoff`, `dim`, or
  `target_temperature`.
- **Trigger Homey Flow** lets you select standard or Advanced Flow, loads the
  matching flows from Homey, and starts the selected flow.

## Authentication

The plugin supports both Homey generations:

### Homey Pro 2023 and newer

Create an API key in the Homey Web App under **Settings → API Keys**, then add a
**Homey** integration in Noxus with:

- **Homey address**: an address reachable from the Noxus plugin sandbox, for
  example `http://192.168.1.100` or Homey's secure local URL.
- **API key**: the Homey API key. Noxus stores it as a masked integration
  credential and injects it only while a node runs.

### Homey Pro 2016–2019

These models use Homey's OAuth flow. Create a Web API client under **My API
Clients** in the [Homey Developer Tools](https://tools.developer.homey.app/),
then configure the **Homey Account** provider in Noxus Platform settings with
its client ID and client secret. Register this redirect URI on the Homey API
client:

```text
https://<your-noxus-backend>/integrations/oauth/callback
```

Workspace users can then open **Workspace control → Connections**, choose
Homey, and approve the Homey consent screen. Noxus securely stores and rotates
the resulting OAuth refresh token. The plugin uses the current access token to:

1. Load the account's Homeys from `/user/me`.
2. Select the first remotely reachable Homey and use its `remoteUrl`.
3. Create a delegation token and exchange it for a short-lived Homey session.
4. Call the Homey over its cloud API URL.

No bearer/session token or private IP address is entered manually. The OAuth
and session sequence follows the official
[Homey HTTP specification](https://api.developer.homey.app/http-and-socket.io/http-specification).

For API-key connections, keep **Verify TLS certificates** enabled for HTTPS
addresses unless the Homey endpoint uses a private, self-signed certificate.

Grant the API key or OAuth client the permissions used by your workflows.
Listing and reading devices needs device read access, changing a capability
needs device control access, and triggering flows needs flow start access. The
integration readiness check also needs system read access.

The API-key form still accepts a private/LAN address when desired. In that
mode, the sandbox provider and network policy must allow the plugin worker to
reach the Homey. OAuth connections always use Homey's `remoteUrl` instead.

Homey responses with status `429` are retried up to four total attempts using
1, 2, and 4 second delays. A longer `Retry-After` response header is respected,
with each delay capped at 30 seconds.

## Capability values

The **Set Homey capability** node accepts a JSON scalar:

- `true` or `false` for `onoff`
- `0.5` for `dim`
- `21.5` for `target_temperature`
- `"heat"` for an enum value

Unquoted text is treated as a string for convenience. Objects, arrays, and
`null` are rejected because Homey's capability API accepts only strings,
numbers, and booleans.

## Development

From this directory:

```bash
noxus plugin validate
noxus plugin generate-manifest
pytest
```
