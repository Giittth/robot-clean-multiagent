"""
一阶低通滤波器，用于平滑位姿和电池电压，避免前端数据抖动。
"""


class SmoothingFilter:
    def __init__(self, alpha: float = 0.15):
        """
        :param alpha: 平滑系数，0~1之间，越小越平滑但响应越慢。
        """
        self.alpha = alpha
        self._value = None

    def filter(self, new_value: float) -> float:
        """输入新值，返回平滑后的值"""
        if self._value is None:
            self._value = new_value
        else:
            self._value += (new_value - self._value) * self.alpha
        return self._value

    def reset(self):
        """重置滤波器状态"""
        self._value = None