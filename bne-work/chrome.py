#!/usr/bin/env python3
"""Drive the compiler's own Chrome through AppleScript, for libraries that refuse scripts.

The Biblioteca Nacional de España answers 403 to curl, to a full set of browser headers and to headless
Chrome alike; in an ordinary window the same pages open. So this asks Chrome to do the browsing: it
keeps one window of its own (it does not touch the others), navigates it, waits for the page to settle,
and reads back whatever a little JavaScript returns.

    from chrome import Chrome
    with Chrome() as c:
        c.go("https://bnedigital.bne.es/...")
        print(c.js("document.title"))

Chrome must have View > Developer > Allow JavaScript from Apple Events turned on, and it must be
running. Nothing is typed into any page, no cookie or session is read out, and only the one window
this makes is used.
"""
import json, subprocess, time

WINDOW_MARK = "about:blank#japan-bib"      # how our own window is recognised


def osascript(script, timeout=60):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout.strip()


class Chrome:
    def __init__(self, keep=False):
        self.keep = keep                    # leave the window open at the end
        self.win = None

    def __enter__(self):
        osascript('tell application "Google Chrome" to make new window with properties {bounds:{40, 40, 1200, 900}}')
        osascript(f'tell application "Google Chrome" to set URL of active tab of front window to "{WINDOW_MARK}"')
        self.win = 1                        # the new window is the front one; we address it as window 1
        return self

    def __exit__(self, *exc):
        if not self.keep:
            try:
                osascript('tell application "Google Chrome" to close window 1')
            except Exception:
                pass

    def go(self, url, settle=2.0, tries=40):
        """Navigate and wait until the document is complete and not a Cloudflare interstitial."""
        osascript(f'tell application "Google Chrome" to set URL of active tab of window 1 to "{json_str(url)}"')
        for _ in range(tries):
            time.sleep(settle)
            try:
                state = self.js("document.readyState + '|' + document.title")
            except Exception:
                continue
            if state.startswith("complete") and "Just a moment" not in state:
                return True
        return False

    def js(self, expression):
        """Run one expression in the page and return it as a string."""
        return osascript('tell application "Google Chrome" to return (execute active tab of window 1 '
                         f'javascript "{json_str(expression)}")', timeout=90)

    def json(self, expression):
        """Run an expression that returns an object; JSON.stringify it on the page and parse it here."""
        out = self.js(f"JSON.stringify({expression})")
        return json.loads(out) if out else None


def json_str(s):
    """Escape for embedding inside an AppleScript double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://bnedigital.bne.es/"
    with Chrome(keep="--keep" in sys.argv) as c:
        ok = c.go(url)
        print("loaded" if ok else "did not settle", "|", c.js("document.title"))
        print(c.js("document.body.innerText.slice(0, 400)"))
