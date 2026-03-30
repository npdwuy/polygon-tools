import os

ids_string = "" 

base_dir = "D:\c++\work\Contest\HSG10-CSP-2025"
inner_name = "hsg10csp25-"
problem_name = "HSG 10 CSP - 2025 - "
statements_url = "https://drive.google.com/file/d/1MR4rMLY4f3iwwx6oeQfk2OKJN6z0Gxtx/view?usp=drive_link"

# Danh sách các thư mục muốn bỏ qua (viết thường để dễ so sánh)
ignore_dirs = {"test", "tests", "template", "scripts"}
use_dirs = {""}

# Lọc: Phải là thư mục + Không bắt đầu bằng '.' + Không nằm trong danh sách bỏ qua
problems = [
    f for f in os.listdir(base_dir) 
    if os.path.isdir(os.path.join(base_dir, f)) 
    and not f.startswith('.') 
    and f.lower() not in ignore_dirs
    # and f.lower() in use_dirs
]

# Tự động sinh các danh sách
internal_names = [f"{inner_name}{p.lower()}" for p in problems]
names = [f"{problem_name}{p}" for p in problems]
contents = [r"\href{" + statements_url + "}{Đề bài}" for _ in problems]

folders =  [f"{base_dir}/{p}" for p in problems]
sols = [f"{directory}/main.cpp" for directory in folders]
scripts = [f"{directory}/script.txt" for directory in folders]
generators = [f"{directory}/generator.cpp" for directory in folders]

# Kiểm tra kết quả
if __name__ == "__main__":
    print(f"Danh sách {len(problems)} bài hợp lệ: {problems}")
