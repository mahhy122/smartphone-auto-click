import cv2
import numpy as np
import subprocess
import time
import os
import concurrent.futures
import re

# --- 設定 ---
ADB = r"C:\Users\mahhy\Documents\scrcpy\scrcpy-win64-v3.3.4\adb.exe"
TARGET_BASE = "targets/powl"
POWL_PACKAGE = "co.testee.android"

# ★ デバッグ用：一致度（スコア）をターミナルに表示するかどうか
SHOW_MATCH_SCORE = True

# パスの正規化
def get_path(name):
  """TARGET_BASE からファイルパスを正規化して返す。"""
  return os.path.normpath(os.path.join(TARGET_BASE, name))

GET_PATH = get_path("get-points.png")
START_PATH = get_path("start-advertisement.png")
TICKET_PATH = get_path("start-advertisement-ticket.png")
GO_LOTTERY_PATH = get_path("draw-lottery.png")
START_LOTTERY_PATH = get_path("start-lottery.png")

RESUME_AD_PATH = get_path("tap-advertisement.png")

# =========================================================
# ★ 新規追加：歩数回収用の画像パス
TAB_STEPS_PATH = get_path("tab-steps.png") # 歩数タブアイコン
TAB_MOVE_PATH = get_path("tab-move.png")   # 移動タブアイコン（戻る用）
GET_STEPS_PATH = get_path("get-steps.png") # 歩数のポイント獲得ボタン
TAB_HOME_PATH = get_path("tab-home.png")   # ホームタブアイコン（くじ引き後のリセット用）

# ★ 新規追加：ユーザー指定の「新しいリワード受け取り完了」画像
REWARD_DONE_PATH = get_path("reward-done.png") 
# =========================================================

SKIP_1 = get_path("skip-advertisement-1.png") # ストア飛ぶ系
SKIP_2_LIST = [ # アプリ内系
  get_path("skip-advertisement-2.png"),
  get_path("skip-advertisement-3.png"), 
  get_path("skip-advertisement-4.png"),
  get_path("skip-advertisement-5.png"),
  get_path("skip-advertisement-6.png"),
  get_path("skip-advertisement-7.png"),
  get_path("skip-advertisement-8.png"),
  get_path("skip-advertisement-9.png"),
  get_path("skip-advertisement-10.png"),
  get_path("skip-advertisement-11.png"),
  get_path("skip-advertisement-12.png"),
  get_path("skip-advertisement-13.png"),
  get_path("skip-advertisement-14.png"),
  get_path("skip-advertisement-15.png"),
  get_path("skip-advertisement-16.png"),
  get_path("skip-advertisement-17.png"),
  get_path("skip-advertisement-18.png"),
  get_path("skip-advertisement-19.png"),
  get_path("skip-advertisement-20.png"),
  get_path("skip-advertisement-21.png"),
  get_path("skip-advertisement-22.png"),
  get_path("skip-advertisement-23.png"),
  get_path("skip-advertisement-24.png"),
  get_path("skip-advertisement-25.png"),
  get_path("skip-advertisement-26.png"),
  get_path("skip-advertisement-27.png"),
  get_path("skip-advertisement-28.png"),
]
CLOSE_LIST = [
  get_path("close-advertisement-1.png"),
  get_path("close-advertisement-2.png"),
  get_path("close-advertisement-3.png"),
  get_path("close-advertisement-4.png"),
  get_path("close-advertisement-5.png"),
  get_path("close-advertisement-6.png"),
  get_path("close-advertisement-7.png"),
  get_path("close-advertisement-8.png"),
  get_path("close-advertisement-9.png"),
  get_path("close-advertisement-10.png"),
  get_path("close-advertisement-11.png"),
  get_path("close-advertisement-12.png"),
  get_path("close-advertisement-13.png"),
  get_path("close-advertisement-14.png"),
  get_path("close-advertisement-15.png"),
  get_path("close-advertisement-16.png"),
  get_path("close-advertisement-17.png"),
  get_path("close-advertisement-18.png"),
  get_path("close-advertisement-19.png"),
  get_path("close-advertisement-20.png"),
  get_path("close-advertisement-21.png"),
  get_path("close-advertisement-22.png"),
  get_path("close-advertisement-23.png"),
  get_path("close-advertisement-24.png"),
  get_path("close-advertisement-25.png"),
  get_path("close-advertisement-26.png"),
  get_path("close-advertisement-27.png"),
  get_path("close-advertisement-28.png"),
  get_path("close-advertisement-29.png"),
  get_path("close-advertisement-30.png"),
]
END_PATH = get_path("advertisement-ended.png")

