"""
note.com 自動投稿スクリプト
Playwrightを使ってnote.comにログインし、記事を自動投稿する
"""

import os
import sys
import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

NOTE_EMAIL = os.environ["NOTE_EMAIL"]
NOTE_PASSWORD = os.environ["NOTE_PASSWORD"]


def extract_title(article: str) -> tuple[str, str]:
    """記事の先頭行をタイトルとして抽出し、本文と分離する"""
    lines = article.strip().splitlines()
    title_line = lines[0].lstrip("# ").strip() if lines else "AIトレンド解説"
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else article.strip()
    # タイトルが長すぎる場合は切り詰める
    if len(title_line) > 60:
        title_line = title_line[:57] + "..."
    return title_line, body


def post_to_note(title: str, body: str) -> bool:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
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

        try:
            # ① ログイン
            print("note.comにアクセス中...")
            page.goto("https://note.com/login", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            print("メールアドレスを入力中...")
            email_selector = 'input[type="email"], input[placeholder*="mail"], input[placeholder*="note ID"], input[name="email_or_id"]'
            page.wait_for_selector(email_selector, timeout=15000)
            page.fill(email_selector, NOTE_EMAIL)
            page.wait_for_timeout(500)

            print("パスワードを入力中...")
            password_selector = 'input[type="password"]'
            page.wait_for_selector(password_selector, timeout=10000)
            page.fill(password_selector, NOTE_PASSWORD)
            page.wait_for_timeout(500)

            print("ログインボタンをクリック...")
            login_btn_selector = 'button:has-text("ログイン"), button[type="submit"]'
            page.click(login_btn_selector)
            page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_timeout(2000)

            # ログイン確認
            if "login" in page.url:
                print("ログイン失敗。メールアドレスまたはパスワードを確認してください。")
                return False
            print(f"ログイン成功。現在のURL: {page.url}")

            # ② 記事作成ページへ移動
            print("記事作成ページへ移動中...")
            page.goto("https://note.com/notes/new", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # ③ タイトル入力
            print(f"タイトルを入力中: {title}")
            title_selector = 'textarea[placeholder="記事タイトル"], div[data-placeholder="タイトルを入力してください"], .title-input, textarea.title'
            page.wait_for_selector(title_selector, timeout=15000)
            page.click(title_selector)
            page.fill(title_selector, title)
            page.wait_for_timeout(1000)

            # ④ 本文入力
            print("本文を入力中...")
            body_selector = 'div[contenteditable="true"].ProseMirror, div[contenteditable="true"][class*="editor"], .note-editor div[contenteditable="true"]'
            page.wait_for_selector(body_selector, timeout=15000)
            page.click(body_selector)
            page.wait_for_timeout(500)

            # 本文をクリップボード経由で貼り付け（日本語対応）
            page.evaluate(
                """(text) => {
                    const el = document.querySelector(
                        'div[contenteditable="true"].ProseMirror, div[contenteditable="true"][class*="editor"]'
                    );
                    if (el) {
                        el.focus();
                        document.execCommand('insertText', false, text);
                    }
                }""",
                body,
            )
            page.wait_for_timeout(2000)

            # ⑤ 公開ボタンをクリック
            print("公開ボタンを探しています...")
            publish_btn_selector = 'button:has-text("公開"), button:has-text("投稿"), button[class*="publish"]'
            page.wait_for_selector(publish_btn_selector, timeout=15000)
            page.click(publish_btn_selector)
            page.wait_for_timeout(2000)

            # ⑥ 公開確認ダイアログの「公開する」ボタン
            confirm_selector = 'button:has-text("公開する"), button:has-text("投稿する")'
            try:
                page.wait_for_selector(confirm_selector, timeout=8000)
                page.click(confirm_selector)
                page.wait_for_load_state("networkidle", timeout=20000)
                page.wait_for_timeout(3000)
            except PlaywrightTimeoutError:
                print("確認ダイアログが見つからなかったため、そのまま続行...")

            # ⑦ 公開完了確認
            current_url = page.url
            print(f"投稿後のURL: {current_url}")

            if "/n/" in current_url or "note.com" in current_url:
                print(f"note投稿成功！ URL: {current_url}")
                return True
            else:
                print(f"投稿結果が不明です。URL: {current_url}")
                # スクリーンショットを保存（デバッグ用）
                page.screenshot(path="note_result.png")
                return False

        except PlaywrightTimeoutError as e:
            print(f"タイムアウトエラー: {e}")
            page.screenshot(path="note_error.png")
            return False
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            page.screenshot(path="note_error.png")
            return False
        finally:
            browser.close()


def main():
    # note_post.py が生成した記事ファイルを読み込む
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    article_files = [
        f"note_article_{today_str}_1.md",
        f"note_article_{today_str}.md",
    ]

    article_path = None
    for f in article_files:
        if os.path.exists(f):
            article_path = f
            break

    if not article_path:
        print(f"記事ファイルが見つかりません: {article_files}")
        print("先に note_post.py を実行して記事を生成してください。")
        sys.exit(1)

    print(f"記事ファイルを読み込み中: {article_path}")
    with open(article_path, encoding="utf-8") as f:
        article = f.read()

    title, body = extract_title(article)
    print(f"タイトル: {title}")
    print(f"本文文字数: {len(body)}文字")

    success = post_to_note(title, body)
    if not success:
        print("noteへの投稿に失敗しました。")
        sys.exit(1)


if __name__ == "__main__":
    main()
