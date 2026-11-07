from __future__ import annotations

import asyncio
import json
import webbrowser
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx2
from mcp import Client
from mcp.client.auth import AuthorizationCodeResult, OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from pydantic import AnyUrl


class FileTokenStorage:
    """Persist OAuth tokens and dynamic client registration outside the repo."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def get_tokens(self) -> OAuthToken | None:
        raw = self._read().get("tokens")
        return OAuthToken.model_validate(raw) if raw else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._read()
        data["tokens"] = tokens.model_dump(mode="json")
        self._write(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        raw = self._read().get("client_info")
        return OAuthClientInformationFull.model_validate(raw) if raw else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        data = self._read()
        data["client_info"] = client_info.model_dump(mode="json")
        self._write(data)


def raw_tool_name(name: str) -> str:
    prefix = "mcp__PrimeXBT__"
    return name[len(prefix) :] if name.startswith(prefix) else name


def parse_authorization_result(url: str) -> AuthorizationCodeResult:
    params = parse_qs(urlparse(url.strip()).query)
    if "error" in params:
        description = params.get("error_description", params["error"])[0]
        raise RuntimeError(f"PrimeXBT OAuth failed: {description}")
    if "code" not in params or "state" not in params:
        raise RuntimeError("OAuth redirect URL is missing code/state")
    return AuthorizationCodeResult(
        code=params["code"][0],
        state=params["state"][0],
        iss=params["iss"][0] if "iss" in params else None,
    )


class OAuthCallbackServer:
    """Temporary localhost listener that receives the browser OAuth redirect."""

    def __init__(self, redirect_url: str) -> None:
        parsed = urlparse(redirect_url)
        if parsed.scheme != "http" or not parsed.hostname or not parsed.port:
            raise ValueError("OAuth redirect URL must be an http localhost URL with a port")
        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("OAuth callback listener only supports localhost")
        self.redirect_url = redirect_url
        self.host = parsed.hostname
        self.port = parsed.port
        self.path = parsed.path or "/"
        self._server: asyncio.AbstractServer | None = None
        self._future: asyncio.Future[AuthorizationCodeResult] | None = None

    async def start(self) -> None:
        self._future = asyncio.get_running_loop().create_future()
        self._server = await asyncio.start_server(self._handle_request, self.host, self.port)

    async def wait(self) -> AuthorizationCodeResult:
        if self._future is None:
            raise RuntimeError("OAuth callback server is not running")
        return await self._future

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self._server = None

    async def _handle_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        status = "200 OK"
        title = "PrimeXBT authorization received"
        message = "You can close this tab and return to the A+ Scalper terminal."
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
            request_line = request.decode("utf-8", errors="replace").split("\r\n", 1)[0]
            method, target, _ = request_line.split(" ", 2)
            if method != "GET" or urlparse(target).path != self.path:
                status = "404 Not Found"
                title = "Callback not found"
                message = "This local endpoint only accepts the PrimeXBT OAuth callback."
            else:
                full_url = f"http://{self.host}:{self.port}{target}"
                result = parse_authorization_result(full_url)
                if self._future is not None and not self._future.done():
                    self._future.set_result(result)
        except Exception as exc:
            status = "400 Bad Request"
            title = "PrimeXBT authorization failed"
            message = str(exc)
            if self._future is not None and not self._future.done():
                self._future.set_exception(exc)

        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title></head>"
            "<body style='font-family:system-ui;margin:48px'>"
            f"<h1>{title}</h1><p>{message}</p></body></html>"
        ).encode("utf-8")
        response = (
            f"HTTP/1.1 {status}\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        writer.write(response + body)
        await writer.drain()
        writer.close()
        await writer.wait_closed()


async def _open_browser(url: str) -> None:
    print("\nPrimeXBT authorization is required.")
    print(f"If the browser does not open, visit:\n{url}\n")
    await asyncio.to_thread(webbrowser.open, url)


async def _read_redirect_url() -> AuthorizationCodeResult:
    prompt = (
        "Local callback port is unavailable. After PrimeXBT authorizes the connection, "
        "copy the FULL redirected URL from your browser address bar and paste it here:\n> "
    )
    redirect_url = await asyncio.to_thread(input, prompt)
    return parse_authorization_result(redirect_url)


class PrimeXbtMcpToolCaller:
    """Persistent local Streamable-HTTP client for PrimeXBT's official MCP server."""

    def __init__(
        self,
        server_url: str,
        token_file: str | Path,
        *,
        redirect_url: str = "http://localhost:3030/callback",
    ) -> None:
        self.server_url = server_url
        self.token_file = Path(token_file)
        self.redirect_url = redirect_url
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self._tool_names: set[str] = set()

    async def __aenter__(self) -> PrimeXbtMcpToolCaller:
        callback = OAuthCallbackServer(self.redirect_url)
        callback_handler = callback.wait
        callback_started = False
        try:
            await callback.start()
            callback_started = True
            print(
                f"OAuth callback listener ready at {self.redirect_url} "
                "(browser redirect will be captured automatically)."
            )
        except OSError as exc:
            print(
                f"Could not listen on {self.redirect_url}: {exc}. "
                "Falling back to manual URL paste."
            )
            callback_handler = _read_redirect_url

        oauth = OAuthClientProvider(
            server_url=self.server_url,
            client_metadata=OAuthClientMetadata(
                client_name="A+ Scalper Engine",
                redirect_uris=[AnyUrl(self.redirect_url)],
            ),
            storage=FileTokenStorage(self.token_file),
            redirect_handler=_open_browser,
            callback_handler=callback_handler,
        )
        stack = AsyncExitStack()
        try:
            http_client = await stack.enter_async_context(
                httpx2.AsyncClient(auth=oauth, timeout=httpx2.Timeout(30.0, read=300.0))
            )
            transport = streamable_http_client(self.server_url, http_client=http_client)
            client = await stack.enter_async_context(Client(transport))
            tools = await client.list_tools()
            self._tool_names = {tool.name for tool in tools.tools}
            self._client = client
            self._stack = stack
            return self
        except Exception:
            await stack.aclose()
            raise
        finally:
            if callback_started:
                await callback.close()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._client = None
        self._tool_names.clear()

    @property
    def tool_names(self) -> frozenset[str]:
        return frozenset(self._tool_names)

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("MCP client is not connected")
        tool = raw_tool_name(name)
        if self._tool_names and tool not in self._tool_names:
            raise RuntimeError(f"PrimeXBT MCP tool is unavailable: {tool}")
        result = await self._client.call_tool(tool, args)
        if getattr(result, "is_error", False):
            messages = [getattr(item, "text", str(item)) for item in result.content]
            raise RuntimeError(f"PrimeXBT MCP tool {tool} failed: {'; '.join(messages)}")
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return {"structuredContent": structured}
        for item in getattr(result, "content", []):
            text = getattr(item, "text", None)
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {"content": [str(item) for item in getattr(result, "content", [])]}
