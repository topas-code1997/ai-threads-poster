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


def _classify_by_keyword(name: str) -> str:
    """キーワードベースの簡易分類（APIキー不要のフォールバック）"""
    n = name
    nl = name.lower()
    ai_keywords = [
        "AI", "ai", "ChatGPT", "Claude", "Gemini", "Suno", "Midjourney",
        "Stable Diffusion", "画像生成", "生成AI", "LLM", "プロンプト", "DALL",
    ]
    prog_keywords = [
        "プログラミング", "コーディング", "エンジニア", "プログラマ",
        "Python", "JavaScript", "Web開発", "ITスクール",
    ]
    sidejob_keywords = [
        "副業", "クラウドソーシング", "ココナラ", "ランサーズ", "クラウドワーク",
        "在宅", "スキマ", "Webライター",
    ]
    biz_keywords = [
        "業務", "効率", "自動化", "SaaS", "生産性", "会計", "勤怠",
        "ドメイン", "サーバー", "ホスティング", "CRM",
    ]

    if any(k in n for k in ai_keywords):
        return "AI"
    if any(k in n for k in prog_keywords):
        return "プログラミング"
    if any(k in n for k in sidejob_keywords):
        return "副業"
    if any(k in n for k in biz_keywords):
        return "業務効率化"
    return "その他"


