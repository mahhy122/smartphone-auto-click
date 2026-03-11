import cv2
import numpy as np
import subprocess
import time
import os

# --- 設定 ---
ADB = r"C:\Users\mahhy\Documents\scrcpy\scrcpy-win64-v3.3.4\adb.exe"
POWL_PACKAGE = "co.testee.android" # mahhyさんの環境で確認済み

def adb_shell(command):
 """ADBコマンドを実行してCompletedProcessを返す。"""
 return subprocess.run(f'"{ADB}" {command}', shell=True, capture_output=True, text=True)

def get_current_package():
 """現在最前面にいるアプリのパッケージ名を取得"""
 # Windowsのfindstrを使用してフォーカス情報を絞り込む
 res = adb_shell("shell dumpsys window | findstr mCurrentFocus")
 line = res.stdout.strip()
 # 取得例: mCurrentFocus=Window{... co.testee.android/co.testee.android.view...}
 if POWL_PACKAGE in line:
  return POWL_PACKAGE
 # ストア(com.android.vending)やその他
 return "OTHER_APP"

def go_back():
 """戻るキーを送信して前の画面に戻す。テスト用の短い待機を含む。"""
 print("🔄 [Recover] パッケージ不一致を検知。戻るボタンを送信します。")
 adb_shell("shell input keyevent 4")
 time.sleep(2)

# --- スキップ・クローズ監視（強化版） ---
def skip_advertisement_v2():
 """広告監視ループのテスト用実装。

  パッケージの切替を優先して検知・復帰するフローを試験する。
  """
 print("⏳ [Monitor] 広告監視フェーズ...")
 start_time = time.time()
 
 while time.time() - start_time < 60:
  # 1. パッケージチェック（画像認識より先に実行）
  current = get_current_package()
  if current == "OTHER_APP":
   print("⚠️ Googleプレイ等への移行を検知しました。")
   go_back()
   continue # 戻った後の画面を再チェック

  # 2. 画像認識でのクローズ処理
  # (ここに以前の find_and_click などのロジックを入れる)
  # ...
  
  time.sleep(1)

# --- 動作確認用メイン ---
if __name__ == "__main__":
 print("🔍 パッケージ監視テストを開始します（中断はCtrl+C）")
 try:
  while True:
   pkg = get_current_package()
   status = "✅ Powl内" if pkg == POWL_PACKAGE else "❌ 外部アプリ（ストア等）"
   print(f"現在の状態: {status} [{pkg}]")
   
   if pkg == "OTHER_APP":
    go_back()
    
   time.sleep(2)
 except KeyboardInterrupt:
  print("\n⏹ 終了します。")