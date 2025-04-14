import traceback
import binascii
import threading
import queue
import time
# import subprocess
# import os

from thirdparty.whisper_streaming.MySTT import *
from thirdparty.Edge_TTS.Edge_TTS import *
from thirdparty.LLM_Client.LLM_Client import *

stt_model = MySTTModel()
# stt_model = None
tts_model = Edge_TTS()
speech_queue = queue.Queue()
client = LLMClient(
    base_url="http://localhost:3000/api/search",
    model="llama3.1:8b",
    provider="ollama",
    engine="TAVILY"
)

def need_to_skip(content: str):
    # 这里用一个比较讨巧的手段，排除掉deepseek的<think>和输入提示符>
    if not content: # 自动过滤空串 
        return True
    return len(content) <= 10 and (content.startswith('<') or content.endswith('>'))

def speak_out():
    """
    调用内置的tts引擎来将生成内容说出来，并记录执行时间
    """
    tts_model.start_playback()
    while True:
        try:
            content = speech_queue.get_nowait()
            if content is None:
                break
            content = content.strip("\n").strip()
            if need_to_skip(content):
                continue  # 排除一些无需说出的内容
            tts_model.generate_and_read_audio(content)
        except queue.Empty:
            time.sleep(0.3)  # 短暂休眠，避免 CPU 占用过高
    tts_model.stop_playback()

def STT_input():
    return stt_model.record_and_transcribe()


def get_output(question):
    # 初始化 LLMClient 实例

    # 启动语音播报线程
    speak_thread = threading.Thread(target=speak_out)
    speak_thread.start()

    output_str = ""  # 用于记录输出内容
    speech_buffer = ""  # 语音播报缓冲区

    # 从 LLMClient 获取流式输出
    for chunk in client.post(question):
        output_str += chunk
        speech_buffer += chunk
        print(chunk, end='', flush=True)

        if '\n' in chunk:
            # 当遇到换行符时，将语音播报缓冲区内容放入队列
            if speech_buffer:
                speech_queue.put(speech_buffer)
                speech_buffer = ""

    # 处理剩余的语音播报缓冲区内容
    if speech_buffer:
        speech_queue.put(speech_buffer)

    # 发送结束信号
    speech_queue.put(None)
    speak_thread.join()

    return output_str


def multi_round_interaction():
    try:
        while True:
            # 获取用户输入的问题
            if stt_model:
                input_text = STT_input()
            else:
                print("> ", end="")
                input_text = input()
            if input_text == "exit":
                break

            # 编码输入文本为字节
            # input_bytes = (input_text + '\n').encode('utf-8')
            # print("转换后的字节序列为:", input_bytes)

            # 向子进程的标准输入发送完整的对话历史
            # process.stdin.write(input_bytes)
            # process.stdin.flush()

            get_output(input_text)

        # 关闭子进程
        # process.stdin.close()
        # process.wait()

    except Exception as e:
        traceback.print_exc()


# def init_llm():
#     command = [
#         "./build/bin/llama-cli",  # llama-cli 可执行文件的路径
#         "-m", "DeepSeek-R1-Distill-Qwen-1.5B/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",  # 模型文件路径
#         "-t", "4",  # 经测试，4线程表现最好，8线程效果甚至不如单线程。
#         "-cnv"  # interactive
#     ]
#     try:
#         # 启动子进程
#         global process
#         process = subprocess.Popen(
#             command,
#             stdin=subprocess.PIPE,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             # 去掉 text=True，以字节形式进行输入输出
#             env={"PARENT_PID": str(os.getpid())}
#         )
#         get_output()
#     except Exception as e:
#         traceback.print_exc()


def init_stt_model():
    # has put code in global area
    # load whisper_model
    # global stt_model
    # stt_model = whisper.load_model("small")
    pass

# 启动多轮交互
if __name__ == '__main__':
    # init_llm()
    init_stt_model()
    multi_round_interaction()