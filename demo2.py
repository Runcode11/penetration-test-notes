import requests
import warnings

warnings.filterwarnings("ignore")

TIMEOUT = 5  # 超时秒数，抽成常量方便改


def dirb(url):
    # 保证结尾有 /，否则拼出来是 xxx.comadmin 这种错误地址
    if not url.endswith('/'):
        url += '/'

    # 指定 utf-8 编码，防止字典里有中文时读文件报错
    with open('scan/dir.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:        # 跳过空行
                continue

            full_url = url + line
            try:
                res = requests.get(
                    full_url,
                    timeout=(TIMEOUT, TIMEOUT),  # 连接超时、读取超时，各 5 秒
                    allow_redirects=False,       # 关键：不自动跟随 302
                    verify=False,
                )
                # 200 正常，302 重定向，都算目录存在
                if res.status_code in (200, 302):
                    print(f"[+] {res.status_code} {full_url}")
            except requests.exceptions.Timeout:
                print(f"[-] 超时：{full_url}")
            except Exception:
                print(f"[-] 失败：{full_url}")