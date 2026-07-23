"""Interactive browser login and automatic session cookie capture."""

import time

from session_admin import (
    REVIZTO_ACCESS_CODE_URL,
    REVIZTO_LOGIN_URL,
    STRATUS_LOGIN_URLS,
    SYMETRI_LOGIN_URL,
    save_stratus_session_cookie,
    save_symetri_bearer_token,
)
from revisto_api import reconnect_revizto_from_session

LOGIN_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 1

SESSION_SIGNALS = {
    "stratus": {
        "login_url_key": "stratus",
        "cookie_names": (
            "GTPUserCompany",
            ".AspNetCore.Cookies.v2.Production",
            ".AspNetCore.Cookies.v2.ProductionC1",
        ),
    },
    "revizto": {
        "login_url_key": "revizto",
    },
}

STABLE_SESSION_POLLS = 2

# This will be used to check if the playwright is available
def playwright_available():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return False
    return True

# This will be used to require the playwright
def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright"
        ) from exc
    return sync_playwright


# This will be used to launch the browser
def _launch_browser(playwright):
    last_error = None
    for channel in ("msedge", "chrome", None):
        try:
            if channel:
                return playwright.chromium.launch(headless=False, channel=channel)
            return playwright.chromium.launch(headless=False)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(
        "Could not launch Edge, Chrome, or Chromium. "
        "Install a browser or run: playwright install chromium"
    ) from last_error


# This will be used to get the login URL for the platform
def _login_url(platform, environment="prod"):
    if platform == "stratus":
        return STRATUS_LOGIN_URLS[(environment or "prod").strip().lower()]
    if platform == "revizto":
        return REVIZTO_LOGIN_URL
    if platform == "symetri":
        return SYMETRI_LOGIN_URL
    raise ValueError(f"Unknown platform: {platform}")


def _cookie_names(cookies):
    return {cookie["name"] for cookie in cookies}


def _has_session_cookies(platform, cookies):
    if platform == "revizto":
        from revisto_api import revizto_session_cookie_usable

        return revizto_session_cookie_usable(_cookies_to_header(cookies))

    names = _cookie_names(cookies)
    required = SESSION_SIGNALS[platform]["cookie_names"]
    return any(name in names for name in required)


def _cookies_to_header(cookies):
    return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)


def wait_for_session_cookies(context, platform, timeout=LOGIN_TIMEOUT_SECONDS):
    deadline = time.time() + timeout
    stable_polls = 0
    while time.time() < deadline:
        cookies = context.cookies()
        if _has_session_cookies(platform, cookies):
            stable_polls += 1
            if stable_polls >= STABLE_SESSION_POLLS:
                return cookies
        else:
            stable_polls = 0
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"Timed out after {timeout // 60} minutes waiting for {platform} sign-in."
    )


_SYMETRI_AUTH0_STORAGE_JS = """
() => {
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (!key || !key.includes("auth0spajs")) {
      continue;
    }
    try {
      const item = JSON.parse(localStorage.getItem(key));
      const body = item?.body || item;
      const token = body?.access_token;
      if (typeof token === "string" && token.split(".").length === 3) {
        return token;
      }
    } catch (_error) {
      // Ignore malformed cache entries.
    }
  }
  return null;
}
"""


def _read_symetri_token_from_pages(context):
    from symetri_api import bearer_token_usable

    for page in context.pages:
        try:
            token = page.evaluate(_SYMETRI_AUTH0_STORAGE_JS)
        except Exception:
            continue
        if token and bearer_token_usable(token):
            return token
    return None


def capture_symetri_bearer_token(manual_confirm=False, timeout=LOGIN_TIMEOUT_SECONDS):
    """Open a browser, wait for sign-in, return a bearer token from Auth0 storage or API traffic."""
    from symetri_api import bearer_token_usable

    login_url = SYMETRI_LOGIN_URL
    sync_playwright = _require_playwright()
    captured = []

    def remember_token(token):
        if token and bearer_token_usable(token):
            captured.append(token)

    def on_request(request):
        if "backend.my.symetri.com" not in request.url:
            return
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth:
            return
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()
        remember_token(token)

    def attach_page(page):
        page.on("request", on_request)

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        try:
            context = browser.new_context()
            context.on("request", on_request)
            context.on("page", attach_page)
            page = context.new_page()
            attach_page(page)
            page.goto(login_url, wait_until="domcontentloaded")
            if manual_confirm:
                input(
                    "Sign in at my.symetri.com in the Playwright browser window, "
                    "then press Enter here..."
                )
            else:
                deadline = time.time() + timeout
                while time.time() < deadline:
                    if captured:
                        break
                    token = _read_symetri_token_from_pages(context)
                    if token:
                        remember_token(token)
                        break
                    time.sleep(POLL_INTERVAL_SECONDS)
                if not captured:
                    raise TimeoutError(
                        "Timed out waiting for Symetri sign-in. "
                        "Use the separate browser window that opened (not your normal browser tab), "
                        "sign in at my.symetri.com, and try Reconnect again."
                    )
        finally:
            browser.close()

    if not captured:
        raise RuntimeError(
            "No Symetri bearer token captured. "
            "Sign in using the separate browser window opened by Reconnect."
        )
    return captured[-1]


_REVIZTO_RECONNECT_BANNER_JS = """
(message) => {
  const id = "umci-revizto-reconnect-banner";
  let banner = document.getElementById(id);
  if (!banner) {
    banner = document.createElement("div");
    banner.id = id;
    banner.style.cssText = [
      "position:fixed",
      "top:0",
      "left:0",
      "right:0",
      "z-index:2147483647",
      "background:#0f3d5c",
      "color:#fff",
      "padding:14px 18px",
      "font:600 15px/1.4 Segoe UI, Arial, sans-serif",
      "box-shadow:0 2px 10px rgba(0,0,0,.35)",
    ].join(";");
    document.documentElement.appendChild(banner);
  }
  banner.textContent = message;
}
"""


