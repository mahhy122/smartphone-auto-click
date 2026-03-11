import cv2
import numpy as np
import subprocess
import time
import os
import copy
import concurrent.futures
import re

# =========================================================
# 1. 設定・定数・パス (Settings & Constants)
# =========================================================
ADB = r"C:\Users\mahhy\Documents\scrcpy\scrcpy-win64-v3.3.4\adb.exe"
TEMPLATE_DIR = "targets/torima-sudoku/digits"
TARGET_BASE = "targets/torima-sudoku/template"
DEBUG_DIR = "debug_cells"

SHOW_MATCH_SCORE = True 
TORIMA_PACKAGE = "jp.geot.trinumpl"

# 座標設定
NUMBER_BUTTONS = {
  1: (108, 2000), 2: (216, 2000), 3: (324, 2000),
  4: (432, 2000), 5: (540, 2000), 6: (648, 2000),
  7: (756, 2000), 8: (864, 2000), 9: (972, 2000),
}
CONTINUOUS_BTN = (300, 2100)

def get_path(name):
  return os.path.normpath(os.path.join(TARGET_BASE, name))

# 画像リストを内包表記でスッキリ記述
SKIP_1 = get_path("skip-advertisement-1.png")
SKIP_2_LIST = [get_path(f"skip-advertisement-{i}.png") for i in range(2, 28)]
CLOSE_LIST = [get_path(f"close-advertisement-{i}.png") for i in range(1, 28)]

# 各種UI・エフェクトのパス
END_PATH = get_path("advertisement-ended.png")
GEM_EFFECT_PATH = get_path("gem-effect-4.png")
DRAW_GACHA_PATH = get_path("draw-gacha.png")
CLOSE_GACHA_RESULT_PATH = get_path("close-gacha-result.png")
NEXT_PUZZLE_PATH = get_path("next-puzzle.png")
SUDOKU_MARKER_PATH = get_path("sudoku-marker.png")


# =========================================================
# 2. デバイス制御・ADB系 (Device Control)
# =========================================================
def adb_shell(command):
  return subprocess.run(f'"{ADB}" {command}', shell=True, capture_output=True, text=True)

def capture_screen():
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
  return cv2.cvtColor(img_arr, cv2.COLOR_RGBA2BGR)

def tap(x, y):
  adb_shell(f"shell input tap {x} {y}")

def tap_double(x1, y1, x2, y2):
  adb_shell(f'shell "input tap {x1} {y1} && sleep 0.1 && input tap {x2} {y2}"')

def go_back():
  print("🔄 [Recover] 戻るボタンを送信します。")
  adb_shell("shell input keyevent 4")
  time.sleep(0.2)

def force_stop_and_sleep():
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

def get_current_package():
  res = adb_shell('shell "dumpsys window | grep mCurrentFocus"')
  match = re.search(r'u0 ([a-zA-Z0-9\._]+)/', res.stdout)
  if match: return match.group(1)
  return ""


# =========================================================
# 3. 画像認識・テンプレート照合系 (Computer Vision)
# =========================================================
_TEMPLATE_CACHE = {}

def _match_template_worker(args):
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

def find_and_click(screen, template_path, threshold=0.6):
  res = _match_template_worker((screen, template_path, threshold))
  if res:
    path, max_val, x, y = res
    print(f"✅ 発見: {os.path.basename(path)} ({max_val:.2f}) -> Tap({x}, {y})")
    tap(x, y)
    return True
  return False

def find_and_click_parallel(screen, template_paths, threshold=0.6):
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

def is_continuous_mode_active(screen, btn_coords):
  """HSV色空間を利用し、指定座標付近が黄色（連続入力ON）か判定する"""
  if screen is None: return False
  x, y = btn_coords
  half_size = 10
  h, w = screen.shape[:2]
  y1, y2 = max(0, int(y) - half_size), min(h, int(y) + half_size)
  x1, x2 = max(0, int(x) - half_size), min(w, int(x) + half_size)
  
  roi = screen[y1:y2, x1:x2]
  if roi.size == 0: return False
  
  hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
  
  # 画像の鮮やかな黄色に完全にフォーカスしたしきい値
  # H(色相): 20〜40 (黄色)
  # S(彩度): 150〜255 (白っぽさを排除)
  # V(明度): 150〜255 (暗がりを排除)
  lower_yellow = np.array([20, 150, 150])
  upper_yellow = np.array([40, 255, 255])
  
  mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
  yellow_ratio = cv2.countNonZero(mask) / (roi.shape[0] * roi.shape[1])
  
  # 領域内の黄色ピクセルが30%以上ならONとみなす
  return yellow_ratio > 0.3

