import pyaudio
import wave
import time
import threading
from whisper_online import *
import logging
import numpy as np


class MySTTModel:
    def __init__(self):
        # 配置日志记录
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # 配置参数
        self.language = "zh"
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.min_chunk = 2.0  # 最小处理时间间隔，单位：秒
        self.OUTPUT_WAV_FILE = "recorded_audio.wav"
        self.audio_instance = None  # pyaudio instance

        self.init_pyaudio()
        self.online = self.init_whisper()
        self.recording_event = threading.Event()
        self.record_thread = None
        self.transcription_thread = None
        self.transcription_results = []  # 用于存储转录结果的列表

    def init_pyaudio(self):
        # 初始化 PyAudio
        self.audio_instance = pyaudio.PyAudio()

        # 查找 PulseAudio 设备索引
        pulse_input = None
        pulse_output = None

        for i in range(self.audio_instance.get_device_count()):
            dev = self.audio_instance.get_device_info_by_index(i)
            if "pulse" in dev["name"].lower():
                if dev["maxInputChannels"] > 0:
                    pulse_input = dev["index"]
                if dev["maxOutputChannels"] > 0:
                    pulse_output = dev["index"]

        # 检查是否找到 PulseAudio 设备
        if pulse_input is None:
            print("未找到支持输入的 PulseAudio 设备，无法进行录音。")
            self.audio_instance.terminate()
            exit(1)

        if pulse_output is None:
            print("未找到支持输出的 PulseAudio 设备，无法进行播放。")
            self.audio_instance.terminate()
            exit(1)

        self.pulse_input = pulse_input
        self.pulse_output = pulse_output

    # 录音并保存为 WAV 文件的函数，将在子线程中运行
    def record_and_save_audio(self, pulse_input):
        wf = wave.open(self.OUTPUT_WAV_FILE, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self.audio_instance.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)

        stream = self.audio_instance.open(format=self.FORMAT,
                                          channels=self.CHANNELS,
                                          rate=self.RATE,
                                          input=True,
                                          input_device_index=pulse_input,
                                          frames_per_buffer=self.CHUNK)

        while self.recording_event.is_set():
            try:
                data = stream.read(self.CHUNK)
                wf.writeframes(data)
            except Exception as e:
                self.logger.error(f"录音过程中出现错误: {e}")

        wf.close()
        stream.stop_stream()
        stream.close()

    # 流式转录的函数，将在子线程中运行
    def stream_transcription(self):
        start = time.time()
        beg = 0
        end = 0

        while self.recording_event.is_set():
            try:
                now = time.time() - start
                if now < end + self.min_chunk:
                    time.sleep(self.min_chunk + end - now)
                end = time.time() - start
                self.logger.debug(f"!!! {beg} {end}")

                # 计算 beg 和 end 对应的帧数
                beg_frame = int(beg * self.RATE)
                end_frame = int(end * self.RATE)

                # 读取从 beg 到 end 内的音频数据进行处理
                with wave.open(self.OUTPUT_WAV_FILE, 'rb') as wf:
                    # 将文件指针移动到 beg 对应的位置
                    wf.setpos(beg_frame)
                    # 读取 end - beg 时间段内的帧数
                    audio_data = wf.readframes(end_frame - beg_frame)

                if audio_data:
                    # 将字节数据转换为 np.float32 类型
                    audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    # 进行归一化处理
                    audio_array /= np.iinfo(np.int16).max
                    self.online.insert_audio_chunk(audio_array)
                    o = self.online.process_iter()
                    result_text = o[2]
                    print(result_text, "###")
                    self.transcription_results.append(result_text)  # 将结果添加到列表中

                beg = end
                now = time.time() - start
                self.logger.debug(f"## last processed {end:.2f} s, now is {now:.2f}, the latency is {now - end:.2f}")

            except Exception as e:
                self.logger.error(f"转录过程中出现错误: {e}")

        # 处理最后的输出
        try:
            o = self.online.finish()
            result_text = o[2]
            print(result_text, "###")
            self.transcription_results.append(result_text)  # 将最后结果添加到列表中
            self.online.init()
        except Exception as e:
            self.logger.error(f"处理最后输出时出现错误: {e}")

    def init_whisper(self):
        # 初始化 Whisper 模型
        asr = FasterWhisperASR(self.language, "base")
        asr.use_vad()
        online = OnlineASRProcessor(asr)
        return online

    def start_recording(self):
        if not self.recording_event.is_set():
            self.recording_event.set()
            print("* 开始录音")
            self.record_thread = threading.Thread(target=self.record_and_save_audio, args=(self.pulse_input,))
            self.transcription_thread = threading.Thread(target=self.stream_transcription)
            self.record_thread.start()
            self.transcription_thread.start()

    def stop_recording(self):
        if self.recording_event.is_set():
            self.recording_event.clear()
            if self.record_thread:
                self.record_thread.join()
            if self.transcription_thread:
                self.transcription_thread.join()
            print("* 录音结束")

    def record_and_transcribe(self):
        self.transcription_results = []
        user_input = input("按回车键开始,再次按下停止录音: ")
        self.start_recording()

        user_input = input()
        self.stop_recording()

        # 将列表中的结果合并为一个字符串
        all_text = " ".join(self.transcription_results).replace(" ", "")
        return all_text