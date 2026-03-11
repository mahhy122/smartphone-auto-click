# ============================================================================
# インポート部
# ============================================================================
import cv2
import numpy as np
import subprocess
import time
import os

# ============================================================================
# モジュール説明
# ============================================================================
"""
スマートフォン自動クリック用スクリプト
"""

# ============================================================================
# 設定・定数部分
# ============================================================================

ADB = os.getenv("ADB_PATH", "adb")
TARGET_BASE = "targets/powl"

GET_PATH = os.getenv("GET_PATH", "targets/powl/get-points.png")
START_PATH = os.getenv("START_PATH", "targets/powl/start-advertisement.png")
SKIP_PATH = os.getenv("SKIP_PATH_", "targets/powl/skip-advertisement-1.png")
CLOSE_PATH_1 = os.getenv("CLOSE_PATH_1", "targets/powl/close-advertisement-1.png")
CLOSE_PATH_2 = os.getenv("CLOSE_PATH_2", "targets/powl/close-advertisement-2.png")
CLOSE_PATH_3 = os.getenv("CLOSE_PATH_3", "targets/powl/close-advertisement-3.png")
START_PATH_TICKET = os.getenv("START_PATH_TICKET", "targets/powl/start-advertisement-ticket.png")

# ============================================================================
# ユーティリティ関数部
# ============================================================================

def adb_shell(command):
 """adbコマンドを実行するヘルパー。CompletedProcessは返さず実行のみ行う。"""
 subprocess.run(f"{ADB} {command}", shell=True)

def capture_screen():
 """端末のスクリーンショットを取得してローカルに保存する。"""
 adb_shell("shell screencap -p /sdcard/screen.png")
 adb_shell("pull /sdcard/screen.png .")

def go_back():
 """戻るキーを送信して前の画面に戻るユーティリティ。"""
 print("⏳ 元のアプリに戻ります...")
 adb_shell("shell input keyevent 4")
 time.sleep(1)
 print("✓ 元のアプリに戻りました。")

# ============================================================================
# テンプレートマッチング関数部
# ============================================================================

def find_and_click(template_path, threshold=0.8):
 """画面を取得してテンプレートマッチングを行い、閾値以上ならタップする。"""
 capture_screen()
 img = cv2.imread("screen.png")
 template = cv2.imread(template_path)
 if img is None or template is None:
  return False
 res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
 _, max_val, _, max_loc = cv2.minMaxLoc(res)
 print(f"[{template_path}] 一致度: {max_val:.2f}")
 if max_val >= threshold:
  h, w = template.shape[:2]
  x = max_loc[0] + w // 2
  y = max_loc[1] + h // 2
  print(f"➡ 発見！ 座標({x}, {y})をタップします。")
  adb_shell(f"shell input tap {x} {y}")
  return True
 return False

# ============================================================================
# タスク関数部
# ============================================================================

def start_advertisement_points():
 """ポイント獲得広告の開始を試行するタスク。

  成功ならTrue、タイムアウトならFalseを返す。
  """
 start_time = time.time()
 while True:
  print("⏳ [ポイント獲得広告] タスク実行中...")
  if find_and_click(GET_PATH):
   print("✓ ポイント獲得の広告をクリックしました。")
   time.sleep(1)
  elif find_and_click(START_PATH):
   print("✓ 広告開始のボタンをクリックしました。")
   time.sleep(2)
   return True
  if (time.time() - start_time) > 15:
   print("✗ ポイント獲得広告タスク失敗")
   return False

def close_advertisement():
 """広告を閉じるための処理を行う。見つかればTrueを返す。"""
 print("⏳ [広告クローズ] タスク実行中...")
 go_back()
 
 if find_and_click(CLOSE_PATH_1) or find_and_click(CLOSE_PATH_2) or find_and_click(CLOSE_PATH_3):
  print("✓ 広告を閉じました。")
  return True
 print("✗ 広告クローズ失敗")
 return False

def skip_advertisement():
 """広告のスキップ処理（閉じる or スキップボタン）を実行する。"""
 print("⏳ [広告スキップ] タスク実行中...")
 if close_advertisement():
  print("✓ 広告を閉じました。")
  time.sleep(1)
  return True
 elif find_and_click(SKIP_PATH):
  print("✓ 広告スキップのボタンをクリックしました。")
  time.sleep(1)
  if close_advertisement():
   print("✓ 広告を閉じました。")
   time.sleep(1)
   return True
 print("✗ 広告スキップタスク失敗")
 return False

def start_advertisement_ticket():
 """チケット広告の開始を試行するタスク。成功ならTrue。"""
 print("⏳ [チケット獲得広告] タスク実行中...")
 if find_and_click(START_PATH_TICKET):
  print("✓ チケット獲得の広告をクリックしました。")
  time.sleep(1)
  return True
 print("✗ チケット獲得広告タスク失敗")
 return False

# ============================================================================
# メインループ部
# ============================================================================
try:
 print("プログラムを開始します。中断は Ctrl+C")
 while True:
  if start_advertisement_points():
   print("✓ [ポイント獲得広告を開く] タスク完了")
   time.sleep(2)
  elif skip_advertisement():
   print("✓ [広告スキップ] タスク完了")
   time.sleep(5)
  elif start_advertisement_ticket():
   print("✓ [チケット獲得広告] タスク完了")
   time.sleep(5)
  else:
   print("✗ [任意タスク] 対象の画像が見つかりませんでした。待機します...")
   time.sleep(3)
except KeyboardInterrupt:
 print("\n⏹ プログラムを終了しました。")