import subprocess
import time

# --- 設定 ---
ADB = r"C:\Users\mahhy\Documents\scrcpy\scrcpy-win64-v3.3.4\adb.exe"
POWL_PACKAGE = "co.testee.android"

def adb_shell(command):
 """ADBコマンドを実行してCompletedProcessを返す。"""
 return subprocess.run(f'"{ADB}" {command}', shell=True, capture_output=True, text=True)

def launch_powl():
 """Powlを起動し、画面が落ち着くまで待機する"""
 print("🚀 Powlを起動します...")
 
 # すでに起動している場合は一度タスクキル（強制終了）してリセットするのも手です
 # adb_shell(f"shell am force-stop {POWL_PACKAGE}")
 # time.sleep(1)
 
 # パッケージ名をもとにアプリを起動
 adb_shell(f"shell monkey -p {POWL_PACKAGE} -c android.intent.category.LAUNCHER 1")
 
 # アプリが立ち上がり、最初の画面（広告やポップアップなど）が出るまで待機
 time.sleep(7)
 print("✅ Powlの起動処理が完了しました。")

# --- テスト実行 ---
if __name__ == "__main__":
 launch_powl()