import os
import time
import subprocess
import logging
import json
import random
import shutil
import urllib.request
import re
import datetime
import config
#开后台线程获取国家代码时需要打开
#import threading

# 版本 1.0.4 （修改了1.0.0版本中获取vms/xxx 创建时间不正确的bug，优化1.0.1的国家判断,添加是否倒序打开虚拟机开关，打开满足打开条件的虚拟机,优化时间读取方案）

# ==============================
# 配置
# ==============================

# MuMu虚拟机目录
VM_DIR = config.HeadPath + "Library/Application Support/com.netease.mumu.nemux-global/vms"

# mumutool路径
MUMUTOOL = "/Applications/MuMuPlayer Pro.app/Contents/MacOS/mumutool"

ADB_PATH = "/Applications/MuMuPlayer Pro.app/Contents/MacOS/MuMu Android Device.app/Contents/MacOS/tools/adb"

#匹配概率删除虚拟机 记录地址 (目前是，下载中的101_mac_adb目录下。vm_delete_record.json会自动创建)
DELETE_RECORD_FILE = os.path.join(config.HeadPath , "Desktop" , "mumu_auto_keep_recode", "vm_delete_record.json")

DELETE_RECORD_FILE_NULL = os.path.join(config.HeadPath , "Desktop" , "mumu_auto_keep_recode", "vm_null_delete_record.json")

#是否倒序打开虚拟机
IS_REVERSE = config.IS_REVERSE

# 同时运行数量
MAX_RUNNING = config.MAX_RUNNING

# APP 包名关键字（模糊匹配）
APP_KEYWORD = config.APP_KEYWORD

# APP运行时间（秒）
RUN_TIME = config.RUN_TIME

# 启动等待时间（模拟器启动）
BOOT_WAIT = config.BOOT_WAIT

# 默认MuMu端口起点（每台虚拟机递增1）
#ADB_BASE_PORT = 7555

# 等待设备就绪最大时间（秒）
DEVICE_READY_TIMEOUT = config.DEVICE_READY_TIMEOUT

# 最新国家代码(开后台线程刷新国家代码的时候使用)
current_country_code = config.current_country_code

# 更新国家代码时间（秒）(开后台线程刷新国家代码的时候使用)
update_country_code_time = 60

#删除策略配置
DELETE_RULES = config.DELETE_RULES

# 日志配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

# ==============================
# 工具函数
# ==============================

def adb(cmd, port):
    """通过指定端口执行 adb 命令"""
    full_cmd = [ADB_PATH, "-s", f"127.0.0.1:{port}"] + cmd
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    return result.stdout.strip()


def scan_vms():
    """扫描 MuMu 虚拟机目录，返回虚拟机 ID 列表"""
    vms = []
    if not os.path.exists(VM_DIR):
        logging.error("虚拟机目录不存在")
        return vms

    for name in os.listdir(VM_DIR):
        path = os.path.join(VM_DIR, name)
        if os.path.isdir(path) and name.isdigit():
            vms.append(name)

    vms.sort(key=int)
    logging.info(f"扫描到虚拟机 {vms}")
    return vms

# 获取ip所在国家code （用哪个方案看实际哪个能正确获取到IP数据）
#方案一
#def get_country_code_from_ip():
#    """获取当前公网 IP 的国家 code"""
#    try:
#        response = requests.get("https://ipapi.co/json/", timeout=5)
#        data = response.json()
#        country_code = data.get("country")  # ISO 2-letter code, 如 'US', 'CN'
#        logging.info(f"当前公网 IP 国家 code: {country_code}")
#        return country_code
#    except Exception as e:
#        logging.error(f"获取国家 code 失败: {e}")
#        return None

#方案二
def get_country_code_from_ip():
    """获取当前公网 IP 的国家 code"""
    try:
        with urllib.request.urlopen("https://ipinfo.io/json") as response:
            data = json.load(response)
            country_code = data.get("country")
            logging.info(f"当前公网 IP 国家 code: {country_code}")
            return country_code
    except Exception as e:
        logging.error(f"获取国家 code 失败: {e}")
        return None

