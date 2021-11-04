import torch
from torchvision import transforms
from PIL import Image
import unet.unet_model as unet


class IVUS:
    def __init__(self):
        self.model_path = "./model/ver1.0_4.pkl"
        # 加载模型
        self.UNet = unet.UNet(n_channels=1, n_classes=2).cuda()
        self.UNet.load_state_dict(torch.load(self.model_path))
        self.UNet.eval()

    def ivus_classify(self, frame):
        preprocess_transforms = transforms.Compose([    # 初等图像预处理变换
            transforms.ToTensor()
        ])

        image_PIL = Image.fromarray(frame).convert('L')
        image_tensor = preprocess_transforms(image_PIL)
        image_tensor_unsq = torch.unsqueeze(image_tensor, 0).cuda()

        test_output = self.UNet(image_tensor_unsq)
        pred_y = torch.max(test_output, 1)[1].data  # 预测结果

        numpy_img = pred_y.cpu().numpy()[0, :, :] * 255
        # 保存原数据帧
        if numpy_img[numpy_img == 255].shape[0] != 0:
            frame[:, :, 1][numpy_img == 255] += 100
        # 保存处理后的数据帧
        return frame



