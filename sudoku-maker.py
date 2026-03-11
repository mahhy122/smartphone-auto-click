import cv2
import numpy as np
import os

def extract_digit_bbox(img):
 """【新機能】画像の白い部分（文字）をギリギリで切り抜いて、24x24に統一する"""
 # 白いピクセルの座標をすべて取得
 coords = cv2.findNonZero(img)
 if coords is None:
  return None
  
 # 白いピクセルを囲む最小の長方形（バウンディングボックス）を計算
 x, y, w, h = cv2.boundingRect(coords)
 
 # 小さすぎるゴミ（幅2px未満、高さ5px未満など）は無視
 if w < 2 or h < 5:
  return None
  
 # 文字のギリギリで画像を切り抜く
 digit_roi = img[y:y+h, x:x+w]
 
 # 比較しやすいように同じサイズ（24x24）に統一する
 return cv2.resize(digit_roi, (24, 24))

def load_templates(template_dir="targets/torima-sudoku/digits"):
 """テンプレート画像群を読み込み、前処理（2値化＋切り抜き）して辞書で返す。

 返却: {数字: 24x24画像}
 """
 templates = {}
 for i in range(1, 10):
  path = os.path.join(template_dir, f"{i}.png")
  img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
  if img is not None:
   _, thresh = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
   # テンプレート画像も「ギリギリ切り抜き」をして基準を揃える！
   processed = extract_digit_bbox(thresh)
   if processed is not None:
    templates[i] = processed
  else:
   print(f"⚠️ テンプレート画像が見つかりません: {path}")
 return templates

def read_sudoku_with_template(cropped_img, templates):
 """切り出した盤面画像をセルごとに分割し、テンプレート照合で数字を読み取る。

 返却: 9x9 の盤面（数字または '○'）
 """
 gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
 height, width = gray.shape
 cell_h = height // 9
 cell_w = width // 9

 sudoku_board = []
 os.makedirs("debug_cells", exist_ok=True)

 for row_idx in range(9):
  row_data = []
  for col_idx in range(9):
   cell = gray[row_idx*cell_h : (row_idx+1)*cell_h, col_idx*cell_w : (col_idx+1)*cell_w]
   margin_y = int(cell_h * 0.15)
   margin_x = int(cell_w * 0.15)
   cropped_cell = cell[margin_y : cell_h - margin_y, margin_x : cell_w - margin_x]

   _, thresh = cv2.threshold(cropped_cell, 128, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

   filename = f"debug_cells/cell_{row_idx}_{col_idx}.png"
   cv2.imwrite(filename, thresh)

   # 【変更点】マス全体を判定するのではなく、文字だけを切り抜いた画像を判定にかける
   digit_roi = extract_digit_bbox(thresh)

   if digit_roi is None:
    row_data.append("○")
   else:
    best_match = "○"
    best_score = 0.0
    
    # ギリギリで切り抜かれた文字同士を比較
    for digit, temp_img in templates.items():
     res = cv2.matchTemplate(digit_roi, temp_img, cv2.TM_CCOEFF_NORMED)
     _, max_val, _, _ = cv2.minMaxLoc(res)
     
     if max_val > best_score:
      best_score = max_val
      best_match = digit
      
    print(f"マス[{row_idx+1}, {col_idx+1}] -> 判定: {best_match} (スコア: {best_score:.2f})")
      
    # ズレが解消されたので、スコアはかなり高くなるはずです（0.7以上を基準に）
    if best_score > 0.7:
     row_data.append(best_match)
    else:
     row_data.append("○")
     
  sudoku_board.append(row_data)

 return sudoku_board