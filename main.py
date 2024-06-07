from ctypes.wintypes import HWND
import asyncio
import threading
from typing import Callable, AsyncGenerator, List, Optional
from win32gui import EnumWindows, GetClassName, GetWindowText, \
    ShowWindow, SetWindowPos, SetForegroundWindow, IsWindowVisible
from win32con import SW_SHOWNORMAL, HWND_TOPMOST, \
    SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW, SWP_NOACTIVATE

class SingletonType(type):
    """单例模式, 元类实现
    \n添加类属性 instantiation 存储类实例
    \n重写类__new__方法, 控制类实例化方法
    """
    def __new__(meta, name, bases, class_dict):
        the_cls = type.__new__(meta, name, bases, class_dict)
        the_cls.instantiation = None
        def single_new(cls):
            if cls.instantiation is None:
                cls.instantiation = super(cls, cls).__new__(cls)
            return cls.instantiation
        the_cls.__new__ = single_new
        return the_cls
    
class Window:
    """ 一个基本的window窗口对象，提供基本操作 """
    title: str  # 窗口标题，一般在左上角
    hwd: int  # 窗口句柄
    visible: bool  # 窗口是否可见标志
    
    def __init__(self, tilte: str, hwd: int, visible: bool) -> None:
        self.title = tilte
        self.hwd = hwd
        self.visible = visible

    def top(self):
        """ 置顶窗口并保持 """
        SetWindowPos(
            hWnd = self.hwd,
            InsertAfter = HWND_TOPMOST,
            X = 0, Y = 0, cx = 0, cy = 0, 
            Flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW | SWP_NOACTIVATE
        )

    def show(self) -> None:
        """ 显示窗口（即置顶不保持）"""
        ShowWindow(self.hwd, SW_SHOWNORMAL)

    def close(self):
        """ 关闭窗口 """
        # TODO
        print("close method will complete")
        pass

class WindowProducer(metaclass=SingletonType):
    """ 单例.获取window窗口类 """
    filter_func: Callable  # 窗口过滤器函数
    producer_timer: AsyncGenerator  # 异步生成所有窗口列表
    windows_queue: List[Window]  # 缓存有效的窗口列表

    def __init__(self, filter_func: Optional[Callable] = None) -> None:
        self.filter_func = filter_func
        self.producer_timer = WindowProducer.producer_windows
        self.windows_queue = []

    @classmethod
    async def producer_windows(cls) -> List[int]:
        """ 异步函数，获取所有窗口列表 """
        store_hwds: List[int] = []
        EnumWindows(
            lambda a_hwd, store_hwds: store_hwds.append(a_hwd),
            store_hwds
        )
        return store_hwds
    
    def hwds_convert_Windows(self, hwds: List[int]) -> None:
        self.windows_queue = [
            Window(GetWindowText(i),i, bool(IsWindowVisible(i)))
                for i in hwds
        ] 
    def print_interface(self) -> List[Window]:
        """ 输出窗口列表 """
        windows_queue = self.windows_queue \
            if self.windows_queue else []
        return [
            Window(GetWindowText(i),i, bool(IsWindowVisible(i)))
                for i in windows_queue
        ] 
    async def _run(self) -> None:
        while(await asyncio.sleep(1)):
            self.hwds_convert_Windows(await self.producer_timer())
    
    def run(self):
        self.run_threading = threading.Thread(
            target = lambda r:asyncio.get_event_loop().run_until_complete(r()),
            args = self._run
        )
        self.run_threading.start()

    def __del__(self) -> None:
        if hasattr(self, 'run_threading'):
            self.run_threading.join()

# class TESTCase
def test_signle_func():
    """测试单例"""
    a = WindowProducer()
    b = WindowProducer()
    assert id(a) == id(b)
    a.new_attr = 90
    assert hasattr(b, 'new_attr') and b.new_attr == a.new_attr

# class A():
#     def __new__(cls) -> 'A':  # cls == <class '__main__.A'>
#         return super().__new__(cls)
#     def __init__(self) -> None:
#         self.a = 3
# A()