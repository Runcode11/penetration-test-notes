from socket import socket, AF_INET, SOCK_STREAM

def client(host,port):
    try:
        socket_client_tcp = socket(AF_INET, SOCK_STREAM)
        socket_client_tcp.connect((host, port))
        print(f"[+] 客户端启动成功, {host}:{port}")
        while True:
            data_client = input("[+] 请输入要发送给服务端的数据: ")
            if data_client =="exit":
                print("退出客户端")
                socket_client_tcp.close()
                exit()
            elif not data_client:
                data_client = "未输入数据"

            socket_client_tcp.send(data_client.encode('utf-8'))
            data_server = socket_client_tcp.recv(1024)
            if not data_server:
                continue
            print(f"[+] 服务端发送数据: {data_server.decode('utf-8')}")
        socket_client_tcp.close()
    except Exception as e:
        print(f"[-] 客户端启动失败, {e}")

if __name__ == "__main__":
    client("192.168.33.31",6767)