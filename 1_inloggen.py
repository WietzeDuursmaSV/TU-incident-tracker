from __future__ import annotations

# Stap 1: eenmalig handmatig inloggen en de sessie opslaan.
# Installatie: pip install playwright && playwright install chromium
from pathlib import Path

from playwright.sync_api import sync_playwright

LOGIN_URL = "https://soneparprod.service-now.com/now/nav/ui/classic/params/target/incident_list.do%3Fsysparm_query%3Dassignment_group%253De68479bb879d4610b42b40480cbb35c0%255EstateIN1%252C9%252C2%252C3%255EORDERBYpriority%255EGROUPBYassignment_group%26sysparm_first_row%3D1%26sysparm_view%3D"

INJECT_CONTINUE_BUTTON_SCRIPT = """
(() => {
    const attachContinueButton = () => {
        if (document.getElementById('copilot-session-continue')) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.id = 'copilot-session-continue';
        wrapper.style.position = 'fixed';
        wrapper.style.right = '20px';
        wrapper.style.bottom = '20px';
        wrapper.style.zIndex = '2147483647';
        wrapper.style.display = 'flex';
        wrapper.style.flexDirection = 'column';
        wrapper.style.alignItems = 'flex-end';
        wrapper.style.gap = '8px';

        const note = document.createElement('div');
        note.textContent = 'Klik zodra je bent ingelogd.';
        note.style.padding = '8px 12px';
        note.style.background = '#111827';
        note.style.color = '#ffffff';
        note.style.borderRadius = '10px';
        note.style.fontFamily = 'Segoe UI, sans-serif';
        note.style.fontSize = '12px';
        note.style.boxShadow = '0 8px 20px rgba(0,0,0,0.18)';

        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = 'Verbonden, ga verder';
        button.style.padding = '10px 14px';
        button.style.border = '0';
        button.style.borderRadius = '999px';
        button.style.background = '#0f766e';
        button.style.color = '#ffffff';
        button.style.fontFamily = 'Segoe UI, sans-serif';
        button.style.fontSize = '13px';
        button.style.fontWeight = '700';
        button.style.cursor = 'pointer';
        button.style.boxShadow = '0 8px 20px rgba(0,0,0,0.18)';
        button.addEventListener('click', () => {
            window.__copilotSessionReady = true;
        });

        wrapper.appendChild(note);
        wrapper.appendChild(button);
        document.body.appendChild(wrapper);
    };

    window.__copilotSessionReady = false;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachContinueButton, { once: true });
    } else {
        attachContinueButton();
    }

    setInterval(() => {
        try {
            attachContinueButton();
        } catch (error) {
            // negeer tijdelijke navigatiefouten
        }
    }, 1000);
})();
"""


def save_session_state(session_path: str | Path = "sessie.json") -> str:
        with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.add_init_script(INJECT_CONTINUE_BUTTON_SCRIPT)
                page.goto(LOGIN_URL, wait_until="domcontentloaded")
                page.wait_for_function("window.__copilotSessionReady === true", timeout=0)
                context.storage_state(path=str(session_path))
                browser.close()

        return str(session_path)


def is_session_state_valid(session_path: str | Path = "sessie.json") -> bool:
    session_file = Path(session_path)
    if not session_file.exists():
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(session_file))
        page = context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        current_url = page.url.lower()
        page_text = page.locator("body").inner_text(timeout=5000).lower()
        browser.close()

    if "login" in current_url:
        return False

    return "username" not in page_text and "password" not in page_text


if __name__ == "__main__":
        session_path = save_session_state()
        print(f"Sessie opgeslagen in {session_path}")
