"""
note.com セッションクッキー保存スクリプト（ローカル実行用）

使い方:
  python save_note_cookies.py

ブラウザが開くので、手動でreCAPTCHAを解いてログインしてください。
ログイン完了後、クッキーが note_cookies.json に保存されます。
"""

import json
from playwright.sync_api import sync_playwright


def main():
    print("=" * 60)
    print("note.com クッキー取得ツール")
    print("=" * 60)
    print()
    print("ブラウザが開きます。")
    print("reCAPTCHAを解いて手動でログインしてください。")
    print("ログイン後、このスクリプトが自動でクッキーを保存します。")
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

        print("note.com ログインページを開いています...")
        page.goto("https://note.com/login")

        print("ログインが完了するまで待機します（最大3分）...")
        print("ブラウザでreCAPTCHAを解いてログインしてください。")

        # ログイン完了を待つ：note.comに戻り、かつログインページでないこと
        try:
            page.wait_for_function(
                """() => {
                    const h = window.location.hostname;
                    const p = window.location.pathname;
                    return h.endsWith('note.com') && !p.startsWith('/login') && !p.startsWith('/signup');
                }""",
                timeout=300000,
            )
        except Exception:
            print("タイムアウトしました。再度実行してください。")
            browser.close()
            return

        print(f"note.comへのログイン検出！ URL: {page.url}")
        # 認証が確実に完了するまで追加で待つ
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        # 認証検証：ログインが必要なページに移動できるかチェック
        print("認証を検証中（/notes/new にアクセス）...")
        page.goto("https://note.com/notes/new", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        if "/login" in page.url:
            print("⚠️  認証検証失敗：/notes/new にアクセスできません。ログインを完全に終わらせてから再実行してください。")
            browser.close()
            return
        print(f"✓ 認証確認OK！ URL: {page.url}")

        # 少し待ってから保存（localStorageが書き込まれるのを待つ）
        page.wait_for_timeout(3000)

        # storage_state（クッキー + localStorage）を保存
        state = context.storage_state()
        with open("note_cookies.json", "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        print()
        print("=" * 60)
        print("クッキーを note_cookies.json に保存しました！")
        print()
        print("次のステップ：")
        print("1. 下記コマンドでGitHub Secretに登録してください：")
        print()
        print("   gh secret set NOTE_COOKIES < note_cookies.json")
        print()
        print("   ※ note_cookies.json の内容をコピーして")
        print("      GitHub → Settings → Secrets → NOTE_COOKIES に貼り付けでもOK")
        print("=" * 60)

        browser.close()


if __name__ == "__main__":
    main()
