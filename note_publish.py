"""
note.com 自動投稿スクリプト
Playwrightを使ってnote.comにログインし、記事を自動投稿する

認証方式：
  NOTE_COOKIES 環境変数（JSON）があればクッキー認証（reCAPTCHA回避）
  なければメール/パスワードでログイン（reCAPTCHAが出る場合は失敗）
"""

import os
import sys
import json
import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

NOTE_EMAIL = os.environ.get("NOTE_EMAIL", "")
NOTE_PASSWORD = os.environ.get("NOTE_PASSWORD", "")
NOTE_COOKIES_JSON = os.environ.get("NOTE_COOKIES", "")


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
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        # ① 認証（storage_state優先、なければパスワードログイン）
        context_kwargs = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        used_storage_state = False
        if NOTE_COOKIES_JSON:
            try:
                state = json.loads(NOTE_COOKIES_JSON)
                # 古い形式（クッキーだけの配列）と新形式（storage_state）の両対応
                if isinstance(state, list):
                    print("旧形式のクッキー（配列）を検出しました")
                    # 旧形式の場合は後でadd_cookiesする
                else:
                    print("storage_state（クッキー+localStorage）を検出しました")
                    context_kwargs["storage_state"] = state
                    used_storage_state = True
            except json.JSONDecodeError as e:
                print(f"NOTE_COOKIESのJSONパース失敗: {e}")

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        try:
            if NOTE_COOKIES_JSON and not used_storage_state:
                # 旧形式のクッキー配列をadd_cookies
                try:
                    cookies = json.loads(NOTE_COOKIES_JSON)
                    if isinstance(cookies, list):
                        context.add_cookies(cookies)
                        print(f"{len(cookies)} 件のクッキーを設定しました")
                except Exception as e:
                    print(f"クッキー設定失敗: {e}")

            if NOTE_COOKIES_JSON:
                # セッション確認
                print("セッション確認中...")
                page.goto("https://note.com/notes/new", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                print(f"アクセス後URL: {page.url}")

                if "/login" in page.url:
                    print("セッション無効。パスワードログインに切り替えます...")
                    if not _password_login(page):
                        return False
                else:
                    print("セッション認証成功！")
            else:
                print("NOTE_COOKIES未設定。パスワードログインを試みます...")
                if not _password_login(page):
                    return False

            # ② 記事作成ページへ移動
            print("記事作成ページへ移動中...")
            page.goto("https://note.com/notes/new", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            print(f"現在のURL: {page.url}")

            if "/login" in page.url:
                print("認証されていません。ログインに失敗しています。")
                page.screenshot(path="note_error.png")
                return False

            # ③ タイトル入力
            print(f"タイトルを入力中: {title}")
            title_selector = (
                'textarea[placeholder="記事タイトル"], '
                'div[data-placeholder="タイトルを入力してください"], '
                '.title-input, textarea.title'
            )
            page.wait_for_selector(title_selector, timeout=15000)
            page.click(title_selector)
            page.fill(title_selector, title)
            page.wait_for_timeout(1000)

            # ④ 本文入力
            print("本文を入力中...")
            body_selector = (
                'div[contenteditable="true"].ProseMirror, '
                'div[contenteditable="true"][class*="editor"], '
                '.note-editor div[contenteditable="true"]'
            )
            page.wait_for_selector(body_selector, timeout=15000)
            page.click(body_selector)
            page.wait_for_timeout(500)

            # 本文をJavaScript経由で貼り付け（日本語対応）
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

            # ⑤ 公開ボタンをクリック → /publish/ 設定画面へ遷移
            print("公開ボタンを探しています...")
            publish_btn_selector = (
                'button:has-text("公開に進む"), button:has-text("公開設定"), '
                'button:has-text("公開"), button[class*="publish"]'
            )
            page.wait_for_selector(publish_btn_selector, timeout=15000)
            page.click(publish_btn_selector)
            page.wait_for_load_state("networkidle", timeout=20000)
            # SPA レンダリング完了を待つ
            print("公開設定画面のレンダリング待機中...")
            page.wait_for_timeout(10000)
            print(f"公開設定画面URL: {page.url}")
            page.screenshot(path="note_publish_page.png")

            # ⑥ クリック可能要素を列挙（デバッグ）
            clickables = page.query_selector_all('button, a, [role="button"]')
            print(f"画面上のクリック可能要素数: {len(clickables)}")
            texts = []
            for el in clickables:
                try:
                    text = el.inner_text().strip()
                    if text and len(text) < 30:
                        texts.append(text)
                except Exception:
                    pass
            print(f"要素テキスト一覧: {texts}")

            # ⑦ テキストベースで最終投稿ボタンを探してクリック
            clicked = False
            for label in ["投稿する", "公開する", "今すぐ投稿", "今すぐ公開", "投稿"]:
                try:
                    locator = page.get_by_role("button", name=label).last
                    if locator.count() > 0:
                        print(f"'{label}' ボタンを発見、クリック中...")
                        locator.click(timeout=5000)
                        page.wait_for_load_state("networkidle", timeout=20000)
                        page.wait_for_timeout(5000)
                        clicked = True
                        break
                except Exception as e:
                    print(f"'{label}' (button role) 失敗: {e}")
                # role=button がダメならテキスト直接
                try:
                    locator = page.get_by_text(label, exact=True).last
                    if locator.count() > 0:
                        print(f"'{label}' テキスト要素を発見、クリック中...")
                        locator.click(timeout=5000)
                        page.wait_for_load_state("networkidle", timeout=20000)
                        page.wait_for_timeout(5000)
                        clicked = True
                        break
                except Exception as e:
                    print(f"'{label}' (text) 失敗: {e}")
            if not clicked:
                print("最終投稿ボタンが見つかりませんでした。")
                page.screenshot(path="note_no_final_button.png")
                return False

            # ⑦.5 投稿成功モーダル「記事をシェアしてみましょう」が出れば成功
            print(f"投稿クリック後URL: {page.url}")
            page.wait_for_timeout(5000)
            page.screenshot(path="note_after_publish_click.png")

            page_text = page.inner_text("body")
            success_phrases = [
                "記事をシェア",
                "作品の完成",
                "シェアして",
                "公開しました",
                "公開されました",
                "投稿しました",
                "投稿されました",
                "連続投稿",
                "創作が継続",
            ]
            if any(phrase in page_text for phrase in success_phrases):
                print(f"✓ note投稿成功！（投稿完了モーダルを検出）URL: {page.url}")
                return True

            # 念のため URL 判定もする
            current_url = page.url
            print(f"最終投稿後のURL: {current_url}")
            page.screenshot(path="note_result.png")

            if "/n/" in current_url or "publish/done" in current_url or "published" in current_url:
                print(f"note投稿成功！ URL: {current_url}")
                return True

            print(f"投稿結果が確認できませんでした。URL: {current_url}")
            return False

        except PlaywrightTimeoutError as e:
            print(f"タイムアウトエラー: {e}")
            page.screenshot(path="note_error.png")
            return False
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            try:
                page.screenshot(path="note_error.png")
            except Exception:
                pass
            return False
        finally:
            browser.close()


def _password_login(page) -> bool:
    """メール/パスワードでログインする（reCAPTCHAが出ると失敗する）"""
    if not NOTE_EMAIL or not NOTE_PASSWORD:
        print("NOTE_EMAIL / NOTE_PASSWORD が未設定です。")
        return False

    print("note.comにアクセス中...")
    page.goto("https://note.com/login", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    print("メールアドレスを入力中...")
    email_selector = (
        'input[type="email"], input[placeholder*="mail"], '
        'input[placeholder*="note ID"], input[name="email_or_id"]'
    )
    page.wait_for_selector(email_selector, timeout=15000)
    page.fill(email_selector, NOTE_EMAIL)
    page.wait_for_timeout(500)

    print("パスワードを入力中...")
    page.wait_for_selector('input[type="password"]', timeout=10000)
    page.fill('input[type="password"]', NOTE_PASSWORD)
    page.wait_for_timeout(500)

    print("ログインボタンをクリック...")
    page.click('button:has-text("ログイン"), button[type="submit"]')
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(3000)

    print(f"ログイン後URL: {page.url}")
    page_text = page.inner_text("body")
    if "reCAPTCHA" in page_text or "recaptcha" in page_text.lower():
        print("reCAPTCHAが検出されました。クッキー認証を使用してください。")
        page.screenshot(path="note_captcha.png")
        return False

    if "/login" in page.url:
        print("ログイン失敗。認証情報またはreCAPTCHAを確認してください。")
        page.screenshot(path="note_login_failed.png")
        return False

    print(f"ログイン成功。URL: {page.url}")
    return True


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
