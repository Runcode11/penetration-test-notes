import pymysql
conn = pymysql.connect(
    host="192.168.33.41",  # 数据库地址
    port=3306,  # 数据库端口
    user="root",  # 数据库账户
    password="tian2004",  # 数据库密码
    database="woniutest",  # 连接数据库
    charset="utf8",  # 设置编码
    connect_timeout=3,  # 连接超时
)