# -*- coding: utf-8 -*-
from enum import Enum

class VendorEnum(str, Enum):
    NVIDIA = "NVIDIA"
    MTHREADS = "Moore Threads"
    Apple = "Apple"
    Huawei = "Huawei"
    AMD = "AMD"
