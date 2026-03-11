import cv2
import numpy as np
import subprocess
import time
import os

# --- 設定 ---
ADB = r"C:\Users\mahhy\Documents\scrcpy\scrcpy-win64-v3.3.4\adb.exe"
TARGET_BASE = "targets/powl"

def adb_shell(command):
 """ADBコマンドを実行してCompletedProcessを返す。"""
 return subprocess.run(f'"{ADB}" {command}', shell=True, capture_output=True, text=True)

def capture_screen():
 """端末のスクリーンショットを取得してOpenCVで読み込んで返す。"""
 adb_shell("shell screencap -p /sdcard/screen.png")
 adb_shell("pull /sdcard/screen.png .")
 return cv2.imread("screen.png")

# --- デバッグメイン関数 ---
def run_debug_scan():
 """現在の画面に対してTARGET_BASE配下の画像テンプレート群を照合し、結果を視覚化して保存するデバッグ用関数。"""
 print("\n" + "="*50)
 print("🔍 広告監視デバッグスキャンを開始します")
 print("="*50)

 # 現在の画面を取得
 screen = capture_screen()
 if screen is None:
  print("❌ 画面取得失敗。ADB接続を確認してください。")
  return

 # 調査対象の画像リストを作成
 targets = []
 for root, dirs, files in os.walk(TARGET_BASE):
  for file in files:
   if file.endswith((".png", ".jpg")):
    targets.append(os.path.join(root, file))

 # 描画用（debug_result.pngとして保存）
 debug_img = screen.copy()

 print(f"{'ファイル名':<30} | {'一致度':<6} | {'判定'}")
 print("-" * 50)

 for path in targets:
  template = cv2.imread(path)
  if template is None:
   print(f"{os.path.basename(path):<30} | 読み込み失敗")
   continue

  h, w = template.shape[:2]
  res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
  min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

  # 判定結果
  status = "✅ OK" if max_val >= 0.8 else "❌ NG"
  print(f"{os.path.basename(path):<30} | {max_val:.3f} | {status}")

  # マッチ箇所を画像に描画（最も高いスコアの場所）
  color = (0, 255, 0) if max_val >= 0.8 else (0, 0, 255)
  top_left = max_loc
  bottom_right = (top_left[0] + w, top_left[1] + h)
  cv2.rectangle(debug_img, top_left, bottom_right, color, 5)
  cv2.putText(debug_img, f"{os.path.basename(path)} ({max_val:.2f})", 
   (top_left[0], top_left[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

 # 結果を保存
 cv2.imwrite("debug_result.png", debug_img)
 print("-" * 50)
 print("📸 視覚化結果を 'debug_result.png' として保存しました。")
 print("="*50 + "\n")

if __name__ == "__main__":
 # 広告が表示されている状態で実行してください
 while True:
  run_debug_scan()
  time.sleep(2) 