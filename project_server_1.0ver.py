"""
네트워크 프로그래밍 과제: TCP 소켓 기반 HTTP 서버 (MySQL 연동 버전)
설명: 본 프로그램은 저수준 TCP 소켓을 활용하여 HTTP/1.0 규격을 준수하는 웹 서버를 구현한 것입니다.
      PyMySQL 라이브러리를 통해 MySQL 데이터베이스와 연동하여 CRUD(Create, Read, Update, Delete) 작업을 수행하며,
      과제 요구사항에 따른 5가지 HTTP Method - Response Case를 처리합니다.
"""

# -*- coding: utf-8 -*-
import socket
import pymysql
import json
import urllib.parse
import traceback

HOST = '127.0.0.1'
PORT = 8080

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',          # 본인의 MySQL 계정
    'password': '71302769',  # 본인의 MySQL 비밀번호
    'db': 'coding_platform',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def parse_http_body(request_data, content_length):
    try:
        parts = request_data.split('\r\n\r\n')
        if len(parts) < 2: return {}
        body_str = parts[1][:content_length]
        if body_str.startswith('{'): return json.loads(body_str)
        return {k: v[0] for k, v in urllib.parse.parse_qs(body_str).items()}
    except:
        return {}

def build_response(status, body_msg):
    body = f"<html><body><h2>{status}</h2><p>{body_msg}</p></body></html>"
    header = f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(body.encode('utf-8'))}\r\nConnection: close\r\n\r\n"
    return header.encode('utf-8') + body.encode('utf-8')

def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"[*] HTTP 서버 구동 완료 (포트 {PORT}) - 고도화된 DB 예외 처리 모드")

    while True:
        client_socket, addr = server_socket.accept()
        try:
            request_data = client_socket.recv(4096).decode('utf-8')
            if not request_data:
                client_socket.close()
                continue

            lines = request_data.split('\r\n')
            method, full_path, _ = lines[0].split(' ')
            
            # URL과 쿼리 스트링 분리 파싱
            parsed_url = urllib.parse.urlparse(full_path)
            path = parsed_url.path
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            content_length = 0
            for line in lines:
                if line.lower().startswith('content-length:'):
                    content_length = int(line.split(':')[1].strip())
                    break

            db_conn = pymysql.connect(**DB_CONFIG)
            
            if path == "/api/users":
                # 컨텍스트 매니저(with)를 통한 안전한 커서 관리
                with db_conn.cursor() as cursor:
                    
                    # 1. GET (동적 조건부 데이터 조회)
                    if method == "GET":
                        sql = "SELECT user_id, email, name, role FROM USER"
                        params = []
                        
                        # 파라미터가 존재하면 WHERE 조건 추가
                        if 'role' in query_params:
                            sql += " WHERE role = %s"
                            params.append(query_params['role'][0])
                            
                        cursor.execute(sql, tuple(params))
                        users = cursor.fetchall()
                        response = build_response("200 OK", f"조회된 유저 수: {len(users)}명<br>{users}")

                    # 2. POST (데이터 생성 및 롤백 처리)
                    elif method == "POST":
                        body = parse_http_body(request_data, content_length)
                        user_id = body.get('user_id')
                        email = body.get('email')
                        password = body.get('password', '1234')
                        name = body.get('name')
                        role = body.get('role', 'STUDENT')

                        if not all([user_id, email, name]):
                            response = build_response("400 Bad Request", "필수 파라미터(user_id, email, name)가 누락되었습니다.")
                        else:
                            try:
                                cursor.execute(
                                    "INSERT INTO USER (user_id, email, password, name, role) VALUES (%s, %s, %s, %s, %s)",
                                    (user_id, email, password, name, role)
                                )
                                db_conn.commit()
                                response = build_response("201 Created", f"유저 '{name}' 등록 완료")
                            except pymysql.err.IntegrityError as e:
                                db_conn.rollback() # 트랜잭션 롤백
                                response = build_response("409 Conflict", f"이미 존재하는 아이디이거나 사용 중인 이메일입니다.<br>DB 에러: {e.args[1]}")
                            except Exception as e:
                                db_conn.rollback()
                                raise e

                    # 3. PUT (데이터 수정 및 롤백 처리)
                    elif method == "PUT":
                        body = parse_http_body(request_data, content_length)
                        user_id = body.get('user_id')
                        new_name = body.get('name')
                        new_role = body.get('role')

                        if not user_id:
                            response = build_response("400 Bad Request", "수정할 대상의 user_id가 누락되었습니다.")
                        elif not new_name and not new_role:
                            response = build_response("400 Bad Request", "수정할 데이터(name 또는 role)를 입력해주세요.")
                        else:
                            try:
                                updates = []
                                params = []
                                if new_name:
                                    updates.append("name = %s")
                                    params.append(new_name)
                                if new_role:
                                    updates.append("role = %s")
                                    params.append(new_role)
                                
                                params.append(user_id)
                                sql = f"UPDATE USER SET {', '.join(updates)} WHERE user_id = %s"
                                
                                affected = cursor.execute(sql, tuple(params))
                                db_conn.commit()
                                
                                if affected > 0:
                                    response = build_response("200 OK", f"'{user_id}' 계정 정보가 성공적으로 수정되었습니다.")
                                else:
                                    response = build_response("404 Not Found", f"수정하려는 대상('{user_id}')이 존재하지 않거나 변경 내용이 없습니다.")
                            except Exception as e:
                                db_conn.rollback()
                                raise e

                    # 4. DELETE (데이터 삭제 및 롤백 처리)
                    elif method == "DELETE":
                        body = parse_http_body(request_data, content_length)
                        user_id = body.get('user_id')
                        
                        if not user_id:
                            response = build_response("400 Bad Request", "삭제할 user_id를 입력하세요.")
                        elif user_id == "admin01":
                            response = build_response("403 Forbidden", "시스템 최고 관리자(ADMIN)는 삭제할 수 없습니다.")
                        else:
                            try:
                                affected = cursor.execute("DELETE FROM USER WHERE user_id=%s", (user_id,))
                                db_conn.commit()
                                if affected > 0:
                                    response = build_response("200 OK", f"'{user_id}' 계정이 정상 삭제되었습니다.")
                                else:
                                    response = build_response("404 Not Found", f"삭제하려는 아이디('{user_id}')를 찾을 수 없습니다.")
                            except Exception as e:
                                db_conn.rollback()
                                raise e

                    else:
                        response = build_response("405 Method Not Allowed", "해당 엔드포인트는 GET, POST, PUT, DELETE만 지원합니다.")

            else:
                response = build_response("404 Not Found", "요청하신 URL 경로가 존재하지 않습니다.")

            db_conn.close()
            client_socket.sendall(response)
            client_socket.close()

        except Exception as e:
            error_msg = traceback.format_exc().replace('\n', '<br>')
            response = build_response("500 Internal Server Error", f"서버 내부 오류가 발생했습니다.<br>{error_msg}")
            client_socket.sendall(response)
            client_socket.close()

if __name__ == "__main__":
    run_server()