# =========================================================
# 4. ナンプレ画像処理系 (Sudoku Image Processing)
# =========================================================
_DIGIT_TEMPLATES = None

def load_templates():
  global _DIGIT_TEMPLATES
  if _DIGIT_TEMPLATES is not None: return _DIGIT_TEMPLATES
  templates = {}
  for i in range(1, 10):
    path = os.path.join(TEMPLATE_DIR, f"{i}.png")
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is not None:
      _, thresh = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
      processed = extract_digit_bbox(thresh)
      if processed is not None:
        templates[i] = processed
  _DIGIT_TEMPLATES = templates
  return templates

def extract_digit_bbox(img):
  coords = cv2.findNonZero(img)
  if coords is None: return None
  x, y, w, h = cv2.boundingRect(coords)
  if w < 2 or h < 5: return None
  return cv2.resize(img[y:y+h, x:x+w], (24, 24))

def crop_sudoku_board(img):
  gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  blur = cv2.GaussianBlur(gray, (5, 5), 0)
  thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
  contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
  max_area = 0
  best_rect = None
  for cnt in contours:
    area = cv2.contourArea(cnt)
    if area > 50000:
      x, y, w, h = cv2.boundingRect(cnt)
      aspect_ratio = float(w) / h
      if 0.8 <= aspect_ratio <= 1.2 and area > max_area:
        max_area, best_rect = area, (x, y, w, h)
  if best_rect is None: return None, None
  x, y, w, h = best_rect
  margin_x, margin_y = int(w * 0.01), int(h * 0.01)
  return img[y + margin_y : y + h - margin_y, x + margin_x : x + w - margin_x], (x, y, w, h)

def read_sudoku_with_template(cropped_img, templates):
  gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
  cell_h, cell_w = gray.shape[0] // 9, gray.shape[1] // 9
  sudoku_board = []
  os.makedirs(DEBUG_DIR, exist_ok=True) 

  for row_idx in range(9):
    row_data = []
    for col_idx in range(9):
      cell = gray[row_idx*cell_h : (row_idx+1)*cell_h, col_idx*cell_w : (col_idx+1)*cell_w]
      my, mx = int(cell_h * 0.15), int(cell_w * 0.15)
      _, thresh = cv2.threshold(cell[my : cell_h - my, mx : cell_w - mx], 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
      digit_roi = extract_digit_bbox(thresh)

      if digit_roi is None:
        row_data.append("○")
      else:
        best_match, best_score = "○", 0.0
        for digit, temp_img in templates.items():
          _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(digit_roi, temp_img, cv2.TM_CCOEFF_NORMED))
          if max_val > best_score:
            best_score, best_match = max_val, digit
        if 0.5 < best_score <= 0.7:
          print(f"⚠️ 警告: マス[{row_idx},{col_idx}]の判定({best_match})はスコアが低いです({best_score:.2f})")
        row_data.append(best_match if best_score > 0.7 else "○")
    sudoku_board.append(row_data)
  return sudoku_board

def get_cell_coords(board_rect, row, col):
  bx, by, bw, bh = board_rect
  return int(bx + (col * bw / 9) + (bw / 18)), int(by + (row * bh / 9) + (bh / 18))


# =========================================================
# 5. ナンプレ解答AI (Sudoku Solver)
# =========================================================
def is_initial_board_valid(board):
  for i in range(9):
    row_nums = [n for n in board[i] if n != "○"]
    col_nums = [board[j][i] for j in range(9) if board[j][i] != "○"]
    if len(row_nums) != len(set(row_nums)) or len(col_nums) != len(set(col_nums)): return False
  for box_r in range(3):
    for box_c in range(3):
      box_nums = [board[box_r*3 + i][box_c*3 + j] for i in range(3) for j in range(3) if board[box_r*3 + i][box_c*3 + j] != "○"]
      if len(box_nums) != len(set(box_nums)): return False
  return True

