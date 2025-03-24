import sys
import whisper
import subprocess
import os
import traceback
import binascii
import time

stt_model = None

# 定义保存录音文件的目录
save_directory = '/data/data/com.termux/files/home/shared/'


def start_recording(file_path):
    """
    开始录音的函数
    :param file_path: 录音文件保存的路径
    """
    try:
        # 执行 Termux 录音命令，指定保存为 WAV 格式
        subprocess.Popen(['termux-microphone-record', '-f', file_path])
        print("录音已开始")
    except Exception as e:
        print(f"开始录音时出错: {e}")


def stop_recording():
    """
    停止录音的函数
    """
    try:
        # 执行 Termux 停止录音命令
        subprocess.run(['termux-microphone-record', '-q'])
        print("录音已停止")
    except Exception as e:
        print(f"停止录音时出错: {e}")


def STT(audio_file_path: str):
    start_time = time.time()
    print("start transcribe:")
    result = stt_model.transcribe(audio_file_path, initial_prompt="以下是普通话的句子。")
    print("get result:", result["text"])
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"STT 函数执行时间: {execution_time:.2f} 秒")
    return result["text"]


def STT_input():
    input("按下Enter以开始录音")
    timestamp = int(time.time())
    file_name = f'recorded_audio_{timestamp}.wav'
    file_path = os.path.join(save_directory, file_name)
    start_recording(file_path)
    input("再次按下Enter停止录音...")
    stop_recording()
    print(f"录音文件已保存为 {file_path}")
    return STT(file_path)


def get_output():
    start_time = time.time()
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

    end_time = time.time()
    execution_time = end_time - start_time
    print(f"get_output 函数执行时间: {execution_time:.2f} 秒")


def multi_round_interaction():
    try:
        while True:
            # 获取用户输入的问题
            if stt_model:
                input_text = STT_input()
            else:
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
        "-m", "DeepSeek-R1-Distill-Qwen-1.5B/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",  # 模型文件路径
        "-t", "4", # 经测试，4线程表现最好，8线程效果甚至不如单线程。
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
            env={"PARENT_PID": str(os.getpid())}
        )
        get_output()
        # print("out of here")
    except Exception as e:
        traceback.print_exc()


def init_stt_model():
    # load whisper_model
    global stt_model
    stt_model = whisper.load_model("small")


# 启动多轮交互
if __name__ == '__main__':
    init_llm()
    init_stt_model()
    multi_round_interaction()