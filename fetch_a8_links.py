"""
A8.net 提携プログラム → アフィリエイトリンク自動取得スクリプト

- A8_COOKIES（GitHub Secret or 環境変数）を使ってログイン状態でブラウザを起動
- 「参加中プログラム一覧」をスクレイピング
- 各プログラムの広告リンク取得画面からテキスト広告URL（https://px.a8.net/...）を抽出
- プログラム名から AI / プログラミング / 副業 / 業務効率化 / その他 を Claude で自動分類
- affiliate_links.json として書き出し

使い方:
  ローカル: NOTE_COOKIES等と同じく環境変数 A8_COOKIES を設定して実行
    export A8_COOKIES="$(cat a8_cookies.json)"
    python3 fetch_a8_links.py

  GitHub Actions: secrets.A8_COOKIES を env に渡す
"""

import json
import os
import re
import sys
import time
import anthropic
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

A8_COOKIES_JSON = os.environ.get("A8_COOKIES", "")

# A8 ページ
PARTNER_LIST_URL = "https://pub.a8.net/a8v2/asPartnerProgramListAction.do"
MEMBER_TOP_URL = "https://pub.a8.net/a8v2/asMemberAction.do"

CATEGORIES = ["AI", "プログラミング", "副業", "業務効率化", "その他"]


