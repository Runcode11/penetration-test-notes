#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL 服务探测脚本（命令行 + 多线程版）

相比 scan_mysql.py，这一版做了三点升级：
    1. 用 argparse 改造成命令行工具：主机、端口、账号字典、密码字典、线程数等全部由命令行参数传入；
    2. 用 ThreadPoolExecutor 多线程并发，把"一个账号密码试一次"的任务同时跑，速度提升明显；
    3. 增加存活服务统计、进度显示、命中后提前停止、结果导出 CSV 等实用功能。

常用命令：
    # 最简用法（默认账号 root/admin，默认密码 root/admin/123456）
    python scan_mysql_cli.py -H 192.168.33.41

    # 自定义端口、账号、密码、线程数
    python scan_mysql_cli.py -H 192.168.33.41 -P 3306 -u root,admin -p root,123456 -t 20

    # 字典写在文件里（一行一个），扫描多个主机并导出结果
    python scan_mysql_cli.py -H hosts.txt -u users.txt -p pass.txt -t 50 -o result.csv

    # 查看全部参数说明
    python scan_mysql_cli.py -h

注意：请仅对自己拥有或已授权的环境（本地/内网靶场）使用。
"""

import argparse
import csv
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pymysql

# MySQL 返回这些错误码，说明"服务器是活的，只是没给权限"，可以用来判断服务是否存在：
#   1044 权限不足    1045 账号或密码错误    1130 该主机不允许连接
SERVICE_REACHABLE_CODES = {1044, 1045, 1130}

# 命令行不指定账号/密码时使用的默认字典
DEFAULT_USERS = ["root", "admin"]
DEFAULT_PASSWORDS = ["root", "admin", "123456"]


# --------------------------------------------------------------------------- #
#                              一、命令行参数解析                              #
# --------------------------------------------------------------------------- #
def build_parser():
    """构造参数解析器。所有可调项都集中在这里，方便查看和修改。"""
    parser = argparse.ArgumentParser(
        prog="scan_mysql_cli.py",
        description="MySQL 服务探测 / 弱口令检查工具（命令行 + 多线程）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python scan_mysql_cli.py -H 192.168.33.41\n"
            "  python scan_mysql_cli.py -H 192.168.33.41 -u root,admin -p root,123456 -t 20\n"
            "  python scan_mysql_cli.py -H hosts.txt -u users.txt -p pass.txt -t 50 -o result.csv\n"
        ),
    )

    # 目标主机：必填。支持逗号分隔的多个 IP，也支持传入一个文件名
    parser.add_argument(
        "-H", "--host", required=True,
        help="目标主机，多个用逗号分隔；也可以直接给一个文件路径（一行一个）",
    )
    # 端口：MySQL 默认 3306
    parser.add_argument(
        "-P", "--port", type=int, default=3306,
        help="目标端口，默认 3306",
    )
    # 账号字典：逗号分隔或文件
    parser.add_argument(
        "-u", "--user", default=",".join(DEFAULT_USERS),
        help="用户名列表，逗号分隔；也可以给文件路径（一行一个），默认 root,admin",
    )
    # 密码字典：逗号分隔或文件
    parser.add_argument(
        "-p", "--password", default=",".join(DEFAULT_PASSWORDS),
        help="密码列表，逗号分隔；也可以给文件路径（一行一个），默认 root,admin,123456",
    )
    # 线程数：同时进行的登录尝试数量
    parser.add_argument(
        "-t", "--threads", type=int, default=10,
        help="并发线程数，默认 10；线程越多越快，但太大会被目标限速或拖慢本机",
    )
    # 单次连接超时时间（秒）
    parser.add_argument(
        "--timeout", type=float, default=3.0,
        help="单次连接超时时间（秒），默认 3",
    )
    # 默认找到第一组可用凭据就停，加 --all 则把字典全部跑完
    parser.add_argument(
        "--all", action="store_true",
        help="找到可用凭据后仍继续扫描全部字典（默认命中即停）",
    )
    # 输出文件
    parser.add_argument(
        "-o", "--output",
        help="把成功的凭据导出到 CSV 文件",
    )
    # 详细模式：打印每一次失败的尝试
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="显示每一次失败的尝试（默认只显示进度和成功结果）",
    )
    return parser


def load_items(raw, default):
    """
    把命令行传入的字符串解析成列表，支持两种写法：
        "root,admin"     -> ["root", "admin"]
        "users.txt"      -> 逐行读取文件，跳过空行和 # 注释行
    解析结果为空时回退到默认字典。
    """
    items = []

    if raw and os.path.isfile(raw):
        # 传进来的是一个存在的文件路径，按行读取
        with open(raw, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    items.append(line)
    elif raw:
        # 按逗号切分
        items = [x.strip() for x in raw.split(",") if x.strip()]

    return items or list(default)


# --------------------------------------------------------------------------- #
#                              二、单次登录尝试                                #
# --------------------------------------------------------------------------- #
def try_login(host, port, user, password, timeout):
    """
    用一组账号密码尝试连接目标 MySQL，返回一个字典：
        ok        : 是否登录成功
        code      : MySQL 错误码（成功时为 None）
        reachable : 是否探测到 MySQL 服务（认证失败也说明服务是存在的）
        info      : 错误描述，便于调试

    这个函数会被多个线程同时调用，所以内部不能修改任何共享变量，
    只做"发请求 -> 返回结果"，线程安全交给调用方处理。
    """
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8",
            connect_timeout=timeout,  # 建立连接的超时时间
            read_timeout=timeout,     # 读取数据的超时时间
            write_timeout=timeout,    # 发送数据的超时时间
        )
    except pymysql.err.OperationalError as e:
        # 网络不通、认证失败、主机被拒绝等，pymysql 都会抛 OperationalError
        code = e.args[0] if e.args else None
        info = e.args[1] if len(e.args) > 1 else str(e)
        return {
            "ok": False,
            "code": code,
            "reachable": code in SERVICE_REACHABLE_CODES,
            "info": f"[{code}] {info}",
        }
    except Exception as e:
        # 兜底：任何意外异常都只影响当前这一组尝试，不能让整个程序崩掉
        return {"ok": False, "code": None, "reachable": False, "info": repr(e)}
    else:
        # 连接成功一定要关闭，否则会把服务端的连接数占满
        conn.close()
        return {"ok": True, "code": None, "reachable": True, "info": "login success"}


# --------------------------------------------------------------------------- #
#                                 三、主流程                                   #
# --------------------------------------------------------------------------- #
def main():
    parser = build_parser()
    args = parser.parse_args()

    # ---------------------------- 1. 参数校验 ---------------------------- #
    if args.threads < 1:
        parser.error("--threads 必须大于 0")
    if args.timeout <= 0:
        parser.error("--timeout 必须大于 0")
    if not 0 < args.port < 65536:
        parser.error("--port 必须是 1-65535 之间的整数")

    # ------------------------- 2. 组装扫描任务 -------------------------- #
    hosts = load_items(args.host, [])
    users = load_items(args.user, DEFAULT_USERS)
    passwords = load_items(args.password, DEFAULT_PASSWORDS)

    if not hosts:
        parser.error("没有解析到任何目标主机，请检查 -H 参数")

    # 任务 = 主机 × 账号 × 密码，每个任务就是一次登录尝试
    targets = [(host, user, password) for host in hosts for user in users for password in passwords]
    total = len(targets)

    # ---------------------------- 3. 打印信息 ---------------------------- #
    print("=" * 64)
    print(f"目标主机 : {', '.join(hosts)}")
    print(f"目标端口 : {args.port}")
    print(f"账号数量 : {len(users)}    密码数量 : {len(passwords)}")
    print(f"任务总数 : {total}（主机 × 账号 × 密码）")
    print(f"并发线程 : {args.threads}    单次超时 : {args.timeout}s")
    print("=" * 64)

    # ---------------------------- 4. 多线程扫描 -------------------------- #
    stop_event = threading.Event()  # 命中后置位，其它线程看到后就不再发起新请求
    found = []                      # 成功的凭据 (host, user, password)
    reachable = set()               # 探测到 MySQL 服务的主机
    finished = 0                    # 已完成的尝试次数（只在主线程累加，无需加锁）
    start_time = time.time()

    def worker(target):
        """线程池中执行的任务：先检查停止标志，再做一次登录尝试。"""
        if stop_event.is_set():
            return None  # 已经有结果了，直接跳过，省下一次网络请求
        host, user, password = target
        return try_login(host, args.port, user, password, args.timeout)

    # with 结束时会自动 shutdown 线程池，等待正在运行的任务收尾
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        # 提交所有任务；future 与 target 一一对应，方便取回结果时知道是哪组账号密码
        future_map = {pool.submit(worker, target): target for target in targets}

        # as_completed：谁先执行完就先处理谁，结果按完成顺序返回
        for future in as_completed(future_map):
            target = future_map[future]
            result = future.result()

            if result is None:      # 被 stop_event 跳过的任务
                continue

            finished += 1
            host, user, password = target

            if result["reachable"]:
                reachable.add(f"{host}:{args.port}")

            if result["ok"]:
                # 命中：记录并打印
                found.append(target)
                print(f"\n[+] 登录成功  {host}:{args.port}  用户名={user}  密码={password}")
                if not args.all:
                    # 默认命中即停：置位标志，让排在后面的任务快速返回
                    stop_event.set()
            elif args.verbose:
                print(f"[-] {host}:{args.port}  用户名={user}  密码={password}  失败：{result['info']}")

            # 进度显示（verbose 模式下会打乱排版，所以只在普通模式下显示）
            if not args.verbose and (finished % 10 == 0 or finished == total):
                print(f"\r进度：{finished}/{total}", end="", flush=True)

    if not args.verbose:
        print()  # 进度条后面补一个换行

    # ---------------------------- 5. 结果汇总 ---------------------------- #
    elapsed = time.time() - start_time
    print("=" * 64)
    print("扫描结束")
    print(f"  完成尝试 : {finished}/{total}")
    print(f"  总耗时   : {elapsed:.2f}s")
    print(f"  存活服务 : {', '.join(sorted(reachable)) if reachable else '无'}")

    if found:
        print(f"  成功凭据 : {len(found)} 组")
        for host, user, password in found:
            print(f"    - {host}:{args.port}  {user} / {password}")
    else:
        print("  成功凭据 : 未发现")
        if not reachable:
            print("  提示     : 没有任何主机返回 MySQL 响应，目标可能未开机、端口不对或被防火墙拦截")
    print("=" * 64)

    # ---------------------------- 6. 导出结果 ---------------------------- #
    if args.output and found:
        # utf-8-sig 带 BOM，用 Excel 打开不会中文乱码
        with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["host", "port", "user", "password"])
            for host, user, password in found:
                writer.writerow([host, args.port, user, password])
        print(f"结果已写入：{os.path.abspath(args.output)}")

    # 找到凭据返回 0，没找到返回 1，方便在脚本/管道里判断结果
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