def is_valid(board, row, col, num):
  for i in range(9):
    if board[row][i] == num or board[i][col] == num: return False
  start_row, start_col = (row // 3) * 3, (col // 3) * 3
  for i in range(3):
    for j in range(3):
      if board[start_row + i][start_col + j] == num: return False
  return True

def solve_sudoku(board):
  for row in range(9):
    for col in range(9):
      if board[row][col] == "○":
        for num in range(1, 10):
          if is_valid(board, row, col, num):
            board[row][col] = num
            if solve_sudoku(board): return True
            board[row][col] = "○"
        return False
  return True


# =========================================================
# 6. アプリ操作・進行・広告監視 (Game Logic & Ads)
# =========================================================
def check_store_and_recover():
  current_app = get_current_package()
  if not current_app or TORIMA_PACKAGE in current_app: return False
  print(f"⚠️ トリマ以外のアプリ（{current_app}）への遷移を検知！バツ探しを中断して即座に戻ります。")
  go_back()
  time.sleep(1) 
  return True

def monitor_and_close(check_board=True):
  print("⏳ [Monitor] 広告終了を監視中...")
  start_time, timeout_duration = time.time(), 250
  
  while time.time() - start_time < timeout_duration:
    if check_store_and_recover(): continue
    screen = capture_screen()
    if screen is None: 
      time.sleep(0.1); continue

    if find_and_click(screen, END_PATH, threshold=0.75):
      print("✨ リワード画面(END_PATH)を閉じました！ナンプレに戻ります。")
      time.sleep(1); return True

    for check_path in [DRAW_GACHA_PATH, NEXT_PUZZLE_PATH]:
      if _match_template_worker((screen, check_path, 0.75)):
        print("✨ アプリへの帰還（ガチャ/次の問題）を検知！待機をキャンセルして次へ進みます。")
        time.sleep(0.4); return True

    if find_and_click_parallel(screen, CLOSE_LIST, threshold=0.74):
      print("✨ ✖ボタンをタップしました。次の画面を待機します...")
      start_time, timeout_duration = time.time(), 50
      time.sleep(0.2); continue

    if find_and_click_parallel(screen, SKIP_2_LIST, threshold=0.74):
      print("➡ スキップボタン(アプリ内)をタップしました。タイマーを延長して監視を継続します...")
      start_time, timeout_duration = time.time(), 40
      time.sleep(0.2); continue

    if find_and_click(screen, SKIP_1, threshold=0.75):
      print("➡ スキップ1検出。タップ後、ストア回避のため戻ります...")
      time.sleep(0.7); go_back(); continue

    if check_board and _match_template_worker((screen, SUDOKU_MARKER_PATH, 0.80)):
      board_img, _ = crop_sudoku_board(screen)
      if board_img is not None:
        temp_board = read_sudoku_with_template(board_img, load_templates())
        if sum(1 for row in temp_board for cell in row if cell != "○") >= 15:
          print(f"👀 盤面らしきものを検知。ラグ対策のため3秒待機します...")
          time.sleep(3.0)
          screen2 = capture_screen()
          if screen2 is not None:
            if find_and_click(screen2, END_PATH, threshold=0.75):
              print("✨ 待機中にリワード画面が出現しました！閉じて戻ります。")
              time.sleep(1); return True
            if _match_template_worker((screen2, SUDOKU_MARKER_PATH, 0.80)):
              board_img2, _ = crop_sudoku_board(screen2)
              if board_img2 is not None:
                temp_board2 = read_sudoku_with_template(board_img2, load_templates())
                if sum(1 for row in temp_board2 for cell in row if cell != "○") >= 15:
                  print("✨ 3秒後も本物のナンプレ盤面を確認！広告監視を終了します。")
                  return True
          print("⚠️ 再確認で盤面が消えました。監視を継続します。")
          continue
    time.sleep(1.2)
  print("✅ 監視終了（これ以上ボタンが出ないため、復帰したと判断します）")
  return True

def scan_for_gem(attempts=1): 
  time.sleep(0.01) 
  os.makedirs("debug_gems", exist_ok=True) 
  last_screen = None
  
  for _ in range(attempts):
    screen = capture_screen()
    if screen is None: continue
    last_screen = screen
    if GEM_EFFECT_PATH not in _TEMPLATE_CACHE:
      _TEMPLATE_CACHE[GEM_EFFECT_PATH] = cv2.imread(GEM_EFFECT_PATH) if os.path.exists(GEM_EFFECT_PATH) else None
    template = _TEMPLATE_CACHE[GEM_EFFECT_PATH]
    if template is not None:
      _, max_val, _, _ = cv2.minMaxLoc(cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED))
      filename = f"debug_gems/gem_score.png"
      cv2.imwrite(filename, screen)
      if max_val >= 0.6:
        print(f"💎 緑のジェムエフェクトを完璧に検知！(スコア: {max_val:.2f}) -> {filename} に保存")
        return True, None
  return False, last_screen

