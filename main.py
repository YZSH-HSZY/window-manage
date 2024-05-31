
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

class WindowProducer(metaclass=SingletonType):
    def __init__(self) -> None:
        self.a = 3


def test_signle_func():
    """测试单例"""
    a = WindowProducer()
    b = WindowProducer()
    assert id(a) == id(b)
    a.new_attr = 90
    assert hasattr(b, 'new_attr') and b.new_attr == a.new_attr