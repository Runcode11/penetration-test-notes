# 导入 csv 模块，用于以表格形式读写用户数据
import csv
# 导入 os 模块，用于判断文件是否存在
import os

# 用户数据文件名（相对当前运行目录），整个程序共用这一个常量
FILE_NAME = 'users.csv'


def init_file():
    """如果文件不存在，则创建包含表头的文件"""
    if not os.path.exists(FILE_NAME):
        with open(FILE_NAME, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['username', 'password', 'phone'])
            f.flush()  # 确保立即写入磁盘


def read_all_users():
    """读取所有用户数据"""
    users = []
    if os.path.exists(FILE_NAME):
        # 使用 utf-8-sig 读取，兼容可能存在的 BOM 头
        with open(FILE_NAME, mode='r', newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 清洗数据：去除键和值两端的空格
                clean_row = {k.strip(): v.strip() for k, v in row.items() if k is not None}
                users.append(clean_row)
    return users


def write_all_users(users):
    """重写整个文件（用于密码修改）"""
    with open(FILE_NAME, mode='w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['username', 'password', 'phone']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(users)
        f.flush()


def register():
    """注册功能"""
    print("\n--- 注册 ---")
    users = read_all_users()
    username = input("请输入新的用户名: ").strip()

    for u in users:
        if u.get('username') == username:
            print("❌ 注册失败：该用户名已被注册！")
            return

    password = input("请输入密码: ").strip()
    phone = input("请输入手机号码（用于找回密码）: ").strip()

    with open(FILE_NAME, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([username, password, phone])
        f.flush()  # 强制刷新缓冲区，确保数据写入文件

    print(f"✅ 注册成功！欢迎你，{username}")


def login():
    """登录功能"""
    print("\n--- 登录 ---")
    users = read_all_users()

    # 调试打印：看看实际读到了什么（测试没问题后可以删掉这两行）
    # print(f"DEBUG: 当前读取到的所有用户 -> {users}")

    username = input("请输入用户名: ").strip()
    password = input("请输入密码: ").strip()

    for u in users:
        # 使用 .get() 更安全，防止键名不匹配报错
        if u.get('username') == username:
            if u.get('password') == password:
                print(f"✅ 登录成功！欢迎回来，{username}")
                return True
            else:
                print("❌ 登录失败：密码错误！")
                return False

    print("❌ 登录失败：用户不存在！")
    return False


def forgot_password():
    """忘记密码功能（手机号验证）"""
    print("\n--- 找回密码 ---")
    users = read_all_users()
    username = input("请输入您的用户名: ").strip()

    for u in users:
        if u.get('username') == username:
            input_phone = input("请输入该账号绑定的手机号码: ").strip()

            if input_phone == u.get('phone'):
                new_password = input("验证成功！请输入新密码: ").strip()
                u['password'] = new_password
                write_all_users(users)
                print("✅ 密码重置成功！请重新登录。")
            else:
                print("❌ 手机号码验证失败，无法重置密码。")
            return

    print("❌ 找不到该用户。")


def main():
    # 启动时先确保数据文件存在（不存在就创建并写入表头）
    init_file()

    # 主循环：每次都重新打印菜单，直到用户选择退出
    while True:
        print("\n" + "=" * 20)
        print(" 用户管理系统")
        print(" 1. 登录")
        print(" 2. 注册")
        print(" 3. 忘记密码")
        print(" 4. 退出")
        print("=" * 20)

        choice = input("请选择操作 (1-4): ").strip()

        if choice == '1':
            login()
        elif choice == '2':
            register()
        elif choice == '3':
            forgot_password()
        elif choice == '4':
            print("👋 退出系统，再见！")
            break
        else:
            print("⚠️ 无效的输入，请输入 1-4 之间的数字。")


if __name__ == '__main__':
    main()