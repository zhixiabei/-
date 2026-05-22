import sys
import os
import json
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import warnings

warnings.filterwarnings('ignore')


# 模型定义（必须与训练代码完全一致）
def create_model():
    """创建与训练时完全相同的ResNet50模型"""
    model = models.resnet50(pretrained=False)

    # 修改第一层卷积适配单通道（与训练代码一致）
    model.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)

    # 修改全连接层（必须与训练代码完全一致）
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=0.3),
        nn.Linear(in_features, 512),
        nn.ReLU(),
        nn.Dropout(p=0.3),
        nn.Linear(512, 4)  # 4个分类
    )
    return model


def predict(image_path):
    """执行预测（与训练时预处理完全一致）"""
    try:
        # 1. 检查文件
        if not os.path.exists(image_path):
            return {
                "code": 404,
                "msg": "图片文件不存在",
                "predResult": "未识别",
                "confidence": 0.0
            }

        # 2. 加载模型
        model = create_model()

        # 3. 加载权重
        model_path = "best_lung_model.pth"
        if not os.path.exists(model_path):
            # 尝试其他路径
            possible_paths = [
                "D:\\program\\test_java\\best_lung_model.pth",
                os.path.join(os.path.dirname(__file__), "best_lung_model.pth"),
                "best_lung_model.pth"
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    break

        if not os.path.exists(model_path):
            return {
                "code": 404,
                "msg": "模型文件不存在",
                "predResult": "未识别",
                "confidence": 0.0
            }

        checkpoint = torch.load(model_path, map_location='cpu')

        # 4. 处理权重加载（与训练代码一致）
        if isinstance(checkpoint, dict):
            if 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            elif 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
            else:
                state_dict = checkpoint
        else:
            state_dict = checkpoint

        # 移除module.前缀（如果使用DataParallel训练）
        if list(state_dict.keys())[0].startswith('module.'):
            state_dict = {k[7:]: v for k, v in state_dict.items() if k.startswith('module.')}

        model.load_state_dict(state_dict, strict=False)
        model.eval()

        # 5. 图片预处理（关键：必须与训练时完全一致）
        # 训练时使用的预处理：
        # transforms.Compose([
        #     transforms.Grayscale(num_output_channels=1),
        #     transforms.Resize((224, 224)),
        #     transforms.ToTensor(),
        #     transforms.Normalize(mean=[0.5], std=[0.5])  # 归一化到 [-1, 1]
        # ])

        # 创建与训练时完全一致的预处理
        transform = transforms.Compose([
            transforms.Grayscale(num_output_channels=1),  # 灰度化
            transforms.Resize((224, 224)),  # 缩放到224x224
            transforms.ToTensor(),  # 转换为Tensor [0,1]
            transforms.Normalize(mean=[0.5], std=[0.5])  # 归一化到[-1,1]
        ])

        # 6. 加载并预处理图片
        try:
            image = Image.open(image_path).convert('L')  # 确保灰度图
        except:
            # 如果直接读取失败，尝试其他方式
            try:
                image = Image.open(image_path).convert('RGB')
                # 转换为灰度图
                image = image.convert('L')
            except Exception as e:
                return {
                    "code": 500,
                    "msg": f"图片加载失败: {str(e)}",
                    "predResult": "未识别",
                    "confidence": 0.0
                }

        # 应用预处理
        image_tensor = transform(image).unsqueeze(0)  # 增加batch维度

        # 7. 模型推理
        with torch.no_grad():
            output = model(image_tensor)
            # 使用softmax计算概率
            probabilities = torch.softmax(output, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        # 8. 类别映射（必须与训练时一致）
        class_names = ["细菌性肺炎", "COVID肺炎", "正常", "病毒性肺炎"]
        pred_idx = predicted.item()

        # 确保索引在范围内
        if pred_idx < 0 or pred_idx >= len(class_names):
            pred_idx = 2  # 默认为"正常"

        pred_result = class_names[pred_idx]
        conf_value = confidence.item() * 100

        return {
            "code": 200,
            "msg": "识别成功",
            "predResult": pred_result,
            "confidence": float(conf_value)
        }

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"预测异常: {error_msg}")
        return {
            "code": 500,
            "msg": f"预测失败: {str(e)}",
            "predResult": "未识别",
            "confidence": 0.0
        }


if __name__ == "__main__":
    # 从命令行参数获取图片路径
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        result = predict(image_path)
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps({
            "code": 400,
            "msg": "请提供图片路径",
            "predResult": "未识别",
            "confidence": 0.0
        }, ensure_ascii=False))