def classify_program(name: str, description: str = "") -> str:
    """Claudeでプログラム名・説明からカテゴリを判定"""
    client = anthropic.Anthropic()
    prompt = f"""以下のアフィリエイト案件を、必ずカテゴリ一覧から1つだけ選んでください。

案件名: {name}
説明: {description}

カテゴリ一覧: {", ".join(CATEGORIES)}

判断基準：
- AI: ChatGPT、Claude、画像生成AI、AI関連ツール全般
- プログラミング: プログラミングスクール、コーディング関連
- 副業: クラウドソーシング、副業マッチング、ココナラ等
- 業務効率化: SaaS、自動化ツール、生産性ツール
- その他: 上記に当てはまらない全て

出力はカテゴリ名のみ（"AI" など、それ以外の文字は一切不要）。"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}],
        )
        result = next(
            (b.text for b in response.content if b.type == "text"), "その他"
        ).strip()
        # 厳格にカテゴリにマッチさせる
        for cat in CATEGORIES:
            if cat in result:
                return cat
        return "その他"
    except Exception as e:
        print(f"  分類失敗（その他にフォールバック）: {e}")
        return "その他"


def fetch_partner_programs(page) -> list[dict]:
    """参加中プログラム一覧を取得（新旧UI両対応）"""
    # 候補URL（新旧両方）
    candidate_urls = [
        "https://pub.a8.net/a8v2/media/program/joinedProgramList.do",
        "https://pub.a8.net/a8v2/media/program/programList.do",
        "https://pub.a8.net/a8v2/asPartnerProgramListAction.do",
        "https://pub.a8.net/a8v2/media/program/joinList.do",
    ]
    found = False
    for url in candidate_urls:
        print(f"試行: {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(2000)
            if "login" in page.url.lower():
                continue
            # プログラム名らしきリンクが存在するか確認
            test_links = page.query_selector_all('a[href*="programSearchId"], a[href*="asProgramDetailAction"], a[href*="programDetail"]')
            if test_links:
                print(f"  → リンク発見（{len(test_links)}件）、このページを使用")
                found = True
                break
            else:
                print(f"  → リンクなし（ボタン類: {len(page.query_selector_all('a'))}件）")
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    if not found:
        # 最後の手段：メニューから手動ナビゲート
        print("メニュー経由で「参加中プログラム」を探します...")
        try:
            page.goto("https://pub.a8.net/a8v2/media/memberAction.do", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            # 「プログラム管理」メニューをホバー or クリック
            for label in ["プログラム管理", "参加中プログラム", "提携中プログラム"]:
                try:
                    elements = page.query_selector_all(f'a:has-text("{label}"), button:has-text("{label}")')
                    if elements:
                        print(f"  '{label}' リンク発見（{len(elements)}件）")
                        for el in elements:
                            href = el.get_attribute("href")
                            if href:
                                print(f"    href: {href}")
                except Exception:
                    pass
            # デバッグ: ページに含まれる /a8v2/ で始まるパスを全て列挙
            html = page.content()
            paths = set(re.findall(r'/a8v2/[a-zA-Z0-9_/.]+', html))
            print(f"ページ内のa8v2パス一覧（最大30件）:")
            for p in list(paths)[:30]:
                print(f"  {p}")
            page.screenshot(path="a8_no_programs.png")
        except Exception as e:
            print(f"メニュー探索失敗: {e}")
        return []

    programs = []

    # ページネーションが存在する場合に備えて全ページ巡回
    while True:
        # 各プログラム行を抽出
        links = page.query_selector_all(
            'a[href*="programSearchId"], a[href*="asProgramDetailAction"], a[href*="programDetail"]'
        )
        for link in links:
            try:
                name = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                if not name or len(name) < 2 or len(name) > 80:
                    continue
                # プログラムIDをURLから抽出
                m = re.search(r"programSearchId=(\d+)", href)
                pid = m.group(1) if m else None
                if not pid:
                    m2 = re.search(r"[?&]a8mat=([^&]+)", href)
                    if m2:
                        pid = m2.group(1)
                if not pid:
                    m3 = re.search(r"/(\d{8,})", href)
                    if m3:
                        pid = m3.group(1)
                if pid and not any(p["id"] == pid for p in programs):
                    programs.append({"id": pid, "name": name, "detail_href": href})
            except Exception:
                continue

        # 次のページへ
        next_btn = page.query_selector('a:has-text("次へ"), a.pageNext, a[rel="next"]')
        if next_btn:
            try:
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(1500)
            except Exception:
                break
        else:
            break

    print(f"取得プログラム数: {len(programs)}")
    return programs


def fetch_text_link(page, program: dict) -> str | None:
    """プログラムのテキスト広告URLを取得"""
    pid = program["id"]
    # 広告リンク取得ページのフォーマット（複数候補）
    candidates = [
        f"https://pub.a8.net/a8v2/asProgramSearchAction.do?programSearchId={pid}",
        f"https://pub.a8.net/a8v2/asPartnerProgramAction.do?programSearchId={pid}",
        program.get("detail_href", ""),
    ]
    for url in candidates:
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://pub.a8.net" + ("" if url.startswith("/") else "/") + url
        try:
            page.goto(url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(1500)
            # ページ内の textarea/input から px.a8.net リンクを探す
            html = page.content()
            m = re.search(r'(https://px\.a8\.net/svt/ejp\?[^"\'<>\s]+)', html)
            if m:
                return m.group(1)
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    return None


def main():
    if not A8_COOKIES_JSON:
        print("環境変数 A8_COOKIES が設定されていません。")
        print("  export A8_COOKIES=\"$(cat a8_cookies.json)\"")
        sys.exit(1)

    try:
        state = json.loads(A8_COOKIES_JSON)
    except json.JSONDecodeError as e:
        print(f"A8_COOKIES のJSONパースに失敗: {e}")
        sys.exit(1)

    # ローカル実行時は HEADLESS=false で起動可能
    headless = os.environ.get("HEADLESS", "true").lower() != "false"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            storage_state=state,
        )
        page = context.new_page()

        # セッション確認
        page.goto(MEMBER_TOP_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        if "login" in page.url.lower():
            print("⚠️ A8セッション無効。save_a8_cookies.py で再取得してください。")
            page.screenshot(path="a8_session_error.png")
            browser.close()
            sys.exit(1)
        print(f"A8セッション認証成功！ URL: {page.url}")

        # 参加中プログラムを取得
        programs = fetch_partner_programs(page)
        if not programs:
            print("参加中プログラムが取得できませんでした。")
            page.screenshot(path="a8_no_programs.png")
            browser.close()
            sys.exit(1)

        # 各プログラムのテキスト広告URLを取得
        results = {cat: [] for cat in CATEGORIES}
        for i, prog in enumerate(programs, 1):
            print(f"[{i}/{len(programs)}] {prog['name']}")
            url = fetch_text_link(page, prog)
            if not url:
                print("  → リンク取得失敗、スキップ")
                continue
            cat = classify_program(prog["name"])
            print(f"  → カテゴリ: {cat}")
            results[cat].append(
                {
                    "name": prog["name"],
                    "url": url,
                    "description": "",
                }
            )
            # サーバ負荷軽減のため少し待機
            time.sleep(1)

        browser.close()

    # 空カテゴリは削除
    results = {k: v for k, v in results.items() if v}

    # JSON出力
    output_path = os.path.join(os.path.dirname(__file__), "affiliate_links.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in results.values())
    print(f"\n✓ {output_path} に {total} 件のリンクを書き出しました")
    for cat, items in results.items():
        print(f"  {cat}: {len(items)} 件")


if __name__ == "__main__":
    main()
