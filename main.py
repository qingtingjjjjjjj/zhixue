import urllib.request
from urllib.parse import urlparse
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import socket
import time
from datetime import datetime, timezone, timedelta
import random


# 读取文本方法
def read_txt_to_array(file_name):
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            lines = [line.strip() for line in lines]
            return lines
    except FileNotFoundError:
        print(f"File '{file_name}' not found.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


# 准备支持 m3u 格式
def get_url_file_extension(url):
    # 解析 URL
    parsed_url = urlparse(url)
    # 获取路径部分
    path = parsed_url.path
    # 提取文件扩展名
    extension = os.path.splitext(path)[1]
    return extension


def convert_m3u_to_txt(m3u_content):
    # 分行处理
    lines = m3u_content.split('\n')
    txt_lines = []
    # 临时变量用于存储频道名称
    channel_name = ""
    for line in lines:
        # 过滤掉 #EXTM3U 开头的行
        if line.startswith("#EXTM3U"):
            continue
        # 处理 #EXTINF 开头的行
        if line.startswith("#EXTINF"):
            # 获取频道名称（假设频道名称在引号后）
            channel_name = line.split(',')[-1].strip()
        # 处理 URL 行
        elif line.startswith("http") or line.startswith("rtmp") or line.startswith("p3p"):
            txt_lines.append(f"{channel_name},{line.strip()}")
    # 将结果合并成一个字符串，以换行符分隔
    return '\n'.join(txt_lines)


# 处理带 $ 的 URL，把 $ 之后的内容都去掉（包括 $ 也去掉）
def clean_url(url):
    last_dollar_index = url.rfind('$')  # 安全起见找最后一个 $ 处理
    if last_dollar_index != -1:
        return url[:last_dollar_index]
    return url


# 处理所有 URL
def process_url(url, timeout=10):
    try:
        # 打开 URL 并读取内容
        start_time = time.time()
        with urllib.request.urlopen(url, timeout=timeout) as response:
            # 以二进制方式读取数据
            data = response.read()
            # 将二进制数据解码为字符串
            text = data.decode('utf-8')

            # 处理 m3u 和 m3u8，提取 channel_name 和 channel_address
            if get_url_file_extension(url) == ".m3u" or get_url_file_extension(url) == ".m3u8":
                text = convert_m3u_to_txt(text)

            # 逐行处理内容
            lines = text.split('\n')
            channel_count = 0  # 初始化频道计数器
            for line in lines:
                if "#genre#" not in line and "," in line and "://" in line:
                    # 拆分成频道名和 URL 部分
                    parts = line.split(',')
                    channel_name = parts[0]  # 获取频道名称
                    channel_address = parts[1]  # 获取频道地址
                    # 处理带 # 号源 = 予加速源
                    if "#" not in channel_address:
                        yield channel_name, clean_url(channel_address)  # 如果没有井号，则照常按照每行规则进行分发
                    else:
                        # 如果有 “#” 号，则根据 “#” 号分隔
                        url_list = channel_address.split('#')
                        for channel_url in url_list:
                            yield channel_name, clean_url(channel_url)
                    channel_count += 1  # 每处理一个频道，计数器加一

            print(f"正在读取URL: {url}")
            print(f"获取到频道列表: {channel_count} 条")  # 打印频道数量

    except Exception as e:
        print(f"处理 URL 时发生错误：{e}")
        return []


# 函数用于过滤和替换频道名称
def filter_and_modify_sources(corrections):
    filtered_corrections = []
    name_dict = ['购物', '理财', '导视', '指南', '测试', '芒果', 'CGTN']
    url_dict = []  # '2409:'留空不过滤ipv6频道

    for name, url in corrections:
        if any(word.lower() in name.lower() for word in name_dict) or any(word in url for word in url_dict):
            print("过滤频道:" + name + "," + url)
        else:
            # 进行频道名称的替换操作
            name = name.replace("FHD", "").replace("HD", "").replace("hd", "").replace("频道", "").replace("高清", "") \
                .replace("超清", "").replace("20M", "").replace("-", "").replace("4k", "").replace("4K", "") \
                .replace("4kR", "")
            filtered_corrections.append((name, url))
    return filtered_corrections


# 删除目录内所有 .txt 文件
def clear_txt_files(directory):
    for filename in os.listdir(directory):
        if filename.endswith('.txt'):
            file_path = os.path.join(directory, filename)
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"删除文件时发生错误: {e}")


# 随机取得URL
def get_random_url(file_path):
    urls = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            # 查找逗号后面的部分，即URL
            url = line.strip().split(',')[-1]
            urls.append(url)    
    # 随机返回一个URL
    return random.choice(urls) if urls else None


# 主函数
def main():
    # 读取 URLs
    urls_file_path = os.path.join(os.getcwd(), 'config/urls.txt')
    urls = read_txt_to_array(urls_file_path)

    # 处理过滤和替换频道名称
    all_channels = []
    for url in urls:
        for channel_name, channel_url in process_url(url):
            all_channels.append((channel_name, channel_url))

    # 过滤和修改频道名称
    filtered_channels = filter_and_modify_sources(all_channels)

    # 去重
    unique_channels = list(set(filtered_channels))

    unique_channels_str = [f"{name},{url}" for name, url in unique_channels]

    # 写入 iptv.txt 文件
    iptv_file_path = os.path.join(os.getcwd(), 'iptv.txt')
    with open(iptv_file_path, 'w', encoding='utf-8') as f:
        for line in unique_channels_str:
            f.write(line + '\n')

    # 打印出本次写入iptv.txt文件的总频道列表数量
    with open(iptv_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        total_channels = len(lines)
        print(f"\n所有频道已保存到文件: {iptv_file_path}，共采集到频道数量: {total_channels} 条\n")

    # 获取随机URL并保存到每日推荐
    daily_mtv = "每日一首," + get_random_url('assets/今日推荐.txt')

    # 获取当前的 UTC 时间
    utc_time = datetime.now(timezone.utc)
    # 北京时间
    beijing_time = utc_time + timedelta(hours=8)
    # 格式化为所需的格式
    formatted_time = beijing_time.strftime("%Y%m%d %H:%M:%S")

    about_video1 = "https://d.kstore.dev/download/8880/%E5%85%AC%E5%91%8A.mp4"
    about_video2 = "https://vd3.bdstatic.com/mda-pcjhhz2na6nnca3a/sc/bd265_cae_visr_v5/1679330663935082640/mda-pcjhhz2na6nnca3a.mp4"
    version = formatted_time + "," + about_video1
    about = "关于本源(塔利班维护)," + about_video2

    # 打印每日推荐和关于信息
    print(daily_mtv)
    print(version)
    print(about)


if __name__ == "__main__":
    main()