# --- ADB制御（★限界突破：RAWデータ直接転送） ---
def adb_shell(command):
  """ADBコマンドを実行してCompletedProcessを返す。"""
  return subprocess.run(f'"{ADB}" {command}', shell=True, capture_output=True, text=True)

def capture_screen():
  """PNG圧縮をスキップし、生のピクセルデータを直接PCメモリに展開する"""
  process = subprocess.Popen(f'"{ADB}" exec-out screencap', shell=True, stdout=subprocess.PIPE)
  raw_bytes = process.stdout.read()
  
  if not raw_bytes or len(raw_bytes) < 12: 
    return None
    
  width = int.from_bytes(raw_bytes[0:4], 'little')
  height = int.from_bytes(raw_bytes[4:8], 'little')
  expected_size = 12 + width * height * 4
  
  if len(raw_bytes) < expected_size:
    return None
    
  img_arr = np.frombuffer(raw_bytes[12:expected_size], dtype=np.uint8).reshape((height, width, 4))
  img = cv2.cvtColor(img_arr, cv2.COLOR_RGBA2BGR)
  return img

def tap(x, y):
  """指定座標へタップイベントを送るユーティリティ。"""
  adb_shell(f"shell input tap {x} {y}")

def go_back():
  """戻るキーイベントを送信して、アプリを1ステップ戻す。"""
  print("🔄 [Recover] 戻るボタンを送信します。")
  adb_shell("shell input keyevent 4")
  time.sleep(1.5)

def is_powl_active():
  """現在フォアグラウンドがPowlかどうかを判定して返す。"""
  res = adb_shell("shell dumpsys window | findstr mCurrentFocus")
  return POWL_PACKAGE in res.stdout

def launch_powl():
  """PowlアプリをADB経由で起動し、起動完了まで待機する。"""
  print("🚀 Powlを起動します...")
  adb_shell(f"shell monkey -p {POWL_PACKAGE} -c android.intent.category.LAUNCHER 1")
  time.sleep(3)
  print("✅ Powlの起動処理が完了しました。")

# --- 画像認識・クリック（★マルチスレッド並列処理） ---
_TEMPLATE_CACHE = {}

def _match_template_worker(args):
  """テンプレート照合を行い、閾値以上なら座標とスコアを返すワーカー。"""
  screen, template_path, threshold = args
  if template_path not in _TEMPLATE_CACHE:
    if not os.path.exists(template_path): return None
    _TEMPLATE_CACHE[template_path] = cv2.imread(template_path)
    
  template = _TEMPLATE_CACHE[template_path]
  if template is None: return None
  
  res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
  _, max_val, _, max_loc = cv2.minMaxLoc(res)
  
  if SHOW_MATCH_SCORE and max_val >= 0.4:
    print(f"  📊 並列判定: {os.path.basename(template_path)} -> スコア: {max_val:.2f} / 必要: {threshold}")
  
  if max_val >= threshold:
    h, w = template.shape[:2]
    x, y = max_loc[0] + w // 2, max_loc[1] + h // 2
    return (template_path, max_val, x, y)
  return None

def find_and_click(screen, template_path, threshold=0.72):
  """単一テンプレートを検索して見つかればタップする。"""
  res = _match_template_worker((screen, template_path, threshold))
  if res:
    path, max_val, x, y = res
    print(f"✅ 発見: {os.path.basename(path)} ({max_val:.2f}) -> Tap({x}, {y})")
    tap(x, y)
    return True
  return False

