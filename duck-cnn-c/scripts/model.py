# scripts/model.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class TinyConvNet(nn.Module):
    """
    Input: 1x128x128 (grayscale)
    1) Conv(1->8, 3x3, s1, p1) + ReLU + MaxPool(2)
    2) Conv(8->16, 3x3, s1, p1) + ReLU + MaxPool(2)
    3) Conv(16->32, 3x3, s1, p1) + ReLU
    4) GlobalAvgPool -> FC(32->1) -> Sigmoid (for probability)
    """
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv2d(3, 8, kernel_size=3, stride=1, padding=1, bias=True)
        self.c2 = nn.Conv2d(8, 16, kernel_size=3, stride=1, padding=1, bias=True)
        self.c3 = nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1, bias=True)
        self.fc = nn.Linear(32, 1, bias=True)

        # kaiming init helps small nets converge quickly
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
                nn.init.zeros_(m.bias)
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, nonlinearity='linear')
                nn.init.zeros_(m.bias)

    def forward(self, x):
        # x: (B,1,128,128)
        x = F.relu(self.c1(x))        # -> (B,8,128,128)
        x = F.max_pool2d(x, 2)        # -> (B,8,64,64)
        x = F.relu(self.c2(x))        # -> (B,16,64,64)
        x = F.max_pool2d(x, 2)        # -> (B,16,32,32)
        x = F.relu(self.c3(x))        # -> (B,32,32,32)
        x = F.adaptive_avg_pool2d(x, 1).squeeze(-1).squeeze(-1)  # -> (B,32)
        logit = self.fc(x).squeeze(-1)                           # -> (B,)
        return logit