def handle_post_sudoku_flow():
  print("🎉 ナンプレクリア！リザルト処理を開始します。")
  time.sleep(1.5) 
  print("⚠️ 1つ目の広告（クリア後広告）の処理に移行します。")
  monitor_and_close(check_board=False)

  print("🎁 『ガチャを引く』ボタンを探しています...")
  tapped_gacha = False
  wait_start = time.time()
  while time.time() - wait_start < 8:
    screen = capture_screen()
    if screen is not None and find_and_click(screen, DRAW_GACHA_PATH, threshold=0.75):
      print("🎯 『ガチャを引く』をタップしました！")
      tapped_gacha = True
      break
    time.sleep(0.2)

  if tapped_gacha:
    print("⚠️ 2つ目の広告（ガチャ広告）の処理に移行します。")
    time.sleep(0.2) 
    monitor_and_close(check_board=False)
    print("⏩ ガチャ結果画面の ✖閉じるボタン を待機中...")
    wait_start = time.time()
    while time.time() - wait_start < 10:
      screen = capture_screen()
      if screen is not None and find_and_click(screen, CLOSE_GACHA_RESULT_PATH, threshold=0.75):
        print("✨ ガチャ結果を閉じました！")
        break
      time.sleep(0.2)

  print("➡ 『次の問題へ』ボタンを探します...")
  time.sleep(0.7)
  wait_start = time.time()
  while time.time() - wait_start < 10:
    screen = capture_screen()
    if screen is not None and find_and_click(screen, NEXT_PUZZLE_PATH, threshold=0.75):
      print("🚀 『次の問題へ』をタップしました！新しい盤面へ進みます。")
      monitor_and_close(check_board=True)
      time.sleep(0.5); return True
    time.sleep(0.5)
  print("⚠️ 『次の問題へ』が見つかりませんでした。")
  return False

def input_sudoku_answers(board_rect, original_board, solved_board):
  print("🚀 連続入力モードで入力を開始します...")
  cx_c, cy_c = CONTINUOUS_BTN
  
  # 色判定によるモードチェック
  screen = capture_screen()
  if not is_continuous_mode_active(screen, CONTINUOUS_BTN):
    print("🔘 連続入力モードをONにします")
    tap(cx_c, cy_c)
    time.sleep(0.5)
  else:
    print("✅ 連続入力モードは既にONです")
  
  for target_num in range(1, 10):
    cells_to_tap = [(r, c) for r in range(9) for c in range(9) if original_board[r][c] == "○" and solved_board[r][c] == target_num]
    if not cells_to_tap: continue 
      
    nx, ny = NUMBER_BUTTONS[target_num]
    tap(nx, ny)
    time.sleep(0.3)
    
    for row, col in cells_to_tap:
      cx, cy = get_cell_coords(board_rect, row, col)
      tap(cx, cy)
      time.sleep(0.1) 
      
      gem_found, _ = scan_for_gem(attempts=1) 
      if gem_found:
        time.sleep(2) 
        print("⚠️ 広告処理に移行します。")
        monitor_and_close(check_board=True)
        print("▶️ ナンプレの入力を再開します。連続入力モードを復旧します...")
        time.sleep(1.0)
        
        recovery_screen = capture_screen()
        if not is_continuous_mode_active(recovery_screen, CONTINUOUS_BTN):
          print("🔄 連続入力が解除されていたため再設定します")
          tap(cx_c, cy_c)
          time.sleep(0.5)
          
        tap(nx, ny)
        time.sleep(0.5)

  print("✨ 一通りの入力が完了しました。入力漏れがないか確認します...")
  
  for retry in range(3):
    time.sleep(2.5) 
    screen = capture_screen()
    if screen is None: continue
    
    board_img, _ = crop_sudoku_board(screen)
    if board_img is None:
      print("🎉 盤面が消えました（クリア画面へ移行）。入力漏れはありません！")
      break
      
    current_board = read_sudoku_with_template(board_img, load_templates())
    missing_inputs = [(r, c, solved_board[r][c]) for r in range(9) for c in range(9) if solved_board[r][c] != "○" and current_board[r][c] == "○"]
          
    if not missing_inputs:
      print("✅ 盤面は残っていますが、空きマスは見当たりません。クリア処理を待ちます...")
      break
      
    if len(missing_inputs) > 10:
      print(f"🎉 盤面から大量の空きマス（{len(missing_inputs)}箇所）を検知しました！演出と判断しスキップします。")
      break
      
    print(f"🔍 タップ抜けを {len(missing_inputs)} 箇所検知しました！即座に補修します（リトライ {retry+1}/3）")
    
    check_screen = capture_screen()
    if not is_continuous_mode_active(check_screen, CONTINUOUS_BTN):
      tap(cx_c, cy_c)
      time.sleep(0.5)
      
    for row, col, ans_num in missing_inputs:
      nx, ny = NUMBER_BUTTONS[ans_num]
      tap(nx, ny)
      time.sleep(0.2)
      cx, cy = get_cell_coords(board_rect, row, col)
      tap(cx, cy) 
      time.sleep(0.5) 
  print("✨ すべての入力処理が完了しました！")

