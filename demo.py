#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
大疆无人机PSDK到MSDK数据传输程序
该程序从PSDK接收负载数据并通过MSDK发送信号
"""

import threading
import time
import logging
import queue

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入大疆的SDK (假设已安装相应的Python包)
try:
    import dji_sdk.psdk as psdk
    import dji_sdk.msdk as msdk
except ImportError:
    logger.error("无法导入大疆SDK包，请确保已正确安装")
    raise

# 数据队列，用于线程间通信
data_queue = queue.Queue()

class PSDKReceiver:
    """处理来自PSDK的数据"""
    
    def __init__(self, device_path='/dev/ttyUSB0', baud_rate=115200):
        self.device_path = device_path
        self.baud_rate = baud_rate
        self.psdk_client = None
        self.running = False
        
    def connect(self):
        """连接到PSDK设备"""
        try:
            logger.info(f"正在连接PSDK设备: {self.device_path}")
            self.psdk_client = psdk.PSDKClient(self.device_path, self.baud_rate)
            self.psdk_client.initialize()
            logger.info("PSDK设备连接成功")
            return True
        except Exception as e:
            logger.error(f"PSDK连接失败: {e}")
            return False
    
    def data_callback(self, data):
        """PSDK数据回调函数"""
        logger.debug(f"接收到PSDK数据: {data}")
        # 将数据放入队列
        data_queue.put(data)
    
    def start(self):
        """启动数据接收"""
        if not self.psdk_client:
            if not self.connect():
                return False
        
        try:
            # 注册数据回调
            self.psdk_client.register_data_callback(self.data_callback)
            self.running = True
            # 启动接收循环
            self.psdk_client.start_receiving()
            logger.info("PSDK数据接收已启动")
            return True
        except Exception as e:
            logger.error(f"启动PSDK接收失败: {e}")
            return False
    
    def stop(self):
        """停止数据接收"""
        if self.psdk_client and self.running:
            self.running = False
            self.psdk_client.stop_receiving()
            self.psdk_client.finalize()
            logger.info("PSDK数据接收已停止")


class MSDKTransmitter:
    """通过MSDK发送信号"""
    
    def __init__(self, app_id="your_app_id", app_key="your_app_key"):
        self.app_id = app_id
        self.app_key = app_key
        self.msdk_client = None
        self.running = False
        
    def connect(self):
        """连接到MSDK"""
        try:
            logger.info("正在初始化MSDK客户端")
            self.msdk_client = msdk.MSDKClient(self.app_id, self.app_key)
            self.msdk_client.initialize()
            logger.info("MSDK客户端初始化成功")
            return True
        except Exception as e:
            logger.error(f"MSDK初始化失败: {e}")
            return False
    
    def send_signal(self, data):
        """发送信号到MSDK"""
        if not self.msdk_client:
            logger.error("MSDK客户端未初始化")
            return False
        
        try:
            # 处理数据并发送信号
            processed_data = self.process_data(data)
            result = self.msdk_client.send_data(processed_data)
            logger.debug(f"MSDK信号发送状态: {result}")
            return result
        except Exception as e:
            logger.error(f"MSDK发送信号失败: {e}")
            return False
    
    def process_data(self, data):
        """处理PSDK数据为MSDK可接受的格式"""
        # 根据实际数据结构进行必要的转换
        # 这里只是一个示例，实际转换取决于您的数据格式
        processed_data = {
            "timestamp": time.time(),
            "payload_data": data,
            "type": "sensor_data"
        }
        return processed_data
    
    def start(self):
        """启动信号发送服务"""
        if not self.msdk_client:
            if not self.connect():
                return False
        
        self.running = True
        logger.info("MSDK发送服务已启动")
        return True
    
    def stop(self):
        """停止信号发送服务"""
        if self.msdk_client and self.running:
            self.running = False
            self.msdk_client.finalize()
            logger.info("MSDK发送服务已停止")


class DataBridge:
    """数据桥接服务"""
    
    def __init__(self, psdk_config=None, msdk_config=None):
        # 默认配置
        default_psdk_config = {
            'device_path': '/dev/ttyUSB0',
            'baud_rate': 115200
        }
        
        default_msdk_config = {
            'app_id': 'your_app_id',
            'app_key': 'your_app_key'
        }
        
        # 使用提供的配置或默认配置
        self.psdk_config = psdk_config or default_psdk_config
        self.msdk_config = msdk_config or default_msdk_config
        
        # 创建PSDK和MSDK实例
        self.psdk_receiver = PSDKReceiver(**self.psdk_config)
        self.msdk_transmitter = MSDKTransmitter(**self.msdk_config)
        
        # 线程控制
        self.bridge_thread = None
        self.running = False
    
    def _bridge_worker(self):
        """桥接工作线程"""
        logger.info("数据桥接线程已启动")
        
        while self.running:
            try:
                # 从队列获取数据，有1秒超时以便能够优雅退出
                try:
                    data = data_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # 发送数据
                self.msdk_transmitter.send_signal(data)
                
                # 标记任务完成
                data_queue.task_done()
                
            except Exception as e:
                logger.error(f"桥接处理中出错: {e}")
        
        logger.info("数据桥接线程已停止")
    
    def start(self):
        """启动桥接服务"""
        # 启动PSDK接收
        if not self.psdk_receiver.start():
            logger.error("无法启动PSDK接收器")
            return False
        
        # 启动MSDK发送服务
        if not self.msdk_transmitter.start():
            logger.error("无法启动MSDK发送器")
            self.psdk_receiver.stop()
            return False
        
        # 启动桥接线程
        self.running = True
        self.bridge_thread = threading.Thread(target=self._bridge_worker)
        self.bridge_thread.daemon = True
        self.bridge_thread.start()
        
        logger.info("数据桥接服务已成功启动")
        return True
    
    def stop(self):
        """停止桥接服务"""
        logger.info("正在停止数据桥接服务...")
        
        # 停止桥接线程
        self.running = False
        if self.bridge_thread and self.bridge_thread.is_alive():
            self.bridge_thread.join(timeout=5.0)
        
        # 停止PSDK和MSDK
        self.psdk_receiver.stop()
        self.msdk_transmitter.stop()
        
        logger.info("数据桥接服务已完全停止")


def main():
    """主函数"""
    # 创建配置
    psdk_config = {
        'device_path': '/dev/ttyUSB0',  # 根据实际设备路径修改
        'baud_rate': 115200
    }
    
    msdk_config = {
        'app_id': 'your_app_id',        # 替换为您的实际App ID
        'app_key': 'your_app_key'       # 替换为您的实际App Key
    }
    
    # 创建并启动桥接服务
    bridge = DataBridge(psdk_config, msdk_config)
    
    try:
        # 启动服务
        if bridge.start():
            logger.info("服务已启动，按Ctrl+C停止...")
            # 保持主线程运行
            while True:
                time.sleep(1)
        else:
            logger.error("服务启动失败")
    
    except KeyboardInterrupt:
        logger.info("接收到退出信号")
    
    finally:
        # 确保服务被正确停止
        bridge.stop()


if __name__ == "__main__":
    main()
