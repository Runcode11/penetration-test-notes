from socket import socket, AF_INET, SOCK_STREAM

def server(host="0.0.0.0",port=6767):
    try:
        socket_server_tcp = socket(AF_INET, SOCK_STREAM)
        socket_server_tcp.bind((host, port))
        socket_server_tcp.listen(5)
        print(f"[+] 服务端启动成功, {host}:{port}")

        socket_client_tcp,address = socket_server_tcp.accept()
        print(f"[+] 客户端连接成功, {address}")

        while True:
            data = socket_client_tcp.recv(1024)
            if not data:
                continue
            print(f"[+] 客户端发送数据: {data.decode('utf-8')}")
            server_data = input("[+] 请输入要发送给客户端的数据: ")
            if server_data == "exit":
                print("退出服务")
                socket_client_tcp.close()
                exit()
            elif not server_data:
                server_data = "未输入数据"
            else:
                socket_client_tcp.send(server_data.encode('utf-8'))
        socket_client_tcp.close()
        socket_server_tcp.close()
    except Exception as e:
        print(f"[-] 服务端启动失败, {e}")

if __name__ == "__main__":
    server()