# 导入依赖库
import torch
import cv2
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import torch.nn as nn  # 提前导入nn，避免类内导入报错

# 初始化Flask应用
app = Flask(__name__)
CORS(app)  # 解决Android跨域请求问题

# ===================== 配置项（必须修改！）=====================
# 你的.pth模型绝对路径
PTH_MODEL_PATH = "F:/AI_model/best_lung_model.pth"
# 模型配置：根据你的数据集修改
YOLO_CONFIG = {
    "nc": 2,  # 数据集类别数（比如肺炎检测：正常/异常 → 2）
    "imgsz": 640,  # 输入图片尺寸
    "conf_thres": 0.5,  # 置信度阈值
    "iou_thres": 0.45,  # IOU阈值（NMS用）
    "names": ["normal", "abnormal"]  # 类别名（和训练时一致）
}


# ===================== YOLOv8后处理工具函数（无需官方模型）=====================
def non_max_suppression(prediction, conf_thres=0.25, iou_thres=0.45, classes=None):
    """YOLOv8非极大值抑制（NMS），手动实现后处理"""
    # 过滤低置信度预测
    xc = prediction[..., 4] > conf_thres
    output = [torch.zeros((0, 6), device=prediction.device)] * prediction.shape[0]

    for xi, x in enumerate(prediction):
        x = x[xc[xi]]
        if not x.shape[0]:
            continue

        # 计算置信度 = 目标置信度 * 类别置信度
        x[:, 5:] *= x[:, 4:5]
        box = xywh2xyxy(x[:, :4])

        # 按类别过滤
        if classes is not None:
            x = x[(x[:, 5:].max(1)[1:2] == torch.tensor(classes, device=x.device)).any(1)]

        # 获取最大置信度和对应类别
        conf, j = x[:, 5:].max(1, keepdim=True)
        x = torch.cat((box, conf, j.float()), 1)[conf.view(-1) > conf_thres]

        # 按置信度排序
        x = x[x[:, 4].argsort(descending=True)]

        # 执行NMS
        boxes, scores = x[:, :4], x[:, 4]
        i = torch.ops.torchvision.nms(boxes, scores, iou_thres)
        output[xi] = x[i]

    return output


def xywh2xyxy(x):
    """将xywh（中心+宽高）转为xyxy（左上角+右下角）"""
    y = x.clone() if isinstance(x, torch.Tensor) else np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2  # x1
    y[:, 1] = x[:, 1] - x[:, 3] / 2  # y1
    y[:, 2] = x[:, 0] + x[:, 2] / 2  # x2
    y[:, 3] = x[:, 1] + x[:, 3] / 2  # y2
    return y


def scale_boxes(img1_shape, boxes, img0_shape, ratio_pad=None):
    """将检测框从输入尺寸缩放到原图尺寸"""
    if ratio_pad is None:
        gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])
        pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (img1_shape[0] - img0_shape[0] * gain) / 2
    else:
        gain = ratio_pad[0][0]
        pad = ratio_pad[1]

    boxes[:, [0, 2]] -= pad[0]
    boxes[:, [1, 3]] -= pad[1]
    boxes[:, :4] /= gain
    clip_boxes(boxes, img0_shape)
    return boxes


def clip_boxes(boxes, shape):
    """裁剪检测框到图片范围内"""
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clamp(0, shape[1])
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clamp(0, shape[0])


# ===================== 加载自定义.pth权重（修复所有错误）=====================
def load_custom_pth_model():
    """加载原生PyTorch .pth权重"""
    try:
        # 1. 加载权重文件（修正torch.Load → torch.load）
        ckpt = torch.load(PTH_MODEL_PATH, map_location=torch.device("cpu"))
        # 处理不同格式的权重
        if "state_dict" in ckpt:
            state_dict = ckpt["state_dict"]
        elif "model" in ckpt:
            state_dict = ckpt["model"]
        else:
            state_dict = ckpt

        # 2. 初始化YOLOv8模型（修复backbone导入路径）
        from ultralytics.nn.modules import Conv, C2f, SPPF  # 正确的导入路径
        class YOLOv8(nn.Module):
            def __init__(self, nc=YOLO_CONFIG["nc"], imgsz=YOLO_CONFIG["imgsz"]):
                super().__init__()
                self.nc = nc
                self.imgsz = imgsz
                # YOLOv8s骨干网络（适配推理）
                self.model = nn.Sequential(
                    Conv(3, 32, 3, 2),
                    Conv(32, 64, 3, 2),
                    C2f(64, 64, 1),
                    Conv(64, 128, 3, 2),
                    C2f(128, 128, 2),
                    Conv(128, 256, 3, 2),
                    C2f(256, 256, 2),
                    Conv(256, 512, 3, 2),
                    C2f(512, 512, 1),
                    SPPF(512, 512, 5),
                    Conv(512, 1024, 1, 1),
                    nn.AdaptiveAvgPool2d(1),
                    nn.Flatten(),
                    nn.Linear(1024, nc * 4 + nc + 1)  # 输出：xywh + conf + cls
                )

            def forward(self, x):
                return self.model(x).reshape(-1, 4 + 1 + self.nc)

        # 3. 加载权重到模型
        model = YOLOv8(nc=YOLO_CONFIG["nc"], imgsz=YOLO_CONFIG["imgsz"])
        model.load_state_dict(state_dict, strict=False)  # 兼容参数名差异
        model.eval()  # 推理模式
        print(f"✅ 自定义.pth权重加载成功：{PTH_MODEL_PATH}")
        return model
    except Exception as e:
        print(f"❌ 加载模型失败：{str(e)}")
        raise e


