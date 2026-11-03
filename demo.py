import time
import threading

class startThread(threading.Thread):
    def run(self):
        print("开始了")

class ingThread(threading.Thread):
    def run(self):
        print("进行中")
        time.sleep(3)

class endThread(threading.Thread):
    def run(self):
        print("结束了")

if __name__ == "__main__":
    print("启动启动启动")

    t1 = startThread()
    t2 = ingThread()
    t3 = endThread()

    #启动线程
    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    print("关闭关闭关闭")

