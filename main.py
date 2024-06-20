from contextlib import contextmanager
from ctypes.wintypes import HWND
import asyncio
import atexit
import functools
from io import StringIO, TextIOBase
import re
import sys
from queue import Queue
import threading
from typing import Any, Callable, AsyncGenerator, List, Optional
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

class ResourceMamagement(metaclass=SingletonType):
    """ 资源管理，处理多线程和协程释放 """
    dispatch_queue: Queue  # 管理基本调度单位的释放
    def __init__(self) -> None:
        self.dispatch_queue = Queue()
    def closed(self) -> int:
        """ 释放资源,return 进程退出标志 """
        WindowProducer().closed()
        return 0

class WindowProducer(metaclass=SingletonType):
    """ 单例.获取window窗口类 """
    filter_func: Callable  # 窗口过滤器函数
    producer_timer: AsyncGenerator  # 异步生成所有窗口列表
    windows_queue: List[Window]  # 缓存有效的窗口列表
    resource_mamagement: ResourceMamagement  # 资源管理friend单例

    def __init__(self, filter_func: Optional[Callable] = None) -> None:
        self.filter_func = filter_func
        self.producer_timer = WindowProducer.producer_windows
        self.windows_queue = []
        self.resource_mamagement = ResourceMamagement()
        

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
        if isinstance(self.windows_queue, list) and \
                all([isinstance(i, Window) for i in self.windows_queue]):
            return self.windows_queue
        else:
            windows_queue = self.windows_queue \
                if self.windows_queue else []
            return [
                Window(GetWindowText(i),i, bool(IsWindowVisible(i)))
                    for i in windows_queue
            ] 
    async def _run(self, msg: str = None) -> None:
        def get_coro_status():
            class_name = self.__class__.__name__
            the_status:str = self.resource_mamagement.dispatch_queue.get(
                block=False)
            self.resource_mamagement.dispatch_queue.put(
                item= class_name + 'running',
                block=False)
            return the_status.replace(class_name, '')
        while(get_coro_status() != 'closed'):
            await asyncio.sleep(1)
            self.hwds_convert_Windows(await self.producer_timer())
    
    def run(self):
        self.resource_mamagement.dispatch_queue.put(
            self.__class__.__name__ + 'running'
        )
        self.run_threading = threading.Thread(
            target = lambda r:asyncio.new_event_loop().run_until_complete(r()),
            args = [self._run]
        )
        # self.run_threading.setDaemon(True)
        self.run_threading.daemon = True
        self.run_threading.start()

    def closed(self) -> None:
        if hasattr(self, 'run_threading'):
            self.resource_mamagement.dispatch_queue.put(
                item=self.__class__.__name__ + 'closed'
            )
            self.run_threading.join()

class DefaultWindowFilter:
    """ 接口，默认窗口过滤器
     在过滤规则中rules中，使用正则表达式进行窗口过滤
     其中`$`指代窗口，多个窗口字段过滤规则以and区别

     每条规则允许的操作包含
     \n 1. match
     \n 2. ==
     \n 3. is
     \n 4. in
     \n **注意** 操作两端需以空格分开
    """
    rules: str  # 过滤规则，使用
    def __init__(self) -> None:
        """ 初始化默认窗口过滤规则 """
        # 默认只保留窗口标题包含中文字符并且窗口可见的窗口对象
        self.rules = r"$.title match {.*[\u4e00-\u9fa5].*} "\
                        r"and $.visible is true"
    def filter_func(self, windows: List[Window]) -> List[Window]:
        """接受需要过滤的窗口对象列表，返回过滤后的窗口列表 
        
        Args:
            windows (List[Window]): 需要过滤的窗口对象列表
        
        Returns:
            List[Window]: 过滤后的窗口列表
        """
        res: List[Window] = []
        for i in windows:
            if self.pass_rules(i):
                res.append(i)
        return res
    def pass_rules(self, a_window: Window) -> bool:
        """判断一个窗口对象能否通过过滤规则 
        
        Args:
            a_window (Window): 输入的窗口对象
        
        Returns:
            bool: 窗口是否合规
        """
        self.rules = self.rules.strip()
        assert self.rules.startswith('$'), "过滤规则请以窗口对象代指$开头"
        def match_op(re_expr: str, window_attribute: str) -> bool:
            return bool(re.match(re_expr, window_attribute))
        
        def equals_op(re_expr: str|bool, window_attribute: str|bool) -> bool:
            return type(window_attribute) == type(re_expr) and \
                window_attribute == re_expr
        
        def is_op(re_expr: bool|None, window_attribute: bool|None) -> bool:
            return type(window_attribute) == type(re_expr) and \
                window_attribute is re_expr
        
        # def in_op(re_expr: str, window_attribute: str) -> bool:
        #     # TODO
        #     return bool(re.match(re_expr, window_attribute))
        def conv_expr_type(expr: str) -> bool|None:
            """转换表达式到python内置类型，仅转换bool/none 
            
            Args:
                expr (str): 输入表达式
            
            Raises:
                Exception: 接受非法expr

            Returns:
                bool|None: 返回类型
            """
            if expr.lower() in ['none', 'null']:
                return None
            elif expr.lower() in ['true', 'false']:
                return True if expr.lower() == 'true' else False
            raise Exception('解析rules expr出错')
        
        def rule_verify(a_rule: str, a_window: Window) -> Callable[..., bool]:
            """ 进行规则有效性校验和对有效规则返回对应的方法调用 """
            assert a_rule.startswith('$'), "过滤规则请以窗口对象代指$开头"
            mat_groups = re.match(r"\$\.(\S+)\s+(match|==|is|in)\s+(.*)",a_rule)
            if mat_groups is None:
                print('error:the rules is illegal')  # 输出错误信息
                return
            # 窗口属性
            the_window_attr = mat_groups.group(1)
            assert hasattr(a_window, the_window_attr), \
                f"窗口对象无属性{the_window_attr}"
            the_window_attr = getattr(a_window, the_window_attr)
            # 操作转发
            the_op = mat_groups.group(2)
            # 表达式
            the_expr = mat_groups.group(3)
            if the_op == 'match':
                assert the_expr[0] == '{' and the_expr[-1] == '}', "match expr error"
                return functools.partial(match_op, the_expr[1:-1], the_window_attr)
            elif the_op == '==':
                if the_expr.lower() in ['true', 'false']:
                    return functools.partial(equals_op, conv_expr_type(the_expr), the_window_attr)
                else:
                    return functools.partial(equals_op, the_expr, the_window_attr)
            elif the_op == 'is':
                return functools.partial(is_op, conv_expr_type(the_expr), the_window_attr)
            elif the_op == 'in':
                print('in_op is TODO')            
        
        rules_items = self.rules.split('and')
        for the_rule in rules_items:
            the_rule = the_rule.strip()
            # 窗口不匹配其中一条规则，返回失败过滤结果
            if not rule_verify(the_rule, a_window)():
                return False
        return True



