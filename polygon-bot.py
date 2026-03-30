import os
import time
import json
import random
import string
import hashlib
import requests # type: ignore
from typing import List, Tuple, Dict, Any, Optional
from Contests import PRETS10c1_PTNK_2026 as Problems_data

# === CẤU HÌNH API ===
API_PATH = r"D:\Polygon-Test-Generator\polygon.api"
CACHE_FILE = 'D:\Polygon-Test-Generator\polygon_cache.json'
API_KEY = "67"
API_SECRET = "36"
BASE_URL = "https://polygon.codeforces.com/api"

session = requests.Session()

# ==========================================
# HÀM CƠ SỞ: GIAO TIẾP API & QUẢN LÝ CACHE
# ==========================================

def generate_api_params(method_name: str, params: Dict[str, Any]) -> Dict[str, str]:
    str_params = {k: str(v) for k, v in params.items()}
    rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    str_params.update({'apiKey': API_KEY, 'time': str(int(time.time()))})
    sorted_params = sorted(str_params.items())  
    
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
    sig_text = f"{rand_str}/{method_name}?{query_string}#{API_SECRET}"
    
    str_params['apiSig'] = rand_str + hashlib.sha512(sig_text.encode('utf-8')).hexdigest()
    return str_params

def call_polygon_api(method_name: str, params: Dict[str, Any], stream: bool = False) -> Any:
    """Gọi API với cơ chế tự động thử lại (Retry) nếu bị Polygon Rate Limit."""
    url = f"{BASE_URL}/{method_name}"
    max_retries = 3
    base_delay = 0

    for attempt in range(max_retries):
        auth_params = generate_api_params(method_name, params)
        try:
            response = session.post(url, data=auth_params, stream=stream, timeout=30)
            
            # Xử lý Rate Limit từ server (HTTP 429 hoặc báo ERROR chuỗi Too many requests)
            if response.status_code == 429 or (not stream and "Too many requests" in response.text):
                delay = 1 * (2 ** attempt)
                print(f"   ⚠️ Rate Limit! Chờ {delay}s để thử lại...")
                time.sleep(delay)
                continue
                
            if stream:
                return response
            return response.json()
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                return {"status": "FAILED", "comment": f"Request Error: {str(e)}"}
            time.sleep(base_delay)

def load_local_cache() -> Dict[str, int]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_local_cache(cache: Dict[str, int]):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)

def sync_cache_from_polygon() -> Dict[str, int]:
    """Gọi API tải toàn bộ bài tập và ghi đè local cache."""
    print("[*] 🔄 Đồng bộ dữ liệu từ Polygon server...")
    res_list = call_polygon_api('problems.list', {})
    
    if res_list.get('status') == 'OK':
        new_cache = {p['name']: p['id'] for p in res_list.get('result', [])}
        save_local_cache(new_cache)
        print(f"[*] ✅ Đã ghi đè local cache với {len(new_cache)} bài tập.")
        return new_cache
    else:
        print(f"[*] ❌ ERROR đồng bộ từ Polygon: {res_list.get('comment')}")
        return {}

def get_or_create_problem(internal_name: str, cache: Dict[str, int]) -> Optional[int]:
    # 1. Kiểm tra trong Local Cache
    if internal_name in cache:
        print(f"[*] ⚡ Bài tập '{internal_name}' đã có trong Local. ID: {cache[internal_name]}")
        return cache[internal_name]
        
    # 2. Không có trong Local -> Yêu cầu tạo mới
    print(f"[*] ✨ Bài tập '{internal_name}' chưa có ở Local. Đang khởi tạo trên server...")
    res = call_polygon_api('problem.create', {'name': internal_name})
    
    # 3. Tạo mới thành công
    if res.get('status') == 'OK':
        pid = res['result']['id']
        cache[internal_name] = pid
        save_local_cache(cache)
        print(f"[*] ✅ Đã tạo thành công. Polygon ID: {pid}")
        return pid
        
    # 4. Gặp lỗi khi tạo (Thường do server đã có nhưng local bị thiếu)
    print(f"[*] ⚠️ Lỗi tạo bài (Server reject): {res.get('comment')}")
    print(f"[*] ⏩ Kích hoạt fallback: Tải lại toàn bộ dữ liệu từ server...")
    
    # 5. Đồng bộ và cập nhật lại biến cache
    synced_cache = sync_cache_from_polygon()
    cache.clear()
    cache.update(synced_cache)
    
    # 6. Kiểm tra lại một lần nữa
    if internal_name in cache:
        print(f"[*] 🔄 Đã tìm thấy '{internal_name}' sau khi đồng bộ. ID: {cache[internal_name]}")
        return cache[internal_name]
    else:
        print(f"[*] ❌ ERROR: Vẫn không thể lấy hoặc tạo bài tập '{internal_name}'.")
        return None