def find_and_click_parallel(screen, template_paths, threshold=0.72):
  """複数テンプレートを並列に検索し、最初にヒットしたものをタップしてパスを返す。"""
  if screen is None or not template_paths: return False
  args_list = [(screen, p, threshold) for p in template_paths]
  
  with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = [executor.submit(_match_template_worker, args) for args in args_list]
    for future in concurrent.futures.as_completed(futures):
      res = future.result()
      if res:
        path, max_val, x, y = res
        print(f"✅ 発見(並列): {os.path.basename(path)} ({max_val:.2f}) -> Tap({x}, {y})")
        tap(x, y)
        return path 
  return None

def check_and_resume_paused_ad(screen):
  """一時停止（インストール誘導）を検知し、安全なエリアをタップして再開する"""
  if screen is None or not os.path.exists(RESUME_AD_PATH): return False
  if RESUME_AD_PATH not in _TEMPLATE_CACHE:
    _TEMPLATE_CACHE[RESUME_AD_PATH] = cv2.imread(RESUME_AD_PATH)
  template = _TEMPLATE_CACHE[RESUME_AD_PATH]
  if template is None: return False
  
  res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
  _, max_val, _, max_loc = cv2.minMaxLoc(res)
  
  if max_val >= 0.75:
    print(f"⏸ 広告の一時停止(インストール誘導)を検知！(スコア: {max_val:.2f})")
    sh, sw = screen.shape[:2]
    button_y = max_loc[1] + template.shape[0] // 2
    safe_x = sw // 2
    safe_y = int(sh * 0.25) if button_y > sh // 2 else int(sh * 0.75)
    
    print(f"👉 ストア誘導を防ぐため、安全なエリア({safe_x}, {safe_y})をダブルタップして再開します。")
    adb_shell(f'shell "input tap {safe_x} {safe_y} && sleep 0.2 && input tap {safe_x} {safe_y}"')
    return True
  return False
# --- 広告開始フェーズ ---
def try_start_step_ad():
  """歩数タブ用のポイント獲得（広告開始）を試みる"""
  print("🔍 歩数ポイントのボタンを探しています...")
  
  # ★ 修正：1回で諦めず、最大4回（約6秒間）ボタンの出現を待つ
  for attempt in range(4):
    screen = capture_screen()
    if screen is not None:
      if find_and_click(screen, GET_STEPS_PATH, threshold=0.70):
        print("🎬 1/2: 【歩数】ポイント獲得ボタンをタップ。再生ボタンを待ちます...")
        start_wait = time.time()
        while time.time() - start_wait < 15:
          screen2 = capture_screen()
          
          if find_and_click(screen2, START_PATH, threshold=0.70):
            print("🚀 2/2: 通常の動画再生ボタンをタップ。広告視聴開始。")
            return "STEPS" 
            
          if find_and_click(screen2, TICKET_PATH, threshold=0.70):
            print("🎫 2/2: チケット動画再生ボタンをタップ。チケット広告視聴開始。")
            return "TICKET"
            
          time.sleep(0.2)
        print("❌ 動画再生ボタンが出現しませんでした。")
        return None
        
    # 見つからなかった場合は1.5秒待ってから再撮影（アニメーション待ち）
    time.sleep(1.5)
    
  return None # 4回探しても無ければ「本当に尽きた」と判断

