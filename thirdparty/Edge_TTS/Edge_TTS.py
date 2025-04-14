import asyncio
import os
import pyaudio
from pydub import AudioSegment
import subprocess
import queue
import threading

class Edge_TTS:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.voice = "zh-CN-YunyangNeural"
        self.audio_queue = queue.Queue()
        self.play_thread = None

    def start_playback(self):
        """开启放音，用pyaudio创建一个输出stream并启动播放线程"""
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=24000,
                                  output=True)
        self.play_thread = threading.Thread(target=self.play_audio)
        self.play_thread.start()

    def stop_playback(self):
        """关闭stream并等待播放线程完成"""
        self.audio_queue.put(None)  # 放入结束标志
        if self.play_thread:
            self.play_thread.join()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.stream = None

    def generate_and_read_audio(self, txt_to_speak):
        """生成并读取音频"""
        try:
            # 生成唯一的临时文件名
            temp_file = f"temp_{hash(txt_to_speak)}.wav"
            # 使用 edge-tts 生成 wav 文件
            subprocess.run([
                'edge-tts',
                '--text', txt_to_speak,
                '--voice', self.voice,
                '--write-media', temp_file
            ], check=True)

            # 使用 AudioSegment 读取音频文件
            audio = AudioSegment.from_file(temp_file)

            # 将音频数据块放入队列
            for chunk in audio[::10]:  # 每次读取 10 毫秒的数据块
                data = chunk.raw_data
                self.audio_queue.put(data)

        except subprocess.CalledProcessError as e:
            print(f"edge-tts 命令执行出错: {e}")
        except Exception as e:
            print(f"读取音频时出现错误: {e}")
        finally:
            # 删除临时生成的 wav 文件
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def play_audio(self):
        """播放音频的线程函数"""
        while True:
            data = self.audio_queue.get()
            if data is None:  # 遇到结束标志
                break
            self.stream.write(data)

    def speak_out(self, txt_to_speak):
        """处理单个文本字符串的音频生成与读取"""
        self.generate_and_read_audio(txt_to_speak)