def classify_program(name: str, description: str = "") -> str:
    """Claudeでプログラム名・説明からカテゴリを判定。APIキーが無い場合はキーワード分類"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _classify_by_keyword(name)

    try:
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
        return _classify_by_keyword(name)
    except Exception as e:
        print(f"  分類失敗、キーワード判定に切替: {e}")
        return _classify_by_keyword(name)


def fetch_partner_programs(page) -> list[dict]:
    """参加中プログラム一覧を取得（新管理画面対応）"""
    # 正しい新UIのURL
    candidate_urls = [
        "https://pub.a8.net/a8v2/media/partnerProgramListAction.do?act=search&viewPage=",
        "https://pub.a8.net/a8v2/media/partnerProgramListAction.do",
        "https://pub.a8.net/a8v2/asPartnerProgramListAction.do",
    ]
    found = False
    for url in candidate_urls:
        print(f"試行: {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(3000)
            if "login" in page.url.lower():
                continue
            # 「プログラム名」のラベルがあるか
            html = page.content()
            if "プログラム名" in html and ("広告リンク" in html or "プログラム詳細" in html):
                print(f"  → 参加中プログラム一覧を確認")
                found = True
                break
            else:
                print(f"  → ラベル見つからず")
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
        # JS でDOMを解析して各プログラムを抽出
        # スクリーンショットの構造：プログラム情報のカード/テーブル内に
        # 「プログラム名」ラベル + 値のセル、「広告リンク」緑ボタンが存在
        extracted = page.evaluate(
            """() => {
                const results = [];
                // 「広告リンク」ボタンを起点に、その親要素から「プログラム名」を探す
                const adLinkButtons = Array.from(
                    document.querySelectorAll('a, button')
                ).filter(el => el.innerText.trim().replace(/\\s+/g, '').includes('広告リンク'));

                for (const btn of adLinkButtons) {
                    // この行/カード全体をたどる（最大10階層上まで）
                    let container = btn;
                    let name = '';
                    let advertiser = '';
                    let detailHref = '';
                    for (let depth = 0; depth < 10; depth++) {
                        if (!container || !container.parentElement) break;
                        container = container.parentElement;
                        const text = container.innerText || '';
                        if (text.includes('プログラム名') && text.includes('広告主名')) {
                            // この container が当該プログラムの行
                            // 「プログラム名」の直後の値を取得
                            const m = text.match(/プログラム名\\s*\\n+([^\\n]+)/);
                            if (m) name = m[1].trim();
                            const m2 = text.match(/広告主名\\s*\\n+([^\\n]+)/);
                            if (m2) advertiser = m2[1].trim();
                            // 「プログラム詳細」リンクのhrefを取得
                            const detailLink = container.querySelector('a[href*="insId="]');
                            if (detailLink) {
                                detailHref = detailLink.getAttribute('href') || '';
                            }
                            break;
                        }
                    }
                    // 「広告リンク」ボタンのhrefも取得（クリック先）
                    const adHref = btn.getAttribute('href') || '';
                    if (name) {
                        results.push({
                            name: name,
                            advertiser: advertiser,
                            detailHref: detailHref,
                            adLinkHref: adHref,
                        });
                    }
                }
                return results;
            }"""
        )

        for item in extracted or []:
            name = (item.get("name") or "").strip()
            detail_href = item.get("detailHref") or ""
            ad_link_href = item.get("adLinkHref") or ""
            advertiser = item.get("advertiser") or ""

            # insId を抽出
            pid = None
            for href in (detail_href, ad_link_href):
                m = re.search(r"insId=([\w]+)", href)
                if m:
                    pid = m.group(1)
                    break
            if not pid:
                # ad_link_href から program_id 等を抽出
                m = re.search(r"(?:program|ad)Id=([\w]+)", ad_link_href)
                if m:
                    pid = m.group(1)
            if not pid:
                pid = f"unknown_{len(programs)}"

            if name and not any(p["id"] == pid for p in programs):
                programs.append(
                    {
                        "id": pid,
                        "name": name,
                        "advertiser": advertiser,
                        "detail_href": detail_href,
                        "ad_link_href": ad_link_href,
                    }
                )
                print(f"  ✓ {name} (insId={pid})")

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


def _extract_px_a8_url(page) -> str | None:
    """ページ内のHTMLとtextareaから px.a8.net のURLを抽出"""
    html = page.content()
    m = re.search(r'(https://px\.a8\.net/svt/ejp\?[^"\'<>\s]+)', html)
    if m:
        return m.group(1)
    try:
        textareas = page.query_selector_all("textarea")
        for ta in textareas:
            val = ta.input_value() or ""
            m2 = re.search(r'(https://px\.a8\.net/svt/ejp\?[^"\'<>\s]+)', val)
            if m2:
                return m2.group(1)
    except Exception:
        pass
    return None


def fetch_text_link(page, program: dict) -> str | None:
    """プログラムのテキスト広告URLを取得"""
    ad_link_href = program.get("ad_link_href", "")
    detail_href = program.get("detail_href", "")
    pid = program["id"]

    # まず「広告リンク」ボタンのhrefに直接遷移
    candidates = []
    for href in (ad_link_href, detail_href):
        if href:
            full = href if href.startswith("http") else "https://pub.a8.net" + ("" if href.startswith("/") else "/") + href
            candidates.append(full)
    # 既知のURLパターンも試す
    candidates.extend(
        [
            f"https://pub.a8.net/a8v2/media/asGetTextAction.do?insId={pid}",
            f"https://pub.a8.net/a8v2/media/asGetTextLinkAction.do?insId={pid}",
            f"https://pub.a8.net/a8v2/media/asAdLinkSelectAction.do?insId={pid}",
        ]
    )

    for url in candidates:
        try:
            page.goto(url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(2500)
            # px.a8.net のテキスト広告URLを探す
            found = _extract_px_a8_url(page)
            if found:
                return found
            # 「テキスト」タブ/ボタンをクリック
            for label in ["テキスト", "テキスト広告", "シンプル"]:
                try:
                    btn = page.query_selector(f'a:has-text("{label}"), button:has-text("{label}")')
                    if btn:
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        page.wait_for_timeout(2000)
                        found2 = _extract_px_a8_url(page)
                        if found2:
                            return found2
                except Exception:
                    continue
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
            print(f"[{i}/{len(programs)}] {prog['name']} (insId={prog['id']})")
            url = fetch_text_link(page, prog)
            if not url:
                # 1件目だけ詳細ページのスクリーンショット & タイトル表示
                if i == 1:
                    print(f"  詳細ページ最終URL: {page.url}")
                    print(f"  ページタイトル: {page.title()}")
                    page.screenshot(path=f"a8_program_detail_{prog['id']}.png")
                    print(f"  → スクリーンショット: a8_program_detail_{prog['id']}.png")
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