def display_board(board, title="Sudoku Board"):
  print(f"\n=== {title} ===")
  for i in range(9):
    if i % 3 == 0 and i != 0: print("-" * 21)
    row_str = ""
    for j in range(9):
      if j % 3 == 0 and j != 0: row_str += "| "
      row_str += str(board[i][j]) if board[i][j] != "○" else "."
      row_str += " "
    print(row_str)
  print("=" * 17)


# =========================================================
# 7. メインループ (Main Execution)
# =========================================================
if __name__ == "__main__":
  print("="*40)
  print("🚀 トリマ ナンプレ完全自動化システム 稼働開始（1時間限定モード）")
  print("="*40)
  
  PROGRAM_START_TIME = time.time()
  RUN_DURATION = 3600 
  MAX_NOT_FOUND = 15
  board_not_found_count = 0 
  
  templates = load_templates()
  
  try:
    while True: 
      elapsed_time = time.time() - PROGRAM_START_TIME
      if elapsed_time > RUN_DURATION:
        print(f"\n⏰ 稼働から1時間が経過しました（{elapsed_time/60:.1f}分）。")
        force_stop_and_sleep()
        break 
        
      print(f"\n📸 スマホ画面を取得中... (残り稼働時間: {(RUN_DURATION - elapsed_time)/60:.1f}分)")
      screen = capture_screen()
      
      if screen is not None:
        if _match_template_worker((screen, SUDOKU_MARKER_PATH, 0.75)):
          board_img, board_rect = crop_sudoku_board(screen)
          if board_img is not None:
            print("🧠 固有マーカーと盤面の枠を検知しました。中身を確認中...")
            original_board = read_sudoku_with_template(board_img, templates)
            known_digits_count = sum(1 for row in original_board for cell in row if cell != "○")
            
            if known_digits_count < 15:
              print(f"⚠️ 数字が少なすぎます（{known_digits_count}個）。広告の誤検知と判断しスルーします。")
              board_not_found_count += 1
              if board_not_found_count >= MAX_NOT_FOUND:
                print("❌ 【タイムアウト】一定時間本物の盤面が検知できなかったため終了します。")
                force_stop_and_sleep(); break
              time.sleep(1); continue 

            board_not_found_count = 0 
            display_board(original_board, "AIが認識した初期盤面")
            
            if not is_initial_board_valid(original_board):
              print("❌ 【重大なエラー】読み取った盤面に矛盾（同じ数字の重複）があります。終了します。")
              force_stop_and_sleep(); break

            solved_board = copy.deepcopy(original_board)
            print("\n⏳ AIが解答を計算中...")
            if solve_sudoku(solved_board):
              display_board(solved_board, "AIが導き出した解答")
              input_sudoku_answers(board_rect, original_board, solved_board)
              handle_post_sudoku_flow()
              print("♻️ 1秒後に次のナンプレの認識を開始します...")
              time.sleep(1)
            else:
              print("❌ 【重大なエラー】このナンプレは解けません（不正な盤面の可能性）。終了します。")
              force_stop_and_sleep(); break
          else:
            board_not_found_count += 1
            print(f"🔍 待機中... (枠未検出 {board_not_found_count}/{MAX_NOT_FOUND}回)")
            if board_not_found_count >= MAX_NOT_FOUND:
              print("❌ 【タイムアウト】一定時間盤面が検知できなかったため終了します。")
              force_stop_and_sleep(); break
            time.sleep(3)
        else:
          board_not_found_count += 1
          print(f"🔍 待機中... (固有マーカー未検出 {board_not_found_count}/{MAX_NOT_FOUND}回)")
          if board_not_found_count >= MAX_NOT_FOUND:
            print("❌ 【タイムアウト】一定時間盤面が検知できなかったため終了します。")
            force_stop_and_sleep(); break
          time.sleep(2)
      else:
        time.sleep(1)
  except KeyboardInterrupt:
    print("\n⏹ 手動でプログラムを終了しました。お疲れ様でした！")