import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
import os
import re

# SSL警告を非表示にする
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定 ---
url = 'https://www.nochuri.co.jp/report/financial/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("レポートを取得中...")

try:
    # セッション作成（リトライ機能付き）
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # ページ取得（SSL検証をスキップ）
    response = session.get(url, headers=headers, timeout=60, verify=False)
    response.encoding = 'utf-8'
    response.raise_for_status()
    
    print("ページの取得に成功しました。")
    
except requests.exceptions.RequestException as e:
    print(f"エラー: ページの取得に失敗しました。")
    print(f"詳細: {e}")
    exit()

# --- HTMLを解析 ---
soup = BeautifulSoup(response.text, 'html.parser')

# レポートの各行（trタグ）を取得（テーブルのbody内）
report_rows = soup.select('.tbl01_body tr')

if not report_rows:
    print("レポート行が見つかりませんでした。")
    print("デバッグ用にHTMLを保存します...")
    with open('debug.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("debug.html を保存しました。")
    exit()

print(f"{len(report_rows)}件のレポート行を検出しました。")

# --- レポート情報を抽出 ---
reports = []
for row in report_rows:
    # 各セル（td）を取得
    cells = row.find_all('td')
    if len(cells) < 8:
        continue
    
    # 1. 発行日（セル0）
    date_text = cells[0].get_text(strip=True)
    pub_date = datetime.now()
    if date_text:
        try:
            # 「2026年08月21日」の形式を解析
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_text)
            if date_match:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                pub_date = datetime(year, month, day)
        except Exception as e:
            print(f"日付の解析に失敗: {date_text}")
    
    # 2. タイトルとリンク（セル1）
    title_tag = cells[1].find('a')
    if not title_tag:
        continue
    
    # ★★★ 修正ポイント1：タイトルからファイルサイズを除去 ★★★
    full_title = title_tag.get_text(strip=True)
    # ファイルサイズ（例：「712.0KB」「1.8MB」）を削除
    # パターン：数字＋.（オプション）＋数字＋KB/MB/GB（末尾にあるもの）
    title = re.sub(r'\s*[\d.]+(KB|MB|GB)\s*$', '', full_title).strip()
    # もしタイトルが空になった場合は、元のタイトルを使う
    if not title:
        title = full_title
    
    link = title_tag.get('href')
    if link and not link.startswith('http'):
        link = 'https://www.nochuri.co.jp' + link
    
    # 3. 編著者（セル2）
    author = cells[2].get_text(strip=True)
    if not author or author == '':
        author = '農林中金総合研究所'
    
    # 4. 媒体名（セル5）
    media = cells[5].get_text(strip=True)
    
    # 5. 説明文を作成
    description = f'{author} のレポート（{pub_date.strftime("%Y/%m/%d")}）'
    if media:
        description += f' [媒体: {media}]'
    
    reports.append({
        'title': title,
        'link': link,
        'pub_date': pub_date,
        'author': author,
        'description': description
    })

print(f"{len(reports)}件のレポートを取得しました。")

if not reports:
    print("レポートが0件のため、RSSを作成しません。")
    exit()

# --- RSSフィードを生成 ---
print("RSSフィードを生成中...")
fg = FeedGenerator()
fg.title('農林中金総合研究所 レポートRSS（経済・金融）')
fg.link(href='https://www.nochuri.co.jp/report/financial/', rel='alternate')
fg.description('農林中金総合研究所が公開する経済・金融分野のレポート更新情報です。')
fg.language('ja')

# 日本時間のタイムゾーン（UTC+9:00）
JST = timezone(timedelta(hours=9))

for report in reports:
    fe = fg.add_entry()
    fe.title(report['title'])
    fe.link(href=report['link'])
    fe.description(report['description'])
    fe.author(name=report['author'])
    
    # タイムゾーン情報（JST）を付与
    pub_date_with_timezone = report['pub_date'].replace(tzinfo=JST)
    fe.pubDate(pub_date_with_timezone)

# RSSファイルとして保存
rss_file = 'nochuri_feed.xml'
fg.rss_file(rss_file, pretty=True)
print(f"完了！ {rss_file} が作成されました。")
print(f"保存場所: {os.path.abspath(rss_file)}")
print(f"取得したレポート数: {len(reports)}件")
