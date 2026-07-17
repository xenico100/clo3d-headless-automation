import os
import time
import subprocess

COMM_DIR = "/Users/enicoveck/Documents/clo/clo3d_mcp"
REQUEST_FILE = os.path.join(COMM_DIR, "request.json")
POLL_INTERVAL = 0.1  # 0.1초 단위 실시간 감시

OSASCRIPT_CMD = """
tell application "System Events"
    if exists process "CLO_Standalone_OnlineAuth" then
        tell process "CLO_Standalone_OnlineAuth"
            repeat with w in every window
                if count of buttons of w is 6 then
                    try
                        click button 5 of w
                    end try
                    exit repeat
                end if
            end repeat
        end tell
    end if
end tell
"""

def main():
    print("🚀 [CLO Auto-Runner] 외부 감시 데몬이 가동되었습니다. (0.1초 간격 감시)")
    print("💡 이제 CLO 3D 안에서 마우스를 클릭할 필요가 전혀 없습니다!")
    
    last_trigger_time = 0
    while True:
        try:
            if os.path.exists(REQUEST_FILE):
                # 중복 연속 호출 방지 (최소 0.2초 간격)
                now = time.time()
                if now - last_trigger_time > 0.2:
                    last_trigger_time = now
                    # AppleScript를 통해 CLO 3D 메인 스레드 플러그인 즉시 실행
                    subprocess.run(["osascript", "-e", OSASCRIPT_CMD], check=False)
        except Exception as e:
            pass
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