# ==========================================
# HÀM XỬ LÝ: UPLOAD VÀ CẤU HÌNH BÀI TẬP
# ==========================================

def upload_statement(pid: int, tex_path: str, name: str = "KONG"):
    if not os.path.exists(tex_path):
        print(f"[{pid}] ❌ KHÔNG TÌM THẤY FILE STATEMENT: {tex_path}")
        return

    # Vẫn giữ utf-8-sig để đề phòng lỗi BOM ký tự ẩn
    with open(tex_path, 'r', encoding='utf-8-sig') as f:
        full_content = f.read().strip()
        
    if len(full_content) == 0:
        print(f"[{pid}] ❌ LỖI: File {tex_path} đang trống.")
        return

    params = {
        'problemId': pid,
        'lang': 'english', # Giữ 'english' để không bị server từ chối vì cấu hình ngôn ngữ
        'encoding': 'UTF-8',
        'name': name,
        'legend': full_content,
        'input': '',
        'output': '',
        'notes': ''
    }

    res_stmt = call_polygon_api('problem.saveStatement', params)

    if res_stmt.get('status') == 'OK':
        print(f"[{pid}] [2/6] ✅ Đã upload Statement ({len(full_content)} ký tự).")
    else:
        print(f"[{pid}] ❌ LỖI Statement: {res_stmt.get('comment')}")

def setup_basic_info(pid: int, name: str, tex_path: str):
    call_polygon_api('problem.updateInfo', {
        'problemId': pid, 'inputFile': 'stdin', 'outputFile': 'stdout', 
        'timeLimit': '1000', 'memoryLimit': '256'
    })
    print(f"[{pid}] [1/6] ✅ Đã set Time Limit 1s, Memory 256MB")

    upload_statement(pid, tex_path, name)
    
    call_polygon_api('problem.setChecker', {'problemId': pid, 'checker': 'std::lcmp.cpp'})
    print(f"[{pid}] [3/6] ✅ Đã set checker: std::lcmp.cpp")

def upload_file_to_polygon(pid: int, file_path: str, file_type: str, file_name: str, step_tag: str, tag: str = None) -> bool:
    if not os.path.exists(file_path):
        print(f"[{pid}] {step_tag} ❌ KHÔNG TÌM THẤY FILE: {file_path}")
        return False
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().replace('\r\n', '\n')
        
    params = {'problemId': pid, 'name': file_name, 'file': content, 'sourceType': 'cpp.gcc14-64-msys2-g++23'}
    
    if file_type == 'solution':
        api_method, params['tag'] = 'problem.saveSolution', tag
    else:
        api_method, params['type'] = 'problem.saveFile', 'source'

    res = call_polygon_api(api_method, params)
    success = res.get('status') == 'OK'
    print(f"[{pid}] {step_tag} {'✅ Đã upload' if success else '❌ ERROR upload'} {file_name}")
    if not success:
        print(f"   -> {res.get('comment')}")
    return success

def setup_tests(pid: int, script_path: str):
    if not os.path.exists(script_path):
        print(f"[{pid}] [6/6] ❌ KHÔNG TÌM THẤY SCRIPT: {script_path}")
        return

    with open(script_path, 'r', encoding='utf-8') as f:
        clean_lines = [line.strip() for line in f.read().splitlines() if line.strip()]
        
    res_script = call_polygon_api('problem.saveScript', {
        'problemId': pid, 'testset': 'tests', 'source': '\n'.join(clean_lines)
    })

    if res_script.get('status') != 'OK':
        print(f"[{pid}] [6/6] ❌ ERROR Script: {res_script.get('comment')}")
        return

    total_tests = len(clean_lines)
    if total_tests == 0:
        print(f"[{pid}] [6/6] ⚠️ Script trống.")
        return

    print(f"[{pid}] [6/6] Phân bổ {total_tests} tests (2 sample), chia đều 100 điểm...")
    call_polygon_api('problem.enablePoints', {'problemId': pid, 'enable': 'true'})
    
    base_points = round(100.0 / total_tests, 2)
    for idx, cmd in enumerate(clean_lines, start=1):
        points = round(100.0 - (base_points * (total_tests - 1)), 2) if idx == total_tests else base_points
        is_sample = 'true' if idx <= 2 else 'false'

        res_test = call_polygon_api('problem.saveTest', {
            'problemId': pid, 'testset': 'tests', 'testIndex': str(idx),
            'testUseInStatements': is_sample, 'testPoints': f"{points:.2f}"
        })
        
        if res_test.get('status') == 'OK':
            print(f"   -> 🟢 [Test {idx}/{total_tests}] OK | Point: {points:.2f} | Sample test: {is_sample} | Script: '{cmd}'")
        else:
            print(f"   -> 🔴 [Test {idx}/{total_tests}] ERROR: {res_test.get('comment')}")