def try_start_ad():
  """広告開始ボタンやチケットを検出して、広告再生を開始する試行。"""
  print("🔍 移動ポイントのボタンを探しています...")
  
  # ★ 修正：1回で諦めず、最大4回（約6秒間）ボタンの出現を待つ
  for attempt in range(4):
    screen = capture_screen()
    if screen is not None:
      # まずは通常のポイント獲得ボタン
      if find_and_click(screen, GET_PATH, threshold=0.70):
        print("🎬 1/2: ポイント獲得ボタンをタップ。再生ボタンを待ちます...")
        start_wait = time.time()
        while time.time() - start_wait < 15:
          screen2 = capture_screen()
          
          if find_and_click(screen2, START_PATH, threshold=0.65):
            print("🚀 2/2: 通常の動画再生ボタンをタップ。広告視聴開始。")
            return "POINTS" 
            
          if find_and_click(screen2, TICKET_PATH, threshold=0.65):
            print("🎫 2/2: チケット動画再生ボタンをタップ。チケット広告視聴開始。")
            return "TICKET"
            
          time.sleep(0.5)
        print("❌ 動画再生ボタンが出現しませんでした。")
        return None

      # 直湧きのチケット広告ボタン
      if find_and_click(screen, TICKET_PATH, threshold=0.65):
        print("🎬 直接チケット広告の再生を開始。")
        return "TICKET" 

    # 見つからなかった場合は1.5秒待ってから再撮影（アニメーション待ち）
    time.sleep(1.5)
    
  return None # 4回探しても無ければ「本当に尽きた」と判断


def draw_lottery():
  """くじ引きを実行し、結果画面または追加の広告を処理する"""
  screen = capture_screen()
  if screen is None: return None 

  # ★ 1. まずは画像認識でボタンの場所（座標）を見つける
  res = _match_template_worker((screen, GO_LOTTERY_PATH, 0.70))
  
  if res:
    path, max_val, x, y = res
    
    # =========================================================
    # ★ 2. 必殺技：見つけたボタンの中心ピクセルの「色」を直接チェック！
    # OpenCVは B, G, R の順番で色データを保持している
    b, g, r = screen[y, x]
    
    # 灰色の時は b, g, r の値がほぼ同じになる。
    # 緑色(アクティブ)の時は、g(緑) が r(赤) や b(青) よりも明らかに大きい。
    # 念のため int() でキャストして計算エラーを防ぐ
    if int(g) > int(r) + 20 and int(g) > int(b) + 20:
      print(f"✅ アクティブ(緑)なくじ引きボタンを発見！(B:{b} G:{g} R:{r}) -> Tap({x}, {y})")
      tap(x, y)
    else:
      print(f"⚠️ くじ引きボタンはありますが、非アクティブ(灰色)です。(B:{b} G:{g} R:{r})")
      print("   これ以上引けないため、ホームへ戻ります。")
      go_back()
      return None
    # =========================================================

    print("🎉 くじ引きボタンをタップしました！演出を待ちます...")
    time.sleep(1.5)
    
    if find_and_click(capture_screen(), START_LOTTERY_PATH, threshold=0.75):
      print("🚀 くじ引き開始！結果を待ちます...")
      time.sleep(6) 
      
      screen_result = capture_screen()
      if screen_result is not None:
        if find_and_click(screen_result, TICKET_PATH, threshold=0.75):
          print("🎬 くじ引き結果画面のチケット広告を発見！再生を開始します。")
          return "LOTTERY_AD" 
          
        if find_and_click_parallel(screen_result, CLOSE_LIST, threshold=0.75):
          print("✨ くじの結果画面を閉じました。")
        else:
          print("⚠️ 結果画面の閉じるボタンが見つかりませんでした。画面外タップで戻ります。")
          go_back()

      return "LOTTERY_DONE" 
      
    else:
      print("⚠️ くじ引きが開始されませんでした。メインスキャンに戻ります。")
      go_back() 
      return None

  return None

