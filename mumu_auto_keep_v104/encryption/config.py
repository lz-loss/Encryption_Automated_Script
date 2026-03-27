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

# ==============================
# 配置
# ==============================

# 地址公共头
HeadPath = "/Users/mac/"

#是否倒序打开虚拟机
IS_REVERSE = False

# 同时运行数量
MAX_RUNNING = 1

# APP 包名关键字（模糊匹配）
APP_KEYWORD = ["com.misla", "com.spring"]

# APP运行时间（秒）
RUN_TIME = 15

# 启动等待时间（模拟器启动）
BOOT_WAIT = 10

# 等待设备就绪最大时间（秒）
DEVICE_READY_TIMEOUT = 10

# 最新国家代码(开后台线程刷新国家代码的时候使用)
current_country_code = None

#删除策略配置
DELETE_RULES = [
    (24, 0.3),   # 24~48小时，30%
    (48, 0.2),   # 48~72小时，20%
    (72, 0.2),   # 72~96小时，20%
    (96, 0.1),   # 96~120小时，10%
    (120, 0.1),  # 120~144小时，10%
    (144, 0.1),  # 144~168小时，10%
    (168, 0.1),  # 超过168小时，10%
    (192, 0.8),  # 超过192小时，80%
    (240, 0.1),  # 超过240小时，10%
    (480, 0.1),  # 超过480小时，10%
    (840, 1.0),  # 超过840小时，100%
]