# ==========================================
# HÀM LẤY DANH SÁCH BÀI TẬP (DWUY CODE)
# ==========================================

def get_problems(problem_data: zip) -> List[Tuple[int, str]]:
    generated_problems = []
    
    print("\n[*] Đang tải dữ liệu bài tập từ Local Cache...")
    problem_cache = load_local_cache()
    print(f"[*] ✅ Local Cache hiện có {len(problem_cache)} bài tập.")
    
    for int_name, stmt_name, sol_path, tex_path, gen_path, script_path, folder in problem_data:

        pid = get_or_create_problem(int_name, problem_cache)
        if not pid: continue
            
        generated_problems.append((pid, folder))
        print(f"🦆 Get problem [{stmt_name}] with ID [{pid}] and Internal name [{int_name}]")

    return generated_problems

# ==========================================
# HÀM XỬ LÝ LÔ: THIẾT LẬP, BUILD VÀ DOWNLOAD
# ==========================================

def batch_upload_resources(problem_data_list: list) -> Dict[str, int]:
    """PHA 1: Tạo bài tập, cấu hình thông tin và upload file (Statement, Sol, Gen)"""
    print("\n[*] Đang tải dữ liệu bài tập từ Local Cache...")
    problem_cache = load_local_cache()
    successful_pids = {}

    for int_name, stmt_name, sol_path, tex_path, gen_path, script_path, folder in problem_data_list:
        print(f"\n{'='*50}\n[PHA 1] UPLOAD TÀI NGUYÊN: {int_name}\n{'='*50}")
        
        pid = get_or_create_problem(int_name, problem_cache)
        if not pid: continue
            
        setup_basic_info(pid, stmt_name, tex_path)
        upload_file_to_polygon(pid, sol_path, 'solution', os.path.basename(sol_path), '[4/6]', 'MA')
        upload_file_to_polygon(pid, gen_path, 'source', 'generator.cpp', '[5/6]')
        
        # Lưu lại những bài đã upload resource thành công để chuyển giao sang Pha 2
        successful_pids[int_name] = pid

    return successful_pids

def batch_setup_tests(problem_data_list: list, successful_pids: Dict[str, int]) -> Dict[str, int]:
    tested_pids = {}

    for int_name, stmt_name, sol_path, tex_path, gen_path, script_path, folder in problem_data_list:
        if int_name not in successful_pids:
            continue
        
        pid = successful_pids[int_name]
        print(f"\n{'='*50}\n[PHA 2] SETUP TESTS: {int_name}\n{'='*50}")
        
        setup_tests(pid, script_path)
        tested_pids[int_name] = pid

    return tested_pids

def batch_commit(pids_to_commit: Dict[str, int]):
    """PHA 3: Commit tất cả các bài tập có sự thay đổi"""
    print("\n=== PHA 3: YÊU CẦU COMMIT CÁC THAY ĐỔI ===")
    if not pids_to_commit:
        print(" -> Không có bài tập nào cần commit.")
        return

    for int_name, pid in pids_to_commit.items():
        print(f"[{pid}] Đang yêu cầu commit bài {int_name}...")
        res_commit = call_polygon_api('problem.commitChanges', {
            'problemId': pid, 
            'message': 'Auto setup: Updated resources/tests'
        })
        
        if res_commit.get('status') == 'OK':
            print(f"   -> ✅ COMMIT thành công.")
        else:
            print(f"   -> ❌ LỖI COMMIT: {res_commit.get('comment')}")

