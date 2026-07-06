# 26_CN
# TCP 소켓 기반 HTTP 웹 서버 및 클라이언트 구현
**온라인 코딩 교육 및 저지(Judge) 플랫폼 백엔드 아키텍처 모사**

---

## 📋 목차
1. [프로젝트 개요](#1-프로젝트-개요)
2. [개발 환경 및 기술 스택](#2-개발-환경-및-기술-스택)
3. [시스템 아키텍처 및 데이터베이스 설계](#3-시스템-아키텍처-및-데이터베이스-설계)
4. [서버 사이드 코드 상세 분석](#4-서버-사이드-코드-상세-분석-serverpy)
5. [클라이언트 사이드 코드 상세 분석](#5-클라이언트-사이드-코드-상세-분석-clientpy)
6. [터미널 실행 결과 및 상태 코드 검증](#6-터미널-실행-결과-및-상태-코드-검증)
7. [Wireshark 패킷 캡처 및 네트워크 계층 검증](#7-wireshark-패킷-캡처-및-네트워크-계층-검증)
8. [결론 및 고찰](#8-결론-및-고찰)

---

## 1. 프로젝트 개요

### 1.1. 목적 및 배경
본 프로젝트는 저수준(Low-level) 파이썬 TCP 소켓을 활용하여 HTTP/1.1 프로토콜의 동작 원리를 구현한 클라이언트-서버 시스템입니다. 프레임워크(Django, Spring 등)에 의존하지 않고, 원시 바이트(Raw Byte) 단위의 통신부터 HTTP 메시지 파싱, 데이터베이스 트랜잭션 제어까지 웹 서버의 내부 동작을 직접 설계하고 검증하는 것을 목표로 합니다. 

### 1.2. 주요 구현 목표
* **HTTP 프로토콜 분석:** 소켓을 통해 수신된 바이트 데이터를 문자열로 디코딩하고, `\r\n`을 기준으로 HTTP 헤더와 본문(Body)을 분리하여 파싱.
* **네트워크 세션 관리:** HTTP/1.1의 Keep-Alive(지속 연결)를 구현하여 통신 오버헤드 최소화.
* **RESTful 아키텍처 적용:** GET, POST, PUT, DELETE 메서드에 따른 데이터베이스 CRUD 매핑.
* **무결성 및 예외 처리:** DB 제약 조건(UNIQUE) 충돌 시 롤백(Rollback) 처리 및 적절한 HTTP 상태 코드(409 Conflict 등) 반환.
* **데이터 인코딩 및 정제:** 클라이언트 전송 시 URL 인코딩 적용 및 수신 시 정규표현식을 활용한 HTML 태그 제거.

---

## 2. 개발 환경 및 기술 스택

* **Language:** Python 3.10+
* **Database:** MySQL 8.0 (PyMySQL 1.1.0)
* **Network/Protocol:** `socket` 모듈, HTTP/1.1, TCP/IP (Port 9090)
* **Standard Library:** `urllib.parse` (URL 인코딩/디코딩), `re` (정규표현식 파싱)
* **Tools:** VSCode, MySQL Workbench, Wireshark (패킷 캡처 및 분석)

---

## 3. 시스템 아키텍처 및 데이터베이스 설계

본 시스템은 온라인 코딩 교육 및 알고리즘 저지(Judge) 플랫폼을 모사하기 위해 총 12개의 테이블로 구성된 `coding_platform` 데이터베이스를 구축했습니다.

![ERD Diagram](ERD_Diagram.png)
*(위 경로에 ERD 이미지를 삽입하세요)*

### 3.1. 핵심 엔티티 및 관계 설명
1. **회원 식별 (USER 테이블)**
   * 시스템의 코어 엔티티로 `role` 칼럼을 통해 STUDENT, INSTRUCTOR, ADMIN 권한을 구분합니다.
   * `email` 칼럼에 `UNIQUE` 제약 조건을 설정하여, 중복 가입 시도 시 데이터베이스 단에서 무결성 에러를 발생시키도록 설계했습니다.
2. **다대다 관계 해소 (COURSE & ENROLLMENT 테이블)**
   * 학생과 강의 코스 간의 다대다(M:N) 관계를 해소하기 위해 `ENROLLMENT`(수강신청) 교차 테이블을 배치했습니다.
   * `student_id`와 `course_id`를 복합 유니크 키(Composite Unique Key)로 묶어 중복 수강을 원천 차단했습니다.
3. **온라인 저지 시스템 (CODING_PROBLEM & SUBMISSION 테이블)**
   * `CODING_PROBLEM` 테이블에 밀리초 단위의 `time_limit`과 메가바이트 단위의 `memory_limit` 칼럼을 설계했습니다.
   * `SUBMISSION` 테이블은 제출된 소스 코드와 함께 `TIME_LIMIT`, `COMPILE_ERROR`, `SUCCESS` 등의 채점 상태를 열거형(ENUM)으로 기록합니다.

---

## 4. 서버 사이드 코드 상세 분석 (`server.py`)

서버 코드는 파이썬 기본 `socket` 모듈을 이용하여 구현되었으며, 크게 소켓 초기화, HTTP 파싱, 라우팅, 트랜잭션 제어의 4단계로 구성됩니다.

### 4.1. 소켓 초기화 및 Keep-Alive 구현
```python
def run_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"[*] HTTP 서버 구동 완료 (포트 {PORT}) - HTTP/1.1 Keep-Alive 모드")

    while True:
        client_socket, addr = server_socket.accept()
        client_socket.settimeout(5.0) # 5초간 요청 대기 (타임아웃 설정)
        
        try:
            while True: # 단일 TCP 연결 내 다중 요청 처리를 위한 내부 루프
                try:
                    request_data = client_socket.recv(4096).decode('utf-8')
                    if not request_data:
                        break
                except socket.timeout:
                    print(f"[-] 타임아웃 발생. 연결 종료: {addr}")
                    break
                # ... (이하 라우팅 로직)
```
* **동작 원리:** 매 요청마다 소켓을 닫는 HTTP/1.0의 한계를 극복하기 위해, 클라이언트 접속 시 `settimeout(5.0)`을 부여하고 내부에 `while True` 루프를 배치했습니다. 이를 통해 단일 TCP 통로에서 다수의 HTTP 요청을 처리하여 네트워크 오버헤드를 감소시켰습니다.

### 4.2. HTTP 패킷 파싱 로직
```python
lines = request_data.split('\r\n')
method, full_path, _ = lines[0].split(' ')

parsed_url = urllib.parse.urlparse(full_path)
path = parsed_url.path
query_params = urllib.parse.parse_qs(parsed_url.query)

content_length = 0
for line in lines:
    if line.lower().startswith('content-length:'):
        content_length = int(line.split(':')[1].strip())
        break
```
* **동작 원리:** 수신된 문자열을 HTTP 규약인 `\r\n` 단위로 분할합니다. 첫 줄에서 HTTP 메서드(GET, POST 등)와 경로를 추출하고, `urllib.parse`를 통해 URL과 쿼리 스트링을 분리합니다. 이후 헤더를 순회하며 `Content-Length`를 추출해 HTTP Body 처리의 기준값으로 삼습니다.

### 4.3. 트랜잭션 제어 및 롤백 방어 (POST 메서드)
```python
if method == "POST":
    try:
        sql = "INSERT INTO USER (user_id, email, name, role) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (body_params['user_id'], body_params['email'], body_params['name'], body_params['role']))
        db_conn.commit()
        response = build_response("201 Created", "회원 가입이 완료되었습니다.")
    except pymysql.err.IntegrityError:
        db_conn.rollback() # 무결성 에러 발생 시 즉시 롤백
        response = build_response("409 Conflict", "이미 가입된 이메일 또는 아이디입니다.")
```
* **동작 원리:** 데이터 삽입 시도 중 `UNIQUE` 제약 조건(이메일 중복 등)에 의해 `IntegrityError`가 발생할 경우, 예외 처리 블록으로 이동합니다. 이때 `db_conn.rollback()`을 명시적으로 호출하여 데이터베이스의 오염을 막고, 프론트엔드로 `409 Conflict` 상태 코드를 반환하여 서버 다운을 방지합니다.

### 4.4. 애플리케이션 단 보안 검증 (DELETE 메서드)
```python
elif method == "DELETE":
    if body_params['user_id'] == 'admin01':
        response = build_response("403 Forbidden", "최고 관리자 계정은 삭제할 수 없습니다.")
    else:
        sql = "DELETE FROM USER WHERE user_id = %s"
        cursor.execute(sql, (body_params['user_id'],))
        db_conn.commit()
        response = build_response("200 OK", "계정이 삭제되었습니다.")
```
* **동작 원리:** DELETE 요청이 들어왔을 때, 삭제 대상이 시스템 최고 관리자(`admin01`)인 경우 DB로 쿼리를 전송하지 않고 애플리케이션 계층에서 선제적으로 `403 Forbidden`을 반환하여 시스템을 보호합니다.

---

## 5. 클라이언트 사이드 코드 상세 분석 (`client.py`)

클라이언트 애플리케이션은 사용자가 서버와 양방향으로 소통할 수 있는 CLI(Command Line Interface) 관리자 콘솔 형태로 제작되었습니다.

### 5.1. 데이터 인코딩 전송 (URL 인코딩)
```python
# 사용자 입력부
uid = input(" * 아이디(user_id): ").strip()
email = input(" * 이메일(email): ").strip()
name = input(" * 이름(name): ").strip()

# 한글 및 특수문자 전송을 위한 URL 인코딩 적용
body = f"user_id={urllib.parse.quote(uid)}&email={urllib.parse.quote(email)}&name={urllib.parse.quote(name)}"
send_request("POST", "/api/users", body)
```
* **동작 원리:** HTTP 패킷 본문에 한글(`이름`)이나 특수문자(`@` 등)가 그대로 실릴 경우 인코딩 깨짐 현상이 발생할 수 있습니다. 이를 방지하기 위해 표준 규격인 `application/x-www-form-urlencoded`에 맞추어 `urllib.parse.quote()`를 적용, `%EC%8B` 형태의 문자열로 치환하여 전송합니다.

### 5.2. 서버 응답 데이터 정제 (정규표현식)
```python
# 서버 응답 수신 및 분할
parts = response.split('\r\n\r\n', 1)
headers = parts[0]
resp_body = parts[1] if len(parts) > 1 else ""

status_line = headers.split('\r\n')[0]

# HTML 태그 제거 로직
clean_body = resp_body.replace('<br>', '\n').replace('</p>', '\n')
clean_body = re.sub(r'<[^>]+>', '', clean_body).strip()
```
* **동작 원리:** 서버가 HTTP 표준을 지키기 위해 응답 본문을 `<html><body>` 태그로 감싸서 보내면, 터미널 출력 시 가독성이 심각하게 저하됩니다. 이를 해결하기 위해 파이썬 `re` 모듈을 사용하여 `<[^>]+>` 정규식 패턴과 매치되는 모든 HTML 태그를 공백으로 치환하고 줄바꿈으로 변환했습니다.

---

## 6. 터미널 실행 결과 및 상태 코드 검증

구현된 서버와 클라이언트를 구동하여 REST API의 다양한 상태 코드 반환을 검증한 로그입니다.

### 6.1. 400 Bad Request (필수 파라미터 누락)
클라이언트에서 가입 시 이름 파라미터를 누락하고 요청을 보낸 결과입니다.

```text
#######################################################
    [ 코딩 교육 플랫폼 관리자 콘솔 v1.1 ]
#######################################################
 1. 신규 회원(수강생/강사) 가입 처리
 2. 전체 회원 리스트 조회
 3. 권한별(Role) 회원 검색
 4. 회원 정보(이름/권한) 수정
 5. 회원 강제 탈퇴 처리
 6. 잘못된 시스템 경로 접근 테스트
 0. 관리자 콘솔 종료
-------------------------------------------------------
원하시는 작업 번호를 입력하세요: 1

>>> [ 신규 회원 가입 ] 빈칸으로 두면 에러 테스트가 가능합니다.
 * 아이디(user_id): testID
 * 이메일(email): test.email.com
 * 이름(name): 
 * 권한(STUDENT/INSTRUCTOR/ADMIN) [기본값:STUDENT]:  

============================================================
📡 [서버로 요청 전송] POST /api/users
📦 [전송 데이터] user_id=testID&email=test.email.com&name=&role=STUDENT
------------------------------------------------------------
✅ [서버 응답 상태] HTTP/1.1 400 Bad Request
📄 [서버 응답 본문]
400 Bad Request필수 파라미터(user_id, email, name)가 누락되었습니다.
============================================================
```

### 6.2. 201 Created & 409 Conflict (정상 생성 및 무결성 충돌 방어)
정상적인 데이터 삽입 후, 동일한 데이터를 재전송하여 DB 롤백 처리를 유도한 결과입니다.

```text
#######################################################
    [ 코딩 교육 플랫폼 관리자 콘솔 v1.1 ]
#######################################################
 1. 신규 회원(수강생/강사) 가입 처리
 2. 전체 회원 리스트 조회
 3. 권한별(Role) 회원 검색
 4. 회원 정보(이름/권한) 수정
 5. 회원 강제 탈퇴 처리
 6. 잘못된 시스템 경로 접근 테스트
 0. 관리자 콘솔 종료
-------------------------------------------------------
원하시는 작업 번호를 입력하세요: 1

>>> [ 신규 회원 가입 ] 빈칸으로 두면 에러 테스트가 가능합니다.
 * 아이디(user_id): testID
 * 이메일(email): test.email.com
 * 이름(name): testName
 * 권한(STUDENT/INSTRUCTOR/ADMIN) [기본값:STUDENT]: 

============================================================
📡 [서버로 요청 전송] POST /api/users
📦 [전송 데이터] user_id=testID&email=test.email.com&name=testName&role=STUDENT
------------------------------------------------------------
✅ [서버 응답 상태] HTTP/1.1 201 Created
📄 [서버 응답 본문]
201 Created유저 'testName' 등록 완료
============================================================

#######################################################
    [ 코딩 교육 플랫폼 관리자 콘솔 v1.1 ]
#######################################################
 1. 신규 회원(수강생/강사) 가입 처리
 2. 전체 회원 리스트 조회
 3. 권한별(Role) 회원 검색
 4. 회원 정보(이름/권한) 수정
 5. 회원 강제 탈퇴 처리
 6. 잘못된 시스템 경로 접근 테스트
 0. 관리자 콘솔 종료
-------------------------------------------------------
원하시는 작업 번호를 입력하세요: 1

>>> [ 신규 회원 가입 ] 빈칸으로 두면 에러 테스트가 가능합니다.
 * 아이디(user_id): testID
 * 이메일(email): test.email.com
 * 이름(name): testName
 * 권한(STUDENT/INSTRUCTOR/ADMIN) [기본값:STUDENT]: 

============================================================
📡 [서버로 요청 전송] POST /api/users
📦 [전송 데이터] user_id=testID&email=test.email.com&name=testName&role=STUDENT
------------------------------------------------------------
✅ [서버 응답 상태] HTTP/1.1 409 Conflict
📄 [서버 응답 본문]
409 Conflict이미 존재하는 아이디이거나 사용 중인 이메일입니다.
DB 에러: Duplicate entry 'testID' for key 'user.PRIMARY'
============================================================
```

### 6.3. 200 OK (GET 동적 쿼리 및 데이터 정제 포맷팅 출력)
권한 필터링(`?role=STUDENT`)을 적용한 GET 조회 결과이며, HTML이 완벽히 제거되어 콘솔에 예쁘게 정렬된 모습입니다.

```text
#######################################################
    [ 코딩 교육 플랫폼 관리자 콘솔 v1.1 ]
#######################################################
 1. 신규 회원(수강생/강사) 가입 처리
 2. 전체 회원 리스트 조회
 3. 권한별(Role) 회원 검색
 4. 회원 정보(이름/권한) 수정
 5. 회원 강제 탈퇴 처리
 6. 잘못된 시스템 경로 접근 테스트
 0. 관리자 콘솔 종료
-------------------------------------------------------
원하시는 작업 번호를 입력하세요: 3

>>> [ 권한별 회원 검색 ]
 * 검색할 권한(예: INSTRUCTOR): STUDENT

============================================================
📡 [서버로 요청 전송] GET /api/users?role=STUDENT
------------------------------------------------------------
✅ [서버 응답 상태] HTTP/1.1 200 OK
📄 [서버 응답 본문]
200 OK총 11명의 회원이 조회되었습니다.
-------------------------------------------------------
 1. [STUDENT   ] 이학생 (stud01) |  stud1@test.com
 2. [STUDENT   ] 박학생 (stud02) |  stud2@test.com
 3. [STUDENT   ] 신태환 (stud03) |  stud03@test.com
 4. [STUDENT   ] 유학생 (stud04) |  stud4@test.com
 5. [STUDENT   ] 조학생 (stud05) |  stud5@test.com
 6. [STUDENT   ] 강학생 (stud06) |  stud6@test.com
 7. [STUDENT   ] 윤학생 (stud07) |  stud7@test.com
 8. [STUDENT   ] 장학생 (stud08) |  stud8@test.com
 9. [STUDENT   ] 임학생 (stud09) |  stud9@test.com
10. [STUDENT   ] 한학생 (stud10) |  stud10@test.com
11. [STUDENT   ] testName (testID) |  test.email.com
-------------------------------------------------------
============================================================
```

### 6.4. 403 Forbidden & 404 Not Found (권한 부족 및 데이터 부재)
관리자 계정 삭제 시도 시 애플리케이션 단에서 차단되는 결과와, 없는 유저를 수정 시도한 결과입니다.

```text
#######################################################
    [ 코딩 교육 플랫폼 관리자 콘솔 v1.1 ]
#######################################################
 1. 신규 회원(수강생/강사) 가입 처리
 2. 전체 회원 리스트 조회
 3. 권한별(Role) 회원 검색
 4. 회원 정보(이름/권한) 수정
 5. 회원 강제 탈퇴 처리
 6. 잘못된 시스템 경로 접근 테스트
 0. 관리자 콘솔 종료
-------------------------------------------------------
원하시는 작업 번호를 입력하세요: 5

>>> [ 회원 강제 탈퇴 ]
 * 탈퇴시킬 회원의 아이디: admin01

============================================================
📡 [서버로 요청 전송] DELETE /api/users
📦 [전송 데이터] user_id=admin01
------------------------------------------------------------
✅ [서버 응답 상태] HTTP/1.1 403 Forbidden
📄 [서버 응답 본문]
403 Forbidden시스템 최고 관리자(ADMIN)는 삭제할 수 없습니다.
============================================================

#######################################################
    [ 코딩 교육 플랫폼 관리자 콘솔 v1.1 ]
#######################################################
 1. 신규 회원(수강생/강사) 가입 처리
 2. 전체 회원 리스트 조회
 3. 권한별(Role) 회원 검색
 4. 회원 정보(이름/권한) 수정
 5. 회원 강제 탈퇴 처리
 6. 잘못된 시스템 경로 접근 테스트
 0. 관리자 콘솔 종료
-------------------------------------------------------
원하시는 작업 번호를 입력하세요: 4

>>> [ 회원 정보 수정 ]
 * 수정할 회원의 아이디: ghostID
 * 새로운 이름 (변경 안함 = 엔터): llll
 * 새로운 권한 (변경 안함 = 엔터):   

============================================================
📡 [서버로 요청 전송] PUT /api/users
📦 [전송 데이터] user_id=ghostID&name=llll
------------------------------------------------------------
✅ [서버 응답 상태] HTTP/1.1 404 Not Found
📄 [서버 응답 본문]
404 Not Found수정하려는 대상('ghostID')이 존재하지 않거나 변경 내용이 없습니다.
============================================================
```

---

## 7. Wireshark 패킷 캡처 및 네트워크 계층 검증

단순히 터미널에 텍스트가 뜨는 것을 넘어, 실제 네트워크 소켓에서 데이터가 규약에 맞게 전송되었는지 로컬호스트(루프백) 포트 9090을 캡처하여 검증했습니다.

### 7.1. TCP 3-Way Handshake 및 연결 해제 (Teardown)
![Wireshark Handshake](Wireshark_Handshake.png)
* HTTP 통신 발생 직전, 클라이언트 포트와 서버 포트(9090) 간에 `SYN` ➔ `SYN, ACK` ➔ `ACK` 패킷이 교환되며 신뢰성 있는 TCP 연결이 성립됨을 확인했습니다.
* 시연 종료 후 5초의 타임아웃이 경과하자 서버 측에서 `FIN` 패킷을 전송하여 연결을 안전하게 회수(Graceful Shutdown)하는 것을 확인했습니다.

### 7.2. HTTP/1.1 Keep-Alive (다중 요청 스트림)
![Wireshark Keep-Alive](wireshark_keep_alive.png)
* 패킷의 [Follow TCP Stream]을 확인한 결과, 응답 헤더에 `Connection: keep-alive`가 명확히 기재되어 있습니다.

### 7.3. Payload URL 인코딩 및 Content-Length 일치 여부
![Wireshark Payload](wireshark_payload.png)
*(위 경로에 바디 데이터 인코딩 캡처 이미지를 삽입하세요)*
* 클라이언트에서 전송한 한글 이름 `신태환`과 이메일의 특수문자 `@`가 원문이 아닌 `%EC%8B%A0%ED%83%9C%ED%99%98` 및 `%40`으로 변환되어 바이트 스트림에 실린 것을 확인했습니다.
* 헤더의 `Content-Length` 값과 실제 전송된 바이트 길이가 정확히 일치하여, 패킷 조각화 과정에서 발생할 수 있는 데이터 손실이 없음을 증명했습니다.

---

## 8. 결론 및 고찰

본 프로젝트를 통해 추상화된 웹 프레임워크 아래에서 네트워크 트래픽이 실제로 어떻게 교환되고 제어되는지 심도 있게 이해할 수 있었습니다. 

특히 HTTP/1.0의 단기 연결 방식을 HTTP/1.1의 Keep-Alive 로직으로 업그레이드하면서 소켓의 타임아웃과 블로킹 개념을 명확히 익혔으며, 데이터베이스 트랜잭션 도중 발생하는 무결성 예외를 `try-except`와 `rollback()`을 통해 직접 방어함으로써 백엔드 서버의 안정성이 구성되는 핵심 원리를 습득했습니다.