#方案三
#def get_country_code_from_ip():
#    try:
#        url = "https://ipwho.is/"
#
#        req = urllib.request.Request(
#            url,
#            headers={
#                "User-Agent": "Mozilla/5.0"
#            }
#        )
#
#        with urllib.request.urlopen(req, timeout=10) as response:
#            data = json.loads(response.read().decode("utf-8"))
#            country_code = data.get("country_code")
#            logging.info(f"当前公网 IP 国家 code: {country_code}")
#            return country_code
#
#    except Exception as e:
#        logging.error(f"获取国家 code 失败: {e}")
#        return None

# 匹配vm名字是否包含IP的国家code
def vm_matches_country(vm_id, target_country_code):
    """
    判断虚拟机 vm.json 的 vmName 是否包含指定国家 code
    """
    vm_json_path = os.path.join(VM_DIR, vm_id, "setting", "vm.json")
    if not os.path.exists(vm_json_path):
        logging.warning(f"{vm_json_path} 不存在")
        return False

    try:
        with open(vm_json_path, "r", encoding="utf-8") as f:
            vm_data = json.load(f)
        
        # 取 vmName 字段
        vm_name = ""
        if isinstance(vm_data, dict):
            vm_name = vm_data.get("vmName", "")
        elif isinstance(vm_data, list) and len(vm_data) > 0:
            vm_name = vm_data[0].get("vmName", "")
        else:
            vm_name = ""

        if target_country_code and target_country_code.upper() in vm_name.upper():
            logging.info(f"虚拟机 {vm_id} 匹配国家 {target_country_code}")
            return True
        else:
            logging.info(f"虚拟机 {vm_id} 不匹配国家 {target_country_code}")
            return False
    except Exception as e:
        logging.error(f"读取 {vm_json_path} 出错: {e}")
        return False

#获取虚拟机端口
def generate_vm_ports(vms):
    """根据虚拟机 vm.json 自动获取 adb 端口"""
    ports = {}
    for vm_id in vms:
        vm_json_path = os.path.join(VM_DIR, vm_id, "setting", "vm.json")
        if not os.path.exists(vm_json_path):
            logging.warning(f"{vm_json_path} 不存在，使用默认端口")
            ports[vm_id] = None
            continue
        try:
            with open(vm_json_path, "r", encoding="utf-8") as f:
                vm_data = json.load(f)
            # 如果 vm.json 是字典
            if isinstance(vm_data, dict):
                port = vm_data.get("adbPort")
            # 如果 vm.json 是列表（多个虚拟机对象），取第一个
            elif isinstance(vm_data, list) and len(vm_data) > 0:
                port = vm_data[0].get("adbPort")
            else:
                port = None

            if port is None:
                logging.warning(f"{vm_json_path} 未找到 adbPort，使用默认端口")
            ports[vm_id] = port
        except Exception as e:
            logging.error(f"读取 {vm_json_path} 出错: {e}")
            ports[vm_id] = None

    logging.info(f"生成虚拟机端口映射: {ports}")
    return ports

def start_vm(vm_id):
    """启动指定虚拟机"""
    logging.info(f"启动虚拟机 {vm_id}")
    subprocess.Popen([MUMUTOOL, "open", vm_id])


def close_vm(vm_id):
    """关闭指定虚拟机"""
    logging.info(f"关闭虚拟机 {vm_id}")
    subprocess.run([MUMUTOOL, "close", vm_id])


def get_devices(port):
    """获取指定端口的设备"""
    out = adb(["devices"], port)
    logging.info(f"adb devices 输出 (端口 {port}):\n{out}:\n{len(out.splitlines())}")
    devices = []
    for line in out.splitlines():
        if "device" in line and ":" in line:
            devices.append(line.split()[0])
    return devices


def wait_for_device(port, timeout=DEVICE_READY_TIMEOUT):
    """等待指定端口的设备准备就绪"""
    logging.info(f"等待端口 {port} 设备 ready...")
    start_time = time.time()
    
    # 先尝试 connect
#    logging.info(f"尝试 adb connect 127.0.0.1:{port}")
#    adb(["connect", f"127.0.0.1:{port}"], port)
    
    while time.time() - start_time < timeout:
        # 先尝试 connect
        adb(["connect", f"127.0.0.1:{port}"], port)
        devices = get_devices(port)
        if devices:
            logging.info(f"端口 {port} 设备已就绪: {devices}")
            return True
        time.sleep(1)
        port = achieve_vm_port(vm_id)
    logging.warning(f"端口 {port} 设备未在 {timeout} 秒内就绪")
    return False