def commit_changes(problem_data_list: List[Tuple[int, str]]):
    print("\nYÊU CẦU COMMIT CÁC BÀI TẬP")
    for pid, _ in problem_data_list:
        res = call_polygon_api('problem.commitChanges', {'problemId': pid, 'message': 'Upload generator, script & solution'})
        print(f"BÀI TẬP [{pid}] {'✅ Thành công' if res.get('status') == 'OK' else f'❌ ERROR: {res.get('comment')}'}")

def download_package_zip(pid: int, package_id: int, save_path: str) -> Dict[str, Any]:
    params = {'problemId': pid, 'packageId': package_id, 'type': 'standard'}
    response = call_polygon_api('problem.package', params, stream=True)
    
    if isinstance(response, dict): 
        return response

    if 'application/json' in response.headers.get('content-type', ''):
        return response.json()
        
    try:
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return {"status": "OK", "path": save_path}
    except IOError as e:
        return {"status": "FAILED", "comment": str(e)}

def build_and_download_packages(problem_data_list: List[Tuple[int, str]]):
    tasks = {}

    print("\n=== PHA 1: YÊU CẦU BUILD TẤT CẢ BÀI TẬP ===")
    for pid, folder in problem_data_list:
        res_before = call_polygon_api('problem.packages', {'problemId': pid})
        packages = res_before.get('result', []) if res_before.get('status') == 'OK' else []
        old_max_id = max([p['id'] for p in packages], default=-1)

        res_build = call_polygon_api('problem.buildPackage', {'problemId': pid, 'full': 'false', 'verify': 'true'})
        
        if res_build.get('status') == 'OK':
            print(f"BÀI TẬP [{pid}] ✅ Đã gửi yêu cầu build.")
            tasks[pid] = {'folder': folder, 'state': 'POLLING', 'old_max_id': old_max_id, 'pkg_id': None}
        else:
            comment = res_build.get('comment', '').lower()
            
            # CHỈ KIỂM TRA TỪ KHÓA CỐT LÕI NÀY / ONLY CHECK THIS CORE KEYWORD
            if "already non-failed" in comment:
                ready_packages = [p for p in packages if p.get('state') == 'READY' and p.get('type', 'standard') == 'standard']
                if ready_packages:
                    target_pkg = max(ready_packages, key=lambda p: p['id'])
                    pkg_id = target_pkg['id']
                    
                    print(f"BÀI TẬP [{pid}] ⏩ Revision này đã có package (ID: {pkg_id}). Đang tải ngay lập tức...")
                    
                    # TẢI LUÔN NGAY TẠI PHA 1 / DOWNLOAD IMMEDIATELY IN PHASE 1
                    os.makedirs(folder, exist_ok=True)
                    zip_path = os.path.join(folder, f"{pid}_standard_package.zip")
                    res_dl = download_package_zip(pid, pkg_id, zip_path)
                    
                    if res_dl.get('status') == 'OK':
                        print(f"   -> ✅ Lưu thành công tại / Successfully saved at: {zip_path}")
                        tasks[pid] = {'state': 'DOWNLOADED'} # Đánh dấu đã tải / Mark as downloaded
                    else:
                        print(f"   -> ❌ ERROR tải / Download error: {res_dl.get('comment')}")
                        tasks[pid] = {'state': 'FAILED'}
                else:
                    print(f"BÀI TẬP [{pid}] ❌ ERROR: Server báo đã có package nhưng không tìm thấy bản READY Standard nào. / Server reports existing package but no READY Standard version found.")
                    tasks[pid] = {'state': 'FAILED'}
            else:
                print(f"BÀI TẬP [{pid}] ❌ ERROR Request Build: {res_build.get('comment', '')}")
                tasks[pid] = {'state': 'FAILED'}

    print("\n=== PHA 2: CHỜ POLYGON BUILD (POLLING) ===")
    for attempt in range(30):
        polling_pids = [pid for pid, data in tasks.items() if data['state'] == 'POLLING']
        
        if not polling_pids:
            break 
            
        print(f"-> Đang chờ {len(polling_pids)} bài tập hoàn thành... (Lần thử {attempt + 1}/30) / Waiting for {len(polling_pids)} problems to finish... (Attempt {attempt + 1}/30)")
        time.sleep(10)
        
        for pid in polling_pids:
            res_pkgs = call_polygon_api('problem.packages', {'problemId': pid})
            new_packages = [p for p in res_pkgs.get('result', []) if p['id'] > tasks[pid]['old_max_id']] if res_pkgs.get('status') == 'OK' else []
            
            if new_packages:
                target_pkg = max(new_packages, key=lambda p: p['id'])
                state = target_pkg.get('state')
                
                if state == 'READY':
                    print(f"BÀI TẬP [{pid}] ✅ Build hoàn tất / Build finished (Package ID: {target_pkg['id']}).")
                    tasks[pid]['state'] = 'READY'
                    tasks[pid]['pkg_id'] = target_pkg['id']
                elif state == 'FAILED':
                    print(f"BÀI TẬP [{pid}] ❌ Build FAILED trên server Polygon.")
                    tasks[pid]['state'] = 'FAILED'

    print("\n=== PHA 3: TIẾN HÀNH DOWNLOAD CÁC GÓI MỚI BUILD ===")
    for pid, data in tasks.items():
        if data['state'] == 'READY':
            folder = data['folder']
            pkg_id = data['pkg_id']
            
            os.makedirs(folder, exist_ok=True)
            zip_path = os.path.join(folder, f"{pid}_standard_package.zip")
            
            print(f"BÀI TẬP [{pid}] 🐢 Đang tải package mới build / Downloading newly built package {pkg_id}...")
            res_dl = download_package_zip(pid, pkg_id, zip_path)
            
            if res_dl.get('status') == 'OK':
                print(f"   -> ✅ Lưu thành công tại / Successfully saved at: {zip_path}")
            else:
                print(f"   -> ❌ ERROR tải / Download error: {res_dl.get('comment')}")
                
        elif data['state'] == 'POLLING':
            print(f"BÀI TẬP [{pid}] ⏰ Timeout: Quá 5 phút nhưng server chưa build xong. Bỏ qua tải. / Over 5 minutes but server hasn't finished building. Skipping download.")
