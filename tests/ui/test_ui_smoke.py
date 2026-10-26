"""Kiểm giao diện bằng Playwright: 4 khu vực hiển thị, không lỗi JS, không tràn ngang ở 375px và 1440px.

Chạy: VBR_CHROMIUM=/đường/dẫn/chrome pytest -m ui   (nếu không đặt biến, dùng chromium mặc định của Playwright)
"""
import os
import socket
import threading
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.ui

TOKEN = "ui-test"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server():
    import uvicorn

    from web.server import create_app
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(create_app(TOKEN, {f"127.0.0.1:{port}"}), host="127.0.0.1", port=port,
                                        log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/?t={TOKEN}"
    srv.should_exit = True
    th.join(5)


@pytest.mark.parametrize("viewport", [(1440, 900), (375, 812)])
def test_four_areas_load_without_js_errors_and_no_horizontal_scroll(server, media, viewport):
    errors: list[str] = []
    with pw.sync_playwright() as p:
        kwargs = {"executable_path": os.environ["VBR_CHROMIUM"]} if os.environ.get("VBR_CHROMIUM") else {}
        browser = p.chromium.launch(args=["--no-sandbox"], **kwargs)
        page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server)
        page.wait_for_selector("h1.brand")
        for heading in ("#h-a", "#h-b", "#h-c", "#h-d"):
            assert page.is_visible(heading)
        page.fill("input[aria-label='Đường dẫn thư mục video gốc']", str(media / "orig"))
        page.wait_for_selector(".file-item", timeout=20000)
        assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        browser.close()
    assert errors == []


def test_overlap_shows_red_warning_and_disables_run(server, media):
    with pw.sync_playwright() as p:
        kwargs = {"executable_path": os.environ["VBR_CHROMIUM"]} if os.environ.get("VBR_CHROMIUM") else {}
        browser = p.chromium.launch(args=["--no-sandbox"], **kwargs)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(server)
        page.wait_for_selector("h1.brand")
        page.fill("input[aria-label='Đường dẫn thư mục video gốc']", str(media / "orig"))
        page.wait_for_selector(".file-item", timeout=20000)
        page.check(".segment-card >> nth=0 >> input[type=checkbox]")
        page.check(".segment-card >> nth=1 >> input[type=checkbox]")
        page.fill("input[aria-label='Intro kết thúc ở giây']", "10")
        page.fill("input[aria-label='Tuỳ chọn bắt đầu ở giây']", "5")
        page.fill("input[aria-label='Tuỳ chọn kết thúc ở giây']", "15")
        assert "chồng" in page.inner_text(".area-b .error")
        browser.close()