#多个字符串匹配
def find_packages(port, keywords):
    """返回端口虚拟机中所有包含关键字的包"""
    packages = []
    for keyword in keywords:
        out = adb(["shell", "pm", "list", "packages", keyword], port)
        for line in out.splitlines():
            pkg = line.replace("package:", "").strip()
            if keyword.lower() in pkg.lower():
                packages.append(pkg)
    return packages


#多个字符串匹配Open
def open_app_fuzzy(port, keywords):
    """通过模糊匹配启动应用（支持关键字数组）"""
    packages = find_packages(port, keywords)
    if not packages:
        logging.warning(f"端口 {port} 未找到匹配 {keywords} 的包")
        return False
    for pkg in packages:
        logging.info(f"端口 {port} 启动模糊匹配包 {pkg}")
        adb(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"], port)
    
    return True

#多个字符串匹配Close
def close_app_fuzzy(port, keywords):
    """通过模糊匹配关闭应用（支持关键字数组）"""
    packages = find_packages(port, keywords)
    if not packages:
        logging.warning(f"端口 {port} 未找到匹配 {keywords} 的包")
        return
    for pkg in packages:
        logging.info(f"端口 {port} 关闭应用 {pkg}")
        adb(["shell", "am", "force-stop", pkg], port)

#获取vmName
def achieve_vm_name(vm_id):
    vm_json_path = os.path.join(VM_DIR, vm_id, "setting", "vm.json")
    with open(vm_json_path, "r", encoding="utf-8") as f:
        vm_data = json.load(f)
    vm_name = ""
    if isinstance(vm_data, dict):
        vm_name = vm_data.get("vmName", "")
    elif isinstance(vm_data, list) and len(vm_data) > 0:
        vm_name = vm_data[0].get("vmName", "")
    
    return vm_name

#获取vm_port
def achieve_vm_port(vm_id):
    vm_json_path = os.path.join(VM_DIR, vm_id, "setting", "vm.json")
    with open(vm_json_path, "r", encoding="utf-8") as f:
        vm_data = json.load(f)
    vm_port = ""
    if isinstance(vm_data, dict):
        vm_port = vm_data.get("adbPort", "")
    elif isinstance(vm_data, list) and len(vm_data) > 0:
        vm_port = vm_data[0].get("adbPort", "")
    else:
        port = None
    
    return vm_port


#获取时间方案一
def parse_first_vm_time(vm_name):
    """
    解析格式：BR 126(13:07 03-25-2026)
    返回 datetime 或 None
    """
    logging.info(f"执行时间获取方案一：获取名字中标准时间格式")
    match = re.search(r"\((.*?)\)", vm_name)

    if not match:
        logging.info(f"执行时间获取方案一失败")
        return None

    time_str = match.group(1)

    try:
        dt = datetime.datetime.strptime(time_str, "%H:%M %m-%d-%Y")
        return dt
    except ValueError:
        logging.info(f"执行时间获取方案一失败：{ValueError}")
        return None

#获取时间方案二
def parse_second_vm_time(vm_name):
    """
    从 vm_name 中解析时间
    格式：BD-101-03-26-11:01
    返回 datetime 或 None
    """
    logging.info(f"执行时间获取方案二：获取名字中老时间格式")
    match = re.search(r"-(\d{2})-(\d{2})-(\d{2}:\d{2})$", vm_name)

    if not match:
        logging.info(f"执行时间获取方案二失败")
        return None

    month, day, time_str = match.groups()

    try:
        dt = datetime.datetime.strptime(
            f"2026-{month}-{day} {time_str}",
            "%Y-%m-%d %H:%M"
        )
        return dt
    except ValueError:
        logging.info(f"执行时间获取方案二失败：{ValueError}")
        return None

#获取虚拟机（vms/xxx）创建时间
def get_vm_creation_time(vm_id):
    """获取虚拟机实例目录的真实创建时间（st_birthtime）"""
    
    vm_name = achieve_vm_name(vm_id)
    first_time = parse_first_vm_time(vm_name)
    if first_time:
        logging.info(f"方案一获取时间为：{first_time}")
        return first_time
    
    second_time = parse_second_vm_time(vm_name)
    if second_time:
        logging.info(f"方案二获取时间为：{second_time}")
        return second_time

    logging.info(f"执行时间获取方案三：获取{vm_id} 索引的创建时间")
    vm_path = os.path.join(VM_DIR, vm_id)
    if not os.path.exists(vm_path):
        logging.warning(f"{vm_path} 不存在")
        return None
    try:
        path = VM_DIR + "/" + vm_id
#            create_time = datetime.datetime.fromtimestamp(stat.st_birthtime)
        cmd = ["stat", "-f", "%SB", "-t", "%Y-%m-%d %H:%M:%S", path]
        time_str = subprocess.check_output(cmd).decode().strip()
        create_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        logging.info(f"{vm_id} 创建时间为：{create_time} ")
        return create_time
    except AttributeError:
        # 如果系统不支持 st_birthtime，回退到 ctime
        logging.warning("系统不支持 st_birthtime，使用 ctime 替代")
        return vm_path.stat().st_ctime

#判断是否在当前时间区间内已经打开过了
def judge_vm_has_opened(vm_id):
    create_time = get_vm_creation_time(vm_id)
    if create_time is None:
        logging.warning(f"{vm_id} 未找到 .gmad 文件，跳过打开")
        return True

    delete_record = load_delete_record()
#    hours_since_creation = (time.time() - create_time) / 3600
    hours_since_creation = (time.mktime(time.localtime()) - create_time.timestamp()) / 3600
    
    segment_idx = get_time_segment(hours_since_creation)
    if segment_idx is None:
        logging.warning(f"虚拟机 {vm_id} ：未找到 概率区间 {segment_idx}，跳过打开")
        return True
    last_segment_idx = delete_record.get(vm_id)
    if last_segment_idx == segment_idx:
        logging.info(f"{vm_id} 在同一区间 {segment_idx}，跳过打开")
        return True

    delete_record[vm_id] = segment_idx
    _, delete_probability = DELETE_RULES[segment_idx]
    
#    delete_probability = None
    logging.info(f"时间段是： {time.time()}、{create_time}、 {hours_since_creation} 、{delete_probability}")

    if delete_probability is None:
        logging.info(f"{vm_id} 不在任何 概率时间段内，跳过打开")
        return True

    return False
    


# ==============================
# 删除部分开始
# ==============================

def load_delete_record():
    # 如果目录不存在先创建
    os.makedirs(os.path.dirname(DELETE_RECORD_FILE), exist_ok=True)

    # 如果文件不存在，创建并初始化为 []
    if not os.path.exists(DELETE_RECORD_FILE):
        with open(DELETE_RECORD_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

    if os.path.exists(DELETE_RECORD_FILE):
        try:
            with open(DELETE_RECORD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"读取删除记录失败: {e}")
    return {}

def save_delete_record(record):

    # 如果目录不存在先创建
    os.makedirs(os.path.dirname(DELETE_RECORD_FILE), exist_ok=True)

    # 如果文件不存在，创建并初始化为 []
    if not os.path.exists(DELETE_RECORD_FILE):
        with open(DELETE_RECORD_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

    try:
        with open(DELETE_RECORD_FILE, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
    except Exception as e:
        logging.error(f"保存删除记录失败: {e}")

def get_time_segment(hours_since_creation):
    for idx, (start_hour, _) in enumerate(DELETE_RULES):
        end_hour = DELETE_RULES[idx + 1][0] if idx + 1 < len(DELETE_RULES) else float('inf')
        if start_hour <= hours_since_creation < end_hour:
            return idx
    return None


#概率删除虚拟机
def maybe_delete_vm(vm_id):
    """根据创建时间和概率，决定是否删除虚拟机"""
    create_time = get_vm_creation_time(vm_id)
    if create_time is None:
        logging.warning(f"{vm_id} 未找到 .gmad 文件，跳过删除")
        return

    delete_record = load_delete_record()
#    hours_since_creation = (time.time() - create_time) / 3600
    hours_since_creation = (time.mktime(time.localtime()) - create_time.timestamp()) / 3600
    
    segment_idx = get_time_segment(hours_since_creation)
    if segment_idx is None:
        logging.warning(f"虚拟机 {vm_id} ：未找到 删除概率区间 {segment_idx}，跳过删除")
        return
    last_segment_idx = delete_record.get(vm_id)
    if last_segment_idx == segment_idx:
        logging.info(f"{vm_id} 在同一区间 {segment_idx}，跳过删除")
        return

    delete_record[vm_id] = segment_idx
    _, delete_probability = DELETE_RULES[segment_idx]
    
#    delete_probability = None
    logging.info(f"时间段是： {time.time()}、{create_time}、 {hours_since_creation} 、{delete_probability}")
#
#    for i, (start_hour, prob) in enumerate(DELETE_RULES):
#        end_hour = DELETE_RULES[i + 1][0] if i + 1 < len(DELETE_RULES) else float('inf')
#        if start_hour <= hours_since_creation < end_hour:
#            delete_probability = prob
#            break

    if delete_probability is None:
        logging.info(f"{vm_id} 不在任何删除时间段内，跳过删除")
        return

    logging.info(f"删除概率为: {delete_probability}")
    
    if random.random() < delete_probability:
        logging.info(f"虚拟机 {vm_id} 被选中删除（删除概率 {delete_probability*100:.1f}%）")
        try:
            # 删除整个虚拟机目录
            delete_vm_with_gmad(vm_id)
            logging.info(f"虚拟机 {vm_id} 已删除")
            if vm_id in delete_record:
                del delete_record[vm_id]
                save_delete_record(delete_record)  # 保存到文件
        except Exception as e:
            logging.error(f"删除虚拟机 {vm_id} 失败: {e}")
    else:
        save_delete_record(delete_record)
        logging.info(f"虚拟机 {vm_id} 未被删除（删除概率 {delete_probability*100:.1f}%）")



def delete_vm_with_gmad(vm_id):
    """
    删除虚拟机实例和对应的真实 .gmad 文件
    """
    vm_path = os.path.join(VM_DIR, vm_id)
    if not os.path.exists(vm_path):
        logging.warning(f"{vm_path} 不存在")
        return

    # 判断是否是符号链接
    if os.path.islink(vm_path):
        # 获取符号链接指向的真实路径
        real_path = os.readlink(vm_path)
        logging.info(f"虚拟机 {vm_id} 是符号链接，真实路径: {real_path}")

        # 删除真实 .gmad 文件
        if os.path.exists(real_path):
            if os.path.isfile(real_path):
                os.remove(real_path)
                logging.info(f"真实 .gmad 文件已删除: {real_path}")
            elif os.path.isdir(real_path):
                shutil.rmtree(real_path)
                logging.info(f"真实目录已删除: {real_path}")
        else:
            logging.warning(f"真实路径不存在: {real_path}")

        # 删除符号链接本身
        os.unlink(vm_path)
        logging.info(f"符号链接实例已删除: {vm_path}")

    elif os.path.isdir(vm_path):
        # 如果是普通目录，直接删除
        shutil.rmtree(vm_path)
        logging.info(f"普通目录虚拟机已删除: {vm_path}")

    else:
        # 如果是普通文件
        os.remove(vm_path)
        logging.info(f"普通文件虚拟机已删除: {vm_path}")

#记录删除记录
def append_json_record(file_path, record):
    # 如果目录不存在先创建
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # 如果文件不存在，创建并初始化为 []
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([], f)

    # 读取原有数据
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = []

    # 确保是数组
    if not isinstance(data, list):
        data = []

    # 添加新记录
    data.append(record)

    # 写回文件
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logging.info(f"无App的{record}虚拟机删除记录已经更新")

# ==============================
# 删除部分结束
# ==============================

#自动隔N秒获取最新的current_country_code
def update_country_code_periodically(interval=60):
    """后台线程，每隔 interval 秒更新一次国家代码"""
    global current_country_code
    while True:
        try:
            current_country_code = get_country_code_from_ip()
            logging.info(f"[国家代码更新] 当前国家 code: {current_country_code}")
        except Exception as e:
            logging.error(f"[国家代码更新失败] {e}")
        time.sleep(interval)

# ==============================
# 批量运行虚拟机 + 应用
# ==============================

def run_batch(vm_batch, vm_ports):
    logging.info(f"启动批次 {vm_batch}")

    # 启动虚拟机
    for vm_id in vm_batch:
        start_vm(vm_id)
        time.sleep(2)

    logging.info(f"等待 {BOOT_WAIT} 秒让模拟器启动...")
    time.sleep(BOOT_WAIT)

    
    nullbatch = []
    # 启动应用前，等待设备 ready
    for vm_id in vm_batch:
#        port = vm_ports[vm_id]
        port = achieve_vm_port(vm_id)
        if wait_for_device(port):
            if not open_app_fuzzy(port, APP_KEYWORD):
                nullbatch.append(vm_id)
        else:
            logging.warning(f"端口 {port} 设备未就绪，跳过启动应用")

    logging.info(f"应用运行 {RUN_TIME} 秒")
    time.sleep(RUN_TIME)
    
#    调整可用的虚拟机
    b_set = set(nullbatch)
    vm_batch = [x for x in vm_batch if x not in b_set]
    
    logging.info(f"调整后的虚拟机分别是  正常：{vm_batch} ，异常：{nullbatch}")

    # 关闭应用
    for vm_id in vm_batch:
        port = achieve_vm_port(vm_id)
        if wait_for_device(port):
            close_app_fuzzy(port, APP_KEYWORD)
        else:
            logging.warning(f"端口 {port} 设备未就绪，跳过关闭应用")

    # 关闭正常虚拟机
    for vm_id in vm_batch:
        close_vm(vm_id)
        time.sleep(1)
        # 概率删除
        maybe_delete_vm(vm_id)
    
    # 关闭非正常虚拟机
    for vm_id in nullbatch:
        close_vm(vm_id)
        time.sleep(1)
        # 直接删除
        logging.info(f"开始删除 非正常的 {vm_id} 虚拟机...")
        vm_name = achieve_vm_name(vm_id)
        delete_vm_with_gmad(vm_id)
        logging.info(f"非正常虚拟机 {vm_id} 删除完毕")
        append_json_record(DELETE_RECORD_FILE_NULL, {"vm_name":f"{vm_name}"})


# ==============================
# 主程序
# ==============================

def main():
    # 启动后台线程更新国家代码
#    threading.Thread(target=update_country_code_periodically, args=(update_country_code_time,), daemon=True).start()
    
    # 扫描虚拟机
    vms = scan_vms()
    if not vms:
        logging.error("没有发现虚拟机，程序退出")
        return

    # 生成端口映射
    vm_ports = generate_vm_ports(vms)
    
    # 是否倒序打开
    if IS_REVERSE:
        vms.reverse()
        logging.info(f"倒序顺序是: {vms} ")
    
    # 批量运行
    index = 0
    while index < len(vms):
#        得到后台更新的最新国家code
#        country_code = current_country_code
#       每次都去获取一次国家code
        country_code = get_country_code_from_ip()
        logging.info(f"country_code: {country_code} ")
        batch = []
        count = 0
        while count < MAX_RUNNING and index < len(vms):
            vm_id = vms[index]
            vm_json_path = os.path.join(VM_DIR, vm_id, "setting", "vm.json")
            index += 1  # 无论匹配不匹配，都向后走
            if not os.path.exists(vm_json_path):
                logging.warning(f"{vm_json_path} 不存在，跳过")
                continue
#            判断目前 是否是 全新时间段 去 打开虚拟机刷留存
            if judge_vm_has_opened(vm_id):
                logging.warning(f"{vm_id} 虚拟机不需要打开，跳过")
                continue
            try:
                with open(vm_json_path, "r", encoding="utf-8") as f:
                    vm_data = json.load(f)
                vm_name = ""
                if isinstance(vm_data, dict):
                    vm_name = vm_data.get("vmName", "")
                elif isinstance(vm_data, list) and len(vm_data) > 0:
                    vm_name = vm_data[0].get("vmName", "")
                
#                不喊字母则添加BR
                if not re.search(r"[A-Za-z]", vm_name):
                    vm_name = "BR" + vm_name
                    logging.warning(f"添加后的名字：{vm_name}")
                # 匹配国家 code
#                if country_code.lower() in vm_name.lower():
#                    batch.append(vm_id)
#                    count += 1
#                country_code是SG的情况，同样算country_code是BD。
                if country_code.lower() in vm_name.lower() or (country_code.upper() == "SG" and "BD" in vm_name.upper()):
                    batch.append(vm_id)
                    count += 1
            except Exception as e:
                logging.error(f"读取 {vm_json_path} 出错: {e}")
        
        if not batch:
            logging.info("当前批次没有匹配的虚拟机，跳过")
            continue
        logging.info(f"启动批次: {batch} ")
        try:
            run_batch(batch, vm_ports)
        except Exception as e:
            logging.error(f"运行错误: {e}")
    logging.info(f"已经运行完毕！")

if __name__ == "__main__":
    main()