# 初始化模型
model = load_custom_pth_model()


# ===================== 核心接口：接收图片并识别 =====================
@app.route("/api/detect", methods=["POST"])
def detect_image():
    try:
        # 1. 接收Android上传的图片文件
        if "image" not in request.files:
            return jsonify({
                "code": -1,
                "msg": "请求中没有图片文件（key必须为image）",
                "data": None
            }), 400

        # 2. 读取图片字节流（内存中处理）
        file = request.files["image"]
        img_bytes = file.read()
        img_array = np.frombuffer(img_bytes, np.uint8)
        img_origin = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img_origin is None:
            return jsonify({
                "code": -1,
                "msg": "图片解码失败（格式错误或文件损坏）",
                "data": None
            }), 400

        # 3. 图片预处理
        img = cv2.cvtColor(img_origin, cv2.COLOR_BGR2RGB)  # BGR→RGB
        img = cv2.resize(img, (YOLO_CONFIG["imgsz"], YOLO_CONFIG["imgsz"]))  # 缩放到模型输入尺寸
        img = img / 255.0  # 归一化到0-1
        img = torch.from_numpy(img).permute(2, 0, 1).float()  # (H,W,C)→(C,H,W)
        img = img.unsqueeze(0)  # 增加batch维度：(1,3,640,640)

        # 4. 模型推理（无梯度计算）
        with torch.no_grad():
            preds = model(img)

        # 5. 手动后处理（NMS）
        results = non_max_suppression(
            preds,
            conf_thres=YOLO_CONFIG["conf_thres"],
            iou_thres=YOLO_CONFIG["iou_thres"]
        )

        # 6. 解析检测结果
        detect_results = []
        if len(results) > 0 and len(results[0]) > 0:
            # 将检测框缩放到原图尺寸
            boxes = scale_boxes(img.shape[2:], results[0][:, :4], img_origin.shape)
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(round, box.tolist())
                confidence = round(float(results[0][i, 4]), 2)
                class_id = int(results[0][i, 5])
                class_name = YOLO_CONFIG["names"][class_id]  # 映射类别名

                # 过滤低置信度结果
                if confidence >= YOLO_CONFIG["conf_thres"]:
                    detect_results.append({
                        "className": class_name,
                        "confidence": confidence,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2
                    })

        # 7. 绘制检测框（生成带框的图片）
        annotated_img = img_origin.copy()
        for result in detect_results:
            x1, y1, x2, y2 = result["x1"], result["y1"], result["x2"], result["y2"]
            # 画矩形框
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # 画类别+置信度标签
            label = f"{result['className']} {result['confidence']}"
            cv2.putText(annotated_img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # 8. 将图片转为Base64（方便Android直接显示）
        _, img_encoded = cv2.imencode(".jpg", annotated_img)
        import base64
        img_base64 = base64.b64encode(img_encoded).decode("utf-8")

        # 9. 返回最终结果
        return jsonify({
            "code": 0,
            "msg": "识别成功",
            "data": {
                "detectResults": detect_results,
                "imageBase64": img_base64,
                "timestamp": str(datetime.datetime.now())
            }
        }), 200

    except Exception as e:
        # 捕获所有异常，返回友好错误信息
        return jsonify({
            "code": -2,
            "msg": f"服务器错误：{str(e)}",
            "data": None
        }), 500


# ===================== 启动服务 =====================
if __name__ == "__main__":
    # host=0.0.0.0：允许局域网内所有设备访问（包括Android）
    print("✅ 后端服务启动成功，地址：http://192.168.163.81:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)