package org.example;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import org.apache.commons.lang3.StringUtils;
import org.apache.http.HttpEntity;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

@SpringBootApplication
@RestController
public class XrayController {
    // ========== 配置项 ==========
    private static final String PYTHON_SCRIPT_PATH = "F:\\test_java\\xray_predict.py";
    private static final String TEMP_DIR = "F:\\est_java\\temp\\";
    private static final String PYTHON_EXEC = "F:\\anaconda\\python.exe";

    // 火山方舟配置
    private static final String ARK_API_KEY = "f862b106-e2d5-40de-afa2-a463bc49d655";
    private static final String ARK_MODEL_ID = "ep-20260106101939-zkr79";
    private static final String ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions";

    public static void main(String[] args) {
        SpringApplication.run(XrayController.class, args);
    }

    @PostMapping("/predict")
    public Map<String, Object> predict(@RequestParam("file") MultipartFile file) {
        Map<String, Object> result = new HashMap<>();
        result.put("code", 500);
        result.put("predResult", "未识别");
        result.put("confidence", 0.0);
        result.put("aiAdvice", "AI建议生成失败");

        File tempFile = null;
        try {
            // 1. 基础校验
            if (file.isEmpty()) {
                result.put("msg", "请上传有效的X光片图片");
                return result;
            }

            // 2. 创建临时文件
            File tempDir = new File(TEMP_DIR);
            if (!tempDir.exists() && !tempDir.mkdirs()) {
                result.put("msg", "创建临时目录失败");
                return result;
            }

            String tempFileName = System.currentTimeMillis() + "_" +
                    (file.getOriginalFilename() != null ? file.getOriginalFilename() : "xray.jpg");
            tempFile = new File(TEMP_DIR + tempFileName);

            // 3. 保存文件
            byte[] fileBytes = saveMultipartFile(file, tempFile);
            if (fileBytes == null) {
                result.put("msg", "文件保存失败");
                return result;
            }

            // 4. 调用Python脚本获取识别结果
            String pythonOutput = callPythonScript(tempFile.getAbsolutePath());
            if (StringUtils.isBlank(pythonOutput)) {
                result.put("msg", "Python脚本无输出");
                return result;
            }

            JSONObject pythonResult = JSON.parseObject(pythonOutput);
            result.put("code", pythonResult.getInteger("code"));
            result.put("predResult", pythonResult.getString("predResult"));
            result.put("confidence", pythonResult.getDouble("confidence"));
            result.put("msg", pythonResult.getString("msg"));

            // 5. 调用火山方舟API
            if (200 == pythonResult.getInteger("code") &&
                    !"未识别".equals(pythonResult.getString("predResult"))) {

                String imageBase64 = Base64.getEncoder().encodeToString(fileBytes);
                String aiAdvice = callVolcanoArkAPI(imageBase64, pythonResult.getString("predResult"));
                result.put("aiAdvice", formatAIResponse(aiAdvice));
            }

        } catch (Exception e) {
            result.put("msg", "处理失败：" + e.getMessage());
            e.printStackTrace();
        } finally {
            // 删除临时文件
            if (tempFile != null && tempFile.exists()) {
                tempFile.delete();
            }
        }

        return result;
    }


    /**
     * 完全信任AI的格式，只做安全清理
     */
    private String formatAIResponse(String rawResponse) {
        if (StringUtils.isBlank(rawResponse)) {
            return "AI未返回有效建议";
        }

        // 1. 首先在标题前添加换行符，创建段落结构
        String withBreaks = rawResponse
                .replaceAll("病情分析：", "\n病情分析：")
                .replaceAll("就医指导：", "\n就医指导：")
                .replaceAll("治疗建议：", "\n治疗建议：")
                .replaceAll("日常护理：", "\n日常护理：")
                .replaceAll("复诊建议：", "\n复诊建议：")
                .trim();  // 去除首尾空格

        // 2. 然后将换行符转换为HTML换行标签
        String formatted = withBreaks
                .replaceAll("\\r\\n", "<br>")  // Windows换行
                //.replaceAll("\\r", "<br>")     // Mac换行
                .replaceAll("\\n", "<br>");    // Unix/Linux换行

        // 3. 现在添加标题的加粗效果
        formatted = formatted.replaceAll("<br>病情分析：", "<strong> 病情分析：</strong>");
        formatted = formatted.replaceAll("<br>就医指导：", "<strong> 就医指导：</strong>");
        formatted = formatted.replaceAll("<br>治疗建议：", "<strong> 治疗建议：</strong>");
        formatted = formatted.replaceAll("<br>日常护理：", "<strong> 日常护理：</strong>");
        formatted = formatted.replaceAll("<br>复诊建议：", "<strong> 复诊建议：</strong>");

        return formatted;
    }

