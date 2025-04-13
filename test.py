import pyaudio
import wave
import time
import threading
from thirdparty.whisper_streaming.whisper_online import *
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置参数
language = "zh"
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
min_chunk = 2.0  # 最小处理时间间隔，单位：秒
OUTPUT_WAV_FILE = "recorded_audio.wav"
audio_instance = None  # pyaudio instance


def init_pyaudio():
    # 初始化 PyAudio
    global audio_instance
    audio_instance = pyaudio.PyAudio()

    # 查找 PulseAudio 设备索引
    pulse_input = None
    pulse_output = None

    for i in range(audio_instance.get_device_count()):
        dev = audio_instance.get_device_info_by_index(i)
        if "pulse" in dev["name"].lower():
            if dev["maxInputChannels"] > 0:
                pulse_input = dev["index"]
            if dev["maxOutputChannels"] > 0:
                pulse_output = dev["index"]

    # 检查是否找到 PulseAudio 设备
    if pulse_input is None:
        print("未找到支持输入的 PulseAudio 设备，无法进行录音。")
        audio_instance.terminate()
        exit(1)

    if pulse_output is None:
        print("未找到支持输出的 PulseAudio 设备，无法进行播放。")
        audio_instance.terminate()
        exit(1)

    return (pulse_input, pulse_output)


# 录音并保存为 WAV 文件的函数，将在子线程中运行
def record_and_save_audio(recording_event, pulse_input):
    global audio_instance
    wf = wave.open(OUTPUT_WAV_FILE, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio_instance.get_sample_size(FORMAT))
    wf.setframerate(RATE)

    stream = audio_instance.open(format=FORMAT,
                                 channels=CHANNELS,
                                 rate=RATE,
                                 input=True,
                                 input_device_index=pulse_input,
                                 frames_per_buffer=CHUNK)

    while recording_event.is_set():
        try:
            data = stream.read(CHUNK)
            wf.writeframes(data)
        except Exception as e:
            logger.error(f"录音过程中出现错误: {e}")

    wf.close()
    stream.stop_stream()
    stream.close()


# 流式转录的函数，将在子线程中运行
def stream_transcription(recording_event, online):
    start = time.time()
    beg = 0
    end = 0

    while recording_event.is_set():
        try:
            now = time.time() - start
            if now < end + min_chunk:
                time.sleep(min_chunk + end - now)
            end = time.time() - start
            logger.debug(f"!!! {beg} {end}")

            # 计算 beg 和 end 对应的帧数
            beg_frame = int(beg * RATE)
            end_frame = int(end * RATE)

            # 读取从 beg 到 end 内的音频数据进行处理
            with wave.open(OUTPUT_WAV_FILE, 'rb') as wf:
                # 将文件指针移动到 beg 对应的位置
                wf.setpos(beg_frame)
                # 读取 end - beg 时间段内的帧数
                audio_data = wf.readframes(end_frame - beg_frame)

            if audio_data:
                # 将字节数据转换为 np.float32 类型
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                # 进行归一化处理
                audio_array /= np.iinfo(np.int16).max
                online.insert_audio_chunk(audio_array)
                o = online.process_iter()
                print(o[2], "###")

            beg = end
            now = time.time() - start
            logger.debug(f"## last processed {end:.2f} s, now is {now:.2f}, the latency is {now - end:.2f}")

        except Exception as e:
            logger.error(f"转录过程中出现错误: {e}")

    # 处理最后的输出
    try:
        o = online.finish()
        print(o[2], "###")
        online.init()
    except Exception as e:
        logger.error(f"处理最后输出时出现错误: {e}")

def init_whisper():
    # 初始化 Whisper 模型
    asr = FasterWhisperASR(language, "base")
    asr.use_vad()
    online = OnlineASRProcessor(asr)
    return online

if __name__ == "__main__":
    # 用于在主线程和子线程间共享录音状态的变量
    (pulse_input, pulse_output) = init_pyaudio()
    recording_event = threading.Event()

    online = init_whisper()    

    record_thread = None
    transcription_thread = None

    while True:
        user_input = input("按回车键开始/停止录音，输入 'q' 退出程序: ")
        if user_input.lower() == 'q':
            if record_thread and record_thread.is_alive():
                recording_event.clear()
                record_thread.join()
            if transcription_thread and transcription_thread.is_alive():
                recording_event.clear()
                transcription_thread.join()
            break
        if not recording_event.is_set():
            recording_event.set()
            print("* 开始录音")
            record_thread = threading.Thread(target=record_and_save_audio, args=(recording_event, pulse_input))
            transcription_thread = threading.Thread(target=stream_transcription, args=(recording_event, online))
            record_thread.start()
            transcription_thread.start()
        else:
            recording_event.clear()
            if record_thread:
                record_thread.join()
            if transcription_thread:
                transcription_thread.join()
            print("* 录音结束")