# --- 広告監視・終了フェーズ ---
def monitor_and_close():
  """広告終了を監視し、リワード画面に戻るまでスキップ・閉じるボタンを押し続けるメインループ。"""
  print("⏳ [Monitor] 広告の終了を監視中...（リワード画面が出るまで執拗にボタンを狙います）")
  start_time = time.time()
  timeout_duration = 150 
  
  while time.time() - start_time < timeout_duration:
    if not is_powl_active():
      print("⚠️ 外部アプリ（Google Play等）への移行を検知しました。即座に戻ります。")
      go_back()
      continue

    screen = capture_screen()
    if screen is None: 
      time.sleep(0.5)
      continue

    # =========================================================
    # 1. ゴール到達確認（リワード画面や元の画面が見えたら監視完了！）
    for check_path in [END_PATH, REWARD_DONE_PATH, GET_PATH, GET_STEPS_PATH, GO_LOTTERY_PATH, TICKET_PATH]:
      if _match_template_worker((screen, check_path, 0.75)):
        print("✨ アプリへの帰還（リワード画面/メイン画面）を検知！監視ループを終了します。")
        return True
    # =========================================================
        
    # 2. 一時停止の検知と再開
    if check_and_resume_paused_ad(screen):
      print("▶️ 広告の再生を再開しました。監視を継続します...")
      time.sleep(1) 
      start_time = time.time() 
      continue

    # 3. ✖ボタンの検知とタップ
    if find_and_click_parallel(screen, CLOSE_LIST, threshold=0.72):
      print("✨ ✖ボタンをタップしました。次の展開を待機します...")
      time.sleep(0.8)
      start_time = time.time() 
      continue

    # 4. ストア回避用スキップボタンの検知とタップ
    if find_and_click(screen, SKIP_1, threshold=0.70):
      print("➡ スキップ1検出。タップ後、ストア回避のため戻ります...")
      time.sleep(1.0)
      go_back()
      start_time = time.time() 
      continue

    # 5. アプリ内スキップボタンの検知とタップ
    if find_and_click_parallel(screen, SKIP_2_LIST, threshold=0.70):
      print("➡ スキップボタン(アプリ内)をタップしました。引き続き監視します...")
      time.sleep(1.0)
      start_time = time.time() 
      continue
      
    time.sleep(0.3) 
    
  print("✅ 長時間の監視が終了しました（タイムアウト）。これ以上ボタンが出ないため復帰したと判断します。")
  return True


# --- リワード処理（共通ヘルパー） ---
def process_ad_reward(ad_type):
  """広告視聴からリワード受け取りまでを処理する共通ヘルパー関数"""
  print(f"⏳ {ad_type} 広告再生開始！すぐに終了ボタンの監視に入ります。")
  
  while True:
    monitor_and_close() 
    
    print(f"🎁 リワード受け取り画面を待機中... ({ad_type})")
    reward_wait = time.time()
    reward_found = False
    
    while time.time() - reward_wait < 15: 
      screen_reward = capture_screen()
      if screen_reward is None:
        time.sleep(0.2)
        continue

      # =========================================================
      # 1. ボーナスチケットを最優先で確認
      if find_and_click(screen_reward, TICKET_PATH, threshold=0.70):
        print("🎫 ボーナス獲得！チケット広告の再生ボタンをタップしました！")
        print("⏳ 追加のチケット広告の終了を監視します...")
        time.sleep(1)
        monitor_and_close() 
        print("🎁 チケット広告終了。最終リワード画面を待機します...")
        reward_wait = time.time() 
        continue 
        
      # 2. リワード受け取りボタン（ポップアップ）を確認してタップ
      if find_and_click(screen_reward, REWARD_DONE_PATH, threshold=0.75):
        print("✨ 新規リワード受け取り画像(REWARD_DONE_PATH)を検知・タップしました！")
        if ad_type == "LOTTERY":
          go_back() 
        reward_found = True
        break

      if find_and_click(screen_reward, END_PATH, threshold=0.75):
        print("✨ ポイント/くじ/チケット リワード画面(END_PATH)を閉じました！")
        if ad_type == "LOTTERY":
          go_back() 
        reward_found = True
        break

      # 3. 【修正】ポップアップのボタンが無い場合にのみ、元の画面への帰還を検知
      for return_path in [GET_PATH, GET_STEPS_PATH, GO_LOTTERY_PATH]:
        if _match_template_worker((screen_reward, return_path, 0.75)):
          print("✨ 元の画面への帰還を検知しました！リワード処理を終了して次へ進みます。")
          reward_found = True
          break
      if reward_found:
        break
      # =========================================================

      time.sleep(0.5)
      
    if reward_found:
      break 
    else:
      print("⚠️ 15秒待機しましたがリワード画面が見つかりません。再度広告スキャンを開始します...")
      
  print("♻️ 次の操作を準備しています...")
  time.sleep(1)