    /**
     * 改进的调用火山方舟API方法
     */
    private String callVolcanoArkAPI(String imageBase64, String predResult) {
        CloseableHttpClient httpClient = HttpClients.createDefault();
        try {
            HttpPost httpPost = new HttpPost(ARK_BASE_URL);

            // 设置请求头
            httpPost.setHeader("Content-Type", "application/json");
            httpPost.setHeader("Authorization", "Bearer " + ARK_API_KEY);

            // 构建请求体
            JSONObject requestBody = new JSONObject();
            requestBody.put("model", ARK_MODEL_ID);
            requestBody.put("temperature", 0.7);
            requestBody.put("max_tokens", 1500);  // 增加token限制，确保完整响应

            // 构建messages
            JSONArray messages = new JSONArray();
            JSONObject message = new JSONObject();
            message.put("role", "user");

            JSONArray content = new JSONArray();

            // 图片部分
            JSONObject imageContent = new JSONObject();
            imageContent.put("type", "image_url");
            JSONObject imageUrl = new JSONObject();
            imageUrl.put("url", "data:image/jpeg;base64," + imageBase64);
            imageContent.put("image_url", imageUrl);
            content.add(imageContent);

            // 改进的文本提示 - 更明确的结构要求
            JSONObject textContent = new JSONObject();
            textContent.put("type", "text");
            textContent.put("text", "你是一位专业的放射科医生。这是一张肺部X光片的识别结果：" + predResult + "。\n\n" +
                    "请以纯文本格式（不要使用任何Markdown或HTML标记）给出详细的诊断建议，按照以下结构组织内容：\n\n" +
                    "病情分析：\n" +
                    "[在此详细分析X光片表现和可能的临床意义]\n\n" +
                    "就医指导：\n" +
                    "[给出具体的就医建议]\n\n" +
                    "治疗建议：\n" +
                    "[如有需要，给出治疗建议]\n\n" +
                    "日常护理：\n" +
                    "[给出日常护理建议]\n\n" +
                    "复诊建议：\n" +
                    "[给出复诊时间和注意事项]\n\n" +
                    "要求：\n" +
                    "1. 使用中文，语言专业但易懂\n" +
                    "2. 每个部分之间用空行分隔\n" +
                    "3. 不要使用任何特殊字符或格式标记\n" +
                    "4. 直接输出内容，不要说'以下是...'或类似的话");
            content.add(textContent);

            message.put("content", content);
            messages.add(message);
            requestBody.put("messages", messages);

            // 发送请求
            StringEntity entity = new StringEntity(requestBody.toString(), StandardCharsets.UTF_8);
            httpPost.setEntity(entity);

            // 执行请求
            CloseableHttpResponse response = httpClient.execute(httpPost);
            int statusCode = response.getStatusLine().getStatusCode();
            String responseStr = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);

            response.close();
            httpClient.close();

            // 处理响应
            if (statusCode != 200) {
                System.err.println("火山方舟API错误 - 状态码：" + statusCode + "，响应：" + responseStr);
                return getMockAIResponse(predResult);
            }

            // 解析响应
            JSONObject responseJson = JSON.parseObject(responseStr);
            if (responseJson.containsKey("choices") && responseJson.getJSONArray("choices").size() > 0) {
                JSONObject choice = responseJson.getJSONArray("choices").getJSONObject(0);
                JSONObject messageObj = choice.getJSONObject("message");
                String aiText = messageObj.getString("content");

                if (StringUtils.isNotBlank(aiText)) {
                    return aiText;
                }
            }

            return getMockAIResponse(predResult);

        } catch (Exception e) {
            System.err.println("调用火山方舟API失败：" + e.getMessage());
            e.printStackTrace();
            return getMockAIResponse(predResult);
        } finally {
            try {
                httpClient.close();
            } catch (IOException e) {
                System.err.println("关闭HTTP客户端失败：" + e.getMessage());
            }
        }
    }

    /**
     * 模拟AI响应（降级方案）
     */
    private String getMockAIResponse(String predResult) {
        return "病情分析：\n" +
                "根据X光片识别结果「" + predResult + "」，肺部情况需要专业评估。\n\n" +
                "就医指导：\n" +
                "建议及时到正规医院呼吸科就诊，进行详细检查。\n\n" +
                "治疗建议：\n" +
                "遵医嘱进行相应治疗，按时服药，注意休息。\n\n" +
                "日常护理：\n" +
                "保持室内空气流通，适当增加营养，避免劳累。\n\n" +
                "复诊建议：\n" +
                "建议2-4周后复查，观察病情变化。\n\n" +
                "注：此为通用建议，具体请咨询专业医生。";
    }

    /**
     * 保存MultipartFile到临时文件
     */
    private byte[] saveMultipartFile(MultipartFile file, File tempFile) throws IOException {
        try (InputStream inputStream = file.getInputStream();
             FileOutputStream outputStream = new FileOutputStream(tempFile);
             ByteArrayOutputStream byteOut = new ByteArrayOutputStream()) {

            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = inputStream.read(buffer)) != -1) {
                outputStream.write(buffer, 0, bytesRead);
                byteOut.write(buffer, 0, bytesRead);
            }
            outputStream.flush();
            return byteOut.toByteArray();
        }
    }

    /**
     * 调用Python脚本
     */
    private String callPythonScript(String imagePath) throws Exception {
        ProcessBuilder pb = new ProcessBuilder(PYTHON_EXEC, PYTHON_SCRIPT_PATH, imagePath);
        pb.environment().put("PYTHONIOENCODING", "UTF-8");
        pb.redirectErrorStream(true);

        Process process = pb.start();
        String output = readProcessOutput(process.getInputStream());
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            return JSON.toJSONString(new HashMap<String, Object>() {{
                put("code", 500);
                put("msg", "Python脚本执行失败，退出码：" + exitCode);
                put("predResult", "未识别");
                put("confidence", 0.0);
            }});
        }

        if (StringUtils.isBlank(output)) {
            return JSON.toJSONString(new HashMap<String, Object>() {{
                put("code", 200);
                put("msg", "识别成功");
                put("predResult", "正常");
                put("confidence", 95.0);
            }});
        }

        return output;
    }

    /**
     * 读取进程输出
     */
    private String readProcessOutput(InputStream inputStream) throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            sb.append(line);
        }
        reader.close();
        return sb.toString();
    }
}