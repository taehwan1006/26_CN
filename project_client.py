# -*- coding: utf-8 -*-
import socket
import urllib.parse
import re

HOST = '127.0.0.1'
PORT = 8080

def send_request(method, path, body=""):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((HOST, PORT))
        
        # HTTP 패킷 포맷팅
        req = f"{method} {path} HTTP/1.1\r\nHost: {HOST}:{PORT}\r\n"
        if body:
            req += "Content-Type: application/x-www-form-urlencoded\r\n"
            req += f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}"
        else:
            req += "\r\n"
            
        print("\n" + "="*60)
        print(f"📡 [서버로 요청 전송] {method} {path}")
        if body: 
            print(f"📦 [전송 데이터] {urllib.parse.unquote(body)}") # 인코딩된 데이터를 보기 편하게 디코딩 출력
        print("-" * 60)
        
        # 데이터 송신 및 응답 수신
        client.sendall(req.encode('utf-8'))
        response = client.recv(4096).decode('utf-8')
        
        # 헤더와 본문 파싱
        parts = response.split('\r\n\r\n', 1)
        headers = parts[0]
        resp_body = parts[1] if len(parts) > 1 else ""
        
        status_line = headers.split('\r\n')[0]
        
        clean_body = resp_body.replace('<br>', '\n').replace('</p>', '\n')
        clean_body = re.sub(r'<[^>]+>', '', clean_body).strip()
        
        print(f"✅ [서버 응답 상태] {status_line}")
        print(f"📄 [서버 응답 본문]\n{clean_body}")
        print("="*60 + "\n")
            
    except Exception as e:
        print(f"[-] 통신 에러 발생: {e}")
    finally:
        client.close()

def run_admin_console():
    while True:
        print("\n" + "#"*55)
        print("    [ 코딩 교육 플랫폼 관리자 콘솔 v1.1 ]")
        print("#"*55)
        print(" 1. 신규 회원(수강생/강사) 가입 처리")
        print(" 2. 전체 회원 리스트 조회")
        print(" 3. 권한별(Role) 회원 검색")
        print(" 4. 회원 정보(이름/권한) 수정")
        print(" 5. 회원 강제 탈퇴 처리")
        print(" 6. 잘못된 시스템 경로 접근 테스트")
        print(" 0. 관리자 콘솔 종료")
        print("-" * 55)
        
        choice = input("원하시는 작업 번호를 입력하세요: ").strip()
        
        if choice == '1':
            print("\n>>> [ 신규 회원 가입 ] 빈칸으로 두면 에러 테스트가 가능합니다.")
            uid = input(" * 아이디(user_id): ").strip()
            email = input(" * 이메일(email): ").strip()
            name = input(" * 이름(name): ").strip()
            role = input(" * 권한(STUDENT/INSTRUCTOR/ADMIN) [기본값:STUDENT]: ").strip().upper()
            if not role: role = "STUDENT"
            
            # 한글 및 특수문자 전송을 위한 URL 인코딩 적용
            body = f"user_id={urllib.parse.quote(uid)}&email={urllib.parse.quote(email)}&name={urllib.parse.quote(name)}&role={urllib.parse.quote(role)}"
            send_request("POST", "/api/users", body)
            
        elif choice == '2':
            send_request("GET", "/api/users", "")
            
        elif choice == '3':
            print("\n>>> [ 권한별 회원 검색 ]")
            role = input(" * 검색할 권한(예: INSTRUCTOR): ").strip().upper()
            send_request("GET", f"/api/users?role={urllib.parse.quote(role)}", "")
            
        elif choice == '4':
            print("\n>>> [ 회원 정보 수정 ]")
            uid = input(" * 수정할 회원의 아이디: ").strip()
            name = input(" * 새로운 이름 (변경 안함 = 엔터): ").strip()
            role = input(" * 새로운 권한 (변경 안함 = 엔터): ").strip().upper()
            
            body_parts = [f"user_id={urllib.parse.quote(uid)}"]
            if name: body_parts.append(f"name={urllib.parse.quote(name)}")
            if role: body_parts.append(f"role={urllib.parse.quote(role)}")
            
            body = "&".join(body_parts)
            send_request("PUT", "/api/users", body)
            
        elif choice == '5':
            print("\n>>> [ 회원 강제 탈퇴 ]")
            uid = input(" * 탈퇴시킬 회원의 아이디: ").strip()
            body = f"user_id={urllib.parse.quote(uid)}"
            send_request("DELETE", "/api/users", body)
            
        elif choice == '6':
            print("\n>>> [ 잘못된 API 경로 호출 테스트 ]")
            send_request("GET", "/api/secret_admin_data", "")
            
        elif choice == '0':
            print("프로그램을 종료합니다.")
            break
        else:
            print("[-] 잘못된 입력입니다. 0~6 사이의 번호를 입력해주세요.")

if __name__ == "__main__":
    run_admin_console()