# --- ★ スマホを強制終了＆スリープさせる機能 ---
def force_stop_and_sleep():
  """現在のアプリを強制終了し、ホームに戻して画面をスリープさせる。"""
  print("\n🛑 終了処理：現在開いているアプリをタスクキルし、画面をオフにします...")
  res = adb_shell("shell dumpsys window | findstr mCurrentFocus")
  
  match = re.search(r'u0 ([a-zA-Z0-9\._]+)/', res.stdout)
  if match:
    package_name = match.group(1)
    print(f"💥 起動中のアプリ ({package_name}) を強制終了しました！")
    adb_shell(f"shell am force-stop {package_name}")
  
  time.sleep(1)
  adb_shell("shell input keyevent 3") 
  
  time.sleep(1)
  adb_shell("shell input keyevent 26") 
  print("🌙 スマホの画面を消灯しました。完璧な状態でおやすみなさい！")


# --- メインループ（完全巡回システム） ---
if __name__ == "__main__":
  print("="*40)
  print("🚀 Powl 限界突破・完全自動化システム 稼働開始（歩数回収対応版）")
  print("="*40)
  
  PROGRAM_START_TIME = time.time()
  RUN_DURATION = 3600*6 
  
  current_task = "MOVE" 
  
  try:
    launch_powl()
    
    while True:
      elapsed_time = time.time() - PROGRAM_START_TIME
      if elapsed_time > RUN_DURATION:
        print(f"\n⏰ 稼働から1時間が経過しました（{elapsed_time/60:.1f}分）。終了します。")
        force_stop_and_sleep()
        break 

      print(f"\n🔍 スキャン中... [現在地: {current_task}] (残り: {(RUN_DURATION - elapsed_time)/60:.1f}分)")
      
      # =========================================================
      # フェーズ1：移動ポイント回収
      # =========================================================
      if current_task == "MOVE":
        ad_type = try_start_ad()
        if ad_type:
          process_ad_reward(ad_type)
          continue
        else:
          print("🔄 移動ポイントが尽きました。「歩数」タブへ移動します。")
          screen = capture_screen()
          if find_and_click(screen, TAB_STEPS_PATH, threshold=0.70):
            time.sleep(2)
          current_task = "STEPS"
          continue

      # =========================================================
      # フェーズ2：歩数ポイント回収
      # =========================================================
      elif current_task == "STEPS":
        ad_type = try_start_step_ad()
        if ad_type:
          process_ad_reward(ad_type)
          continue
        else:
          print("🔄 歩数ポイントが尽きました。「移動(メイン)」タブへ戻ります。")
          screen = capture_screen()
          if find_and_click(screen, TAB_MOVE_PATH, threshold=0.70):
            time.sleep(2)
          current_task = "LOTTERY"
          continue

      # =========================================================
      # フェーズ3：くじ引き
      # =========================================================
      elif current_task == "LOTTERY":
        lottery_status = draw_lottery()
        
        if lottery_status == "LOTTERY_AD":
          process_ad_reward("LOTTERY")
          continue
          
        elif lottery_status == "LOTTERY_DONE":
          print("♻️ くじ引き1回完了。連続して引けるか確認します...")
          time.sleep(2)
          continue
          
        else:
          # ★ くじ終了後にホームタブへ戻る処理
          print("🔍 ポイントもくじ引きも対象がありません。Powlの「ホーム」タブに戻ります...")
          screen = capture_screen()
          if find_and_click(screen, TAB_HOME_PATH, threshold=0.70):
            time.sleep(2)
          
          print("⏳ 画面が更新されるまで待機します...")
          time.sleep(5)
          
          print("🔄 次の周回を開始するため、「移動」タブへ戻ります...")
          screen = capture_screen()
          if find_and_click(screen, TAB_MOVE_PATH, threshold=0.70):
            time.sleep(2)
            
          current_task = "MOVE" 

  except KeyboardInterrupt:
    print("\n⏹ 手動でプログラムを終了しました。お疲れ様でした！")