# ==========================================
# THỰC THI CHÍNH
# ==========================================
if __name__ == '__main__':
    try:
        with open(API_PATH, 'r') as f:
            data = json.load(f)
            API_KEY = data.get("apiKey")
            API_SECRET = data.get("apiSecret")
        print()
        print(f"Found API Key: {API_KEY}")
        print(f"Found API Secret: {API_SECRET[:10] + '*' * (len(API_SECRET) - 10)}")
    except FileNotFoundError:
        print("API đâu ?")
        exit()

    try:
        problem_data = list(zip(
            Problems_data.internal_names, Problems_data.names, Problems_data.sols,
            Problems_data.texs, Problems_data.generators, Problems_data.scripts, Problems_data.folders
        ))

        # ==========================================
        # CÁC CÔNG TẮC ĐIỀU KHIỂN QUY TRÌNH
        # ==========================================
        ENABLE_PHASE_1_UPLOAD = False
        ENABLE_PHASE_2_TESTS  = False 
        ENABLE_PHASE_3_COMMIT = False
        ENABLE_PHASE_4_BUILD  = True
        
        # Biến lưu trữ các bài tập bị thay đổi cần commit
        pids_to_commit = {}
        working_pids = {}

        # PHA 1: Upload Tài nguyên
        if ENABLE_PHASE_1_UPLOAD:
            working_pids = batch_upload_resources(problem_data)
            pids_to_commit.update(working_pids)
        else:
            working_pids = load_local_cache()
            
        # PHA 2: Chạy Script sinh test
        if ENABLE_PHASE_2_TESTS and working_pids:
            tested_pids = batch_setup_tests(problem_data, working_pids)
            pids_to_commit.update(tested_pids)
            
        # PHA 3: Commit 1 lần duy nhất cho những bài đã bị tác động
        if ENABLE_PHASE_3_COMMIT and pids_to_commit:
            batch_commit(pids_to_commit)

        # PHA 4: Build package và Download
        if ENABLE_PHASE_4_BUILD:
            # Thu thập danh sách (pid, folder) để tải về dựa trên những bài đã hoàn thành
            download_list = [(pid, folder) for int_name, _, _, _, _, _, folder in problem_data if (pid := working_pids.get(int_name))]
            if download_list:
                build_and_download_packages(download_list)
            
    except NameError as e:
        print(f"Lỗi: {e}. Vui lòng kiểm tra lại class Problems_data.")