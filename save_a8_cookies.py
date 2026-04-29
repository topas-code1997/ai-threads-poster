"""
A8.net セッションクッキー保存スクリプト（ローカル実行用）

使い方:
  python3 save_a8_cookies.py

ブラウザが開くので、手動でA8.netにログインしてください。
ログイン完了後、クッキーが a8_cookies.json に保存されます。

その後、以下でGitHub Secretに登録:
  gh secret set A8_COOKIES < a8_cookies.json
"""

import json
from playwright.sync_api import sync_playwright


def main():
    print("=" * 60)
    print("A8.net クッキー取得ツール")
    print("=" * 60)
    print()
    print("ブラウザが開きます。")
    print("A8.netにログインしてください（IDとパスワード入力 → ログイン）。")
    print("ログイン後、自動でセッションを検証してクッキーを保存します。")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 手動操作のため表示モード
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print("A8.net トップページを開いています...")
        page.goto("https://www.a8.net/")

        print("ログインが完了するまで待機します（最大5分）...")
        print("ブラウザでメディアID・パスワードを入力してログインしてください。")

        # ログイン後は pub.a8.net のメンバー画面に遷移する
        # 新旧の管理画面URLパターン両方に対応：
        # - 旧: /a8v2/asMemberAction.do
        # - 新: /a8v2/media/memberAction.do
        try:
            page.wait_for_function(
                """() => {
                    const h = window.location.hostname;
                    const p = window.location.pathname;
                    if (!h.includes('pub.a8.net')) return false;
                    // ログインフォームのページからの遷移を確認
                    return p.includes('memberAction') ||
                           p.includes('Member') ||
                           p.includes('/media/') ||
                           p.includes('/home');
                }""",
                timeout=300000,
            )
        except Exception:
            print("タイムアウトしました。再度実行してください。")
            browser.close()
            return

        print(f"A8.netログイン検出！ URL: {page.url}")
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # 認証検証：管理画面トップにアクセスできるか確認（新旧両方試す）
        print("認証を検証中...")
        verify_urls = [
            "https://pub.a8.net/a8v2/media/memberAction.do",
            "https://pub.a8.net/a8v2/asMemberAction.do",
        ]
        verified = False
        for url in verify_urls:
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                if "login" not in page.url.lower():
                    verified = True
                    print(f"✓ 認証確認OK！ URL: {page.url}")
                    break
            except Exception:
                continue

        if not verified:
            print("⚠️  認証検証失敗：ログイン画面に戻されました。再実行してください。")
            browser.close()
            return

        # storage_state（クッキー + localStorage）を保存
        page.wait_for_timeout(2000)
        state = context.storage_state()
        with open("a8_cookies.json", "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        print()
        print("=" * 60)
        print("クッキーを a8_cookies.json に保存しました！")
        print()
        print("次のステップ：")
        print("  gh secret set A8_COOKIES < a8_cookies.json")
        print("=" * 60)

        browser.close()


if __name__ == "__main__":
    main()