def _show_revizto_reconnect_banner(page, message):
    try:
        page.evaluate(_REVIZTO_RECONNECT_BANNER_JS, message)
    except Exception:
        pass


def _inject_revizto_banner_on_page(page, message):
    _show_revizto_reconnect_banner(page, message)
    page.on(
        "domcontentloaded",
        lambda: _show_revizto_reconnect_banner(page, message),
    )


def capture_revizto_session_and_access_code(manual_confirm=False, timeout=LOGIN_TIMEOUT_SECONDS):
    """
    Sign in to ws.revizto.com, capture session cookie, then obtain a fresh API access code.
    """
    from revisto_api import ACCESS_CODE_PATTERN, extract_access_code_from_payload, request_revizto_access_code

    login_url = REVIZTO_LOGIN_URL
    sync_playwright = _require_playwright()
    captured_codes = []

    def on_response(response):
        try:
            if "revizto.com" not in response.url:
                return
            try:
                body = response.json()
            except ValueError:
                body = response.text()
            code = extract_access_code_from_payload(body)
            if code:
                captured_codes.append(code)
        except Exception:
            return

    sign_in_message = (
        "User Disabling Platform: sign in to Revizto in THIS window (not your normal browser tab)."
    )
    api_message = (
        "User Disabling Platform: stay on the access code page "
        "(login?request=accessCode), copy/generate the access code, "
        "and leave this window open until it is captured."
    )

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        try:
            context = browser.new_context()
            context.on("response", on_response)

            def attach_page(new_page):
                _inject_revizto_banner_on_page(new_page, sign_in_message)

            context.on("page", attach_page)
            page = context.new_page()
            attach_page(page)
            page.goto(login_url, wait_until="domcontentloaded")
            try:
                page.bring_to_front()
            except Exception:
                pass
            _show_revizto_reconnect_banner(page, sign_in_message)

            if manual_confirm:
                input(
                    "Sign in to ws.revizto.com in the Playwright browser window, "
                    "then press Enter here..."
                )
                cookies = context.cookies()
            else:
                cookies = wait_for_session_cookies(context, "revizto", timeout=timeout)

            cookie_header = _cookies_to_header(cookies)
            if not _has_session_cookies("revizto", cookies):
                raise RuntimeError("Revizto sign-in did not look complete.")

            for active_page in context.pages:
                _show_revizto_reconnect_banner(active_page, api_message)
                try:
                    active_page.bring_to_front()
                except Exception:
                    pass

            try:
                page.goto(REVIZTO_ACCESS_CODE_URL, wait_until="domcontentloaded", timeout=30000)
                _show_revizto_reconnect_banner(page, api_message)
            except Exception:
                pass

            code_deadline = time.time() + min(timeout, 240)
            while time.time() < code_deadline and not captured_codes:
                for active_page in context.pages:
                    try:
                        match = ACCESS_CODE_PATTERN.search(active_page.content())
                    except Exception:
                        match = None
                    if match:
                        captured_codes.append(match.group(0))
                        break
                if captured_codes:
                    break
                time.sleep(POLL_INTERVAL_SECONDS)

            if captured_codes:
                access_code = captured_codes[-1]
            else:
                try:
                    access_code = request_revizto_access_code(cookie_header)
                except Exception as exc:
                    raise RuntimeError(
                        "Could not capture a Revizto API access code. "
                        "Check your taskbar for the separate browser window that opened, "
                        "then open https://ws.revizto.com/login?request=accessCode "
                        "and copy the access code. "
                        "Or click Reconnect on this page and paste it manually. "
                        f"({exc})"
                    ) from exc
            return cookie_header, access_code
        finally:
            browser.close()


def capture_session_cookie(platform, environment="prod", manual_confirm=False, timeout=LOGIN_TIMEOUT_SECONDS):
    """Open a browser, wait for sign-in, return a Cookie header string."""
    platform = platform.strip().lower()
    if platform not in SESSION_SIGNALS:
        raise ValueError(f"Unknown platform: {platform}")

    login_url = _login_url(platform, environment)
    sync_playwright = _require_playwright()

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded")
            if manual_confirm:
                input("Sign in, then press Enter here...")
                cookies = context.cookies()
            else:
                cookies = wait_for_session_cookies(context, platform, timeout=timeout)
        finally:
            browser.close()

    if not cookies:
        raise RuntimeError("No cookies captured. Did you finish signing in?")
    if not _has_session_cookies(platform, cookies):
        raise RuntimeError(f"Sign-in did not look complete for {platform}.")
    return _cookies_to_header(cookies)


def connect_platform_session(platform, environment="prod", validate=True, manual_confirm=False):
    """Sign in via browser, capture session credentials, validate, and save to .env."""
    platform = platform.strip().lower()
    if platform == "symetri":
        token = capture_symetri_bearer_token(manual_confirm=manual_confirm)
        return save_symetri_bearer_token(token, validate=validate)
    if platform == "revizto":
        cookie, access_code = capture_revizto_session_and_access_code(manual_confirm=manual_confirm)
        return reconnect_revizto_from_session(cookie, access_code=access_code)
    cookie = capture_session_cookie(
        platform,
        environment=environment,
        manual_confirm=manual_confirm,
    )
    if platform == "stratus":
        return save_stratus_session_cookie(cookie, environment=environment, validate=validate)
    raise ValueError(f"Unknown platform: {platform}")
