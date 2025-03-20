import subprocess
import os
import traceback
import binascii

def get_output():
    import fcntl

    fd = process.stdout.fileno()  # 获取文件描述符
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)  # 获取当前的文件状态标志
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)  # 设置为非阻塞模式

    buffer = b''  # 初始化缓冲区
    while True:
        try:
            chunk = process.stdout.read(1)  # 逐字节读取
            if not chunk:
                continue

            buffer += chunk
            try:
                decoded = buffer.decode('utf-8')
                hex_buffer = binascii.hexlify(buffer).decode('ascii')
                # print(f"Decoded successfully, buffer bytes: {hex_buffer}")
                # 检查是否读取到 U+f8ff
                if decoded == '\uf8ff':
                    break
                print(decoded, end='', flush=True)
                buffer = b''  # 清空缓冲区
            except UnicodeDecodeError:
                # 继续累积字节
                continue
        except Exception as e:
            traceback.print_exc()
            break

def multi_round_interaction():
    try:
        while True:
            # 获取用户输入的问题
            input_text = input()
            if input_text == "exit":
                break

            # 编码输入文本为字节
            input_bytes = (input_text + '\n').encode('utf-8')
            # print("转换后的字节序列为:", input_bytes)

            # 向子进程的标准输入发送完整的对话历史
            process.stdin.write(input_bytes)
            process.stdin.flush()

            get_output()

        # 关闭子进程
        process.stdin.close()
        process.wait()

    except Exception as e:
        traceback.print_exc()

def init_llm():
    command = [
        "./build/bin/llama-cli",  # llama-cli 可执行文件的路径
        "-m", "DeepSeek-R1-Distill-Qwen-7B/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",  # 模型文件路径
        "-cnv"  # interactive
    ]
    try:
        # 启动子进程
        global process
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # 去掉 text=True，以字节形式进行输入输出
            # bufsize=1,  # 设置为行缓冲，确保输出及时刷新
            env={"PARENT_PID": str(os.getpid())}
        )
        get_output()
        # print("out of here")
    except Exception as e:
        traceback.print_exc()

# 启动多轮交互
if __name__ == '__main__':
    init_llm()
    multi_round_interaction()