class TestClass:
    """ 使用pytest测试的test_group """
    def test_window_producer_signle_func(self):
        """测试WindowProducer单例"""
        a = WindowProducer()
        b = WindowProducer()
        assert id(a) == id(b)
        a.new_attr = 90
        assert hasattr(b, 'new_attr') and b.new_attr == a.new_attr
    
    def test_resource_mamagement_signle_func(self):
        """测试ResourceMamagement单例"""
        a = ResourceMamagement()
        b = ResourceMamagement()
        assert id(a) == id(b)
        a.new_attr = 90
        assert hasattr(b, 'new_attr') and b.new_attr == a.new_attr
    def test_window_producer_threading_run_func(self):
        win = WindowProducer()
        win.run()
        assert win.run_threading.is_alive()
        print('current threads num is : ', threading.active_count())
        win.closed()
    def test_default_window_filter_func(self, monkeypatch):
        """ 测试窗口过滤器 """
        # print('all monkeypatch attr key : ', dir(monkeypatch))
        mock_window_obj = Window("", 0, True)
        monkeypatch.setattr(mock_window_obj, "title", "window_mock_obj")
        monkeypatch.setattr(mock_window_obj, "hwd", 1)
        monkeypatch.setattr(mock_window_obj, "visible", False)
        the_filter = DefaultWindowFilter()
        assert the_filter.filter_func([mock_window_obj]).__len__() == 0
        monkeypatch.setattr(mock_window_obj, "visible", True)
        assert the_filter.filter_func([mock_window_obj]).__len__() == 0
        monkeypatch.setattr(mock_window_obj, "title", "window_mock_obj测试")
        assert the_filter.filter_func([mock_window_obj]).__len__() == 1
        monkeypatch.setattr(mock_window_obj, "visible", False)
        assert the_filter.filter_func([mock_window_obj]).__len__() == 0
        assert 'mock' == 'mock'


# sys.exit(ResourceMamagement().closed())
atexit.register(ResourceMamagement().closed)

def first_dev_script():
    """ 显示dev_script分支开发成果 """
    the_producer = WindowProducer()
    the_producer.run()

    @contextmanager
    def stdout_content():
        """ 一个简易的cli接口显示窗口列表 """
        # cli显示init操作
        # temp = sys.stdout.write
        class FObject:
            pass
        f = FObject()
        def f_write(x: str):
            sys.stdout.write(x)
            sys.stdout.flush()
            sys.stdout.write('\x08' * len(x))
        f.write = f_write
        yield f
        # sys.stdout = temp
        # cli显示清理操作
        # TODO
    def cli_display_style():
        """ 简易cli显示窗口界面样式 """
        get_windows = the_producer.print_interface()
        from pandas import DataFrame
        from dataclasses import make_dataclass

        WindowTableCli = make_dataclass(
            cls_name='WindowTableCli', 
            fields=[('hwnd', int), ('title', str), ('visible', bool)])
        the_table = DataFrame([WindowTableCli(v.hwd, v.title, v.visible) 
                           for v in get_windows])
        return the_table.to_markdown()

    with stdout_content() as f:
        f.write(cli_display_style())

if __name__ == "__main__":
    # TestClass().test_window_producer_threading_run_func()
    first_dev_script()
    # private email 