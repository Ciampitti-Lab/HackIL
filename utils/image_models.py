import torch.nn as nn
import timm

class MobileViT(nn.Module):
    def __init__(
        self,
        model_name="mobilevit_s",
        num_classes=1
    ):
        super().__init__()

        self.model = timm.create_model(
            model_name,
            pretrained=True,
            in_chans=3,
            num_classes=num_classes
        )

    def forward(self, x):
        return self.model(x)

class MobileNetV3(nn.Module):
    def __init__(
        self,
        model_name="mobilenetv3_small_100",
        num_classes=1
    ):
        super().__init__()

        self.model = timm.create_model(
            model_name,
            pretrained=True,
            in_chans=3,
            num_classes=num_classes
        )

    def forward(self, x):
        return self